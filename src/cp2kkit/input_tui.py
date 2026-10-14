"""Numbered, line-oriented input editor inspired by Multiwfn outCP2Kinp.

Reference: Multiwfn 2026.10.1 cp2kmate.f90 menu loop; no Fortran UI code
is distributed or used at runtime. See third_party/multiwfn/PROVENANCE.md.
Required references: Lu & Chen, J. Comput. Chem. 33, 580 (2012),
doi:10.1002/jcc.22885; Lu, J. Chem. Phys. 161, 082503 (2024),
doi:10.1063/5.0216272. This UI delegates chemistry/serialization to inputgen.
"""
import math
import shlex
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import KitError
from .inputgen import (BASES, CP2K_VERSIONS, FUNCTIONALS, PERIODICITIES, RUN_TYPES,
                       InputSettings, generate_input, write_input)
from .structure import read_structure


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    kind: str = "text"
    choices: tuple = ()
    optional: bool = False
    minimum: float | None = None
    positive: bool = False


# Every InputSettings field is editable; menu numbering is local, not upstream's.
GROUPS = (
    ("文件、项目与版本", (
        Field("path", "结构路径（XYZ/extXYZ/restart；路径含空格时无需引号）"),
        Field("frame", "XYZ 帧索引（默认 -1；restart 忽略）", "int"),
        Field("output", "新输入文件路径（同时生成 .json）"),
        Field("project", "项目名"),
        Field("cp2k_version", "目标 CP2K 版本（非运行认证）", choices=CP2K_VERSIONS))),
    ("任务与优化", (
        Field("run_type", "任务", choices=RUN_TYPES),
        Field("optimizer", "优化器（仅优化任务有效）", choices=("BFGS", "LBFGS", "CG")),
        Field("max_iter", "最大优化步数", "int", minimum=1),
        Field("pressure", "CELL_OPT 外压 [bar]", "float"))),
    ("方法、基组与色散", (
        Field("functional", "泛函（GPW/GTH）", choices=FUNCTIONALS),
        Field("basis", "基组（赝势随泛函/元素预设匹配）", choices=BASES),
        Field("dispersion", "色散", choices=("none", "d3", "d3bj")),
        Field("data_dir", "CP2K data 目录（核对名字与哈希）", optional=True))),
    ("电荷与自旋", (
        Field("charge", "总电荷 [e]（不从 restart 继承）", "int"),
        Field("multiplicity", "自旋多重度（>1 启用 UKS；不继承磁态）", "int", minimum=1))),
    ("周期性与晶胞", (
        Field("periodic", "周期性（auto 继承源 PBC；XYZ 未知时必须明确选择）",
              choices=PERIODICITIES, optional=True),
        Field("cell", "正交晶胞覆盖 A B C [angstrom]（auto 保留源晶胞）",
              "float3", optional=True, positive=True),
        Field("vacuum", "自动孤立盒子每侧 padding [angstrom]", "float", positive=True))),
    ("SCF、k 点与占据", (
        Field("scf", "SCF（OT 适用于有隙体系，金属应核对 diag/展宽）", choices=("ot", "diag")),
        Field("eps_scf", "EPS_SCF（auto 为任务默认值）", "float", optional=True, positive=True),
        Field("max_scf", "最大 SCF 步数", "int", minimum=1),
        Field("kpoints", "MONKHORST-PACK NX NY NZ（非 Gamma 要求 XYZ + diag）", "int3", minimum=1),
        Field("smearing", "Fermi-Dirac 温度 [K]（auto 关闭；要求 diag）",
              "float", optional=True, positive=True),
        Field("added_mos", "ADDED_MOS（展宽要求 >0）", "int", minimum=0))),
    ("积分网格", (
        Field("cutoff", "CUTOFF [Ry]", "float", positive=True),
        Field("rel_cutoff", "REL_CUTOFF [Ry]", "float", positive=True))),
    ("电子/自旋密度 cube", (
        Field("electron_density", "电子密度（GPW 赝势显式价电子密度）", "bool"),
        Field("spin_density", "自旋密度（alpha-minus-beta；要求 UKS）", "bool"),
        Field("cube_stride", "STRIDE NX NY NZ（auto 为 1 1 1；需先开启密度）",
              "int3", optional=True, minimum=1))),
)


def display(value):
    if value is None:
        return "auto / 未设置"
    if type(value) is bool:
        return "开启" if value else "关闭"
    if isinstance(value, tuple):
        return " ".join(map(str, value))
    return str(value)


def parse_value(field, raw):
    """Local lexical/range validation only; cross-field chemistry stays in inputgen."""
    if field.optional and raw.lower() == "auto":
        return None
    if field.choices:
        if raw in tuple(str(i) for i in range(1, len(field.choices)+1)):
            return field.choices[int(raw)-1]
        for choice in field.choices:
            if raw.casefold() == choice.casefold():
                return choice
        raise ValueError("请选择列出的编号或名称")
    if field.kind == "bool":
        if raw.lower() in ("y", "yes", "1", "true", "on", "开启"):
            return True
        if raw.lower() in ("n", "no", "0", "false", "off", "关闭"):
            return False
        raise ValueError("请输入 y/n（开启/关闭）")
    if field.kind == "text":
        if any(ord(c) < 32 or ord(c) == 127 for c in raw):
            raise ValueError("文本或路径不能包含控制字符")
        return raw
    converter = int if field.kind.startswith("int") else float
    if field.kind.endswith("3"):
        parts = raw.split()
        if len(parts) != 3:
            raise ValueError("需要三个以空格分隔的数")
        value = tuple(converter(p) for p in parts)
        numbers = value
    else:
        value = converter(raw)
        numbers = (value,)
    for number in numbers:
        if isinstance(number, float) and not math.isfinite(number):
            raise ValueError("数值必须有限，不能为 NaN/Inf")
        if field.positive and number <= 0:
            raise ValueError("数值必须为正")
        if field.minimum is not None and number < field.minimum:
            raise ValueError(f"数值必须 >= {field.minimum:g}")
    return value


def command_arguments(path, frame, output, settings):
    """Replayable argv; no shell execution. Equals protects dash-prefixed text."""
    args = [sys.executable, "-m", "cp2kkit", "generate-input", str(Path(path).resolve()),
            f"--frame={frame}", f"--output={output}"]
    for name, value in asdict(settings).items():
        flag = "--" + name.replace("_", "-")
        if type(value) is bool:
            if value:
                args.append(flag)
        elif value is not None:
            if isinstance(value, tuple):
                args.extend([flag, *map(str, value)])
            else:
                args.append(f"{flag}={value}")
    return args


class Cancelled(Exception):
    """Explicit user cancellation: no output, successful return."""


class Menu:
    def __init__(self, stdin, stdout):
        self.stdin, self.stdout = stdin, stdout

    def show(self, text=""):
        print(text, file=self.stdout)

    def ask(self, prompt):
        self.stdout.write(prompt)
        self.stdout.flush()
        line = self.stdin.readline()
        if not line:
            raise EOFError
        raw = line.strip()
        if raw.lower() in ("q", "quit"):
            raise Cancelled
        return raw

    def edit(self, field, current):
        self.show(field.label)
        for i, choice in enumerate(field.choices, 1):
            self.show(f"  {i}. {choice}")
        extra = "; auto 恢复自动/关闭可选值" if field.optional else ""
        while True:
            raw = self.ask(f"当前 [{display(current)}]；回车保持{extra}；q 取消: ")
            if not raw:
                return current
            try:
                return parse_value(field, raw)
            except ValueError as exc:
                self.show(f"无效输入: {exc}")

    def group(self, title, fields, values):
        while True:
            self.show(f"\n--- {title} ---")
            for i, field in enumerate(fields, 1):
                self.show(f"  {i}. {field.label}: {display(values[field.name])}")
            raw = self.ask("选择项目编号；0 返回主菜单；q 取消: ")
            if raw == "0":
                return
            if raw not in tuple(str(i) for i in range(1, len(fields)+1)):
                self.show("无效菜单编号")
                continue
            field = fields[int(raw)-1]
            values[field.name] = self.edit(field, values[field.name])

    def review(self, values, full=False):
        """Read and validate without writing; caller can fix an invalid draft."""
        settings = InputSettings(**{name: values[name] for name in InputSettings.__dataclass_fields__})
        structure = read_structure(values["path"], values["frame"])
        text, manifest = generate_input(structure, settings)
        self.show("\n--- 已校验生成参数（不是运行/收敛认证）---")
        self.show(f"原子数: {len(structure.symbols)}；显式价电子数: {manifest['valence_electron_count']}")
        self.show(f"目标版本: {settings.cp2k_version}；任务: {settings.run_type}；方法: GPW/{settings.functional}")
        self.show(f"SCF: {settings.scf}；有效 EPS_SCF: {manifest['effective_eps_scf']}；Poisson: {manifest['poisson_solver']}")
        self.show(f"实际晶胞 [angstrom]: {manifest['generated_structure']['cell']}")
        self.show(f"原子坐标已平移: {manifest['coordinates_translated']}；基组/赝势: {manifest['kinds']}")
        self.show(f"有效密度输出: electron={manifest['density_output']['electron_density']}, "
                  f"spin={manifest['density_output']['spin_density']}, stride={manifest['density_output']['stride']}")
        for warning in manifest["warnings"]:
            self.show(f"WARNING: {warning}")
        self.show(f"将新建: {values['output']} 和 {values['output']}.json")
        self.show("可复现命令（当前工作目录；不会自动执行）:")
        self.show(shlex.join(command_arguments(values["path"], values["frame"], values["output"], settings)))
        if full:
            self.show("\n--- 输入预览（未写入）---\n" + text)
        return structure, settings


def run_interactive(path, frame, output, settings, stdin=None, stdout=None):
    """Edit CLI-seeded settings; only an explicit final yes writes new files."""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    if not stdin.isatty():
        raise KitError("Interactive generation requires a terminal (TTY); use generate-input PATH -o OUTPUT for scripts")
    menu = Menu(stdin, stdout)
    values = {**asdict(settings), "path": path, "frame": frame, "output": output}
    try:
        menu.show("CP2K 输入生成 — Multiwfn 风格数字菜单（当前 GPW 子集）")
        menu.show("只生成新文件，不运行计算；不从 restart 继承电荷/自旋/方法；q 随时取消。")
        for field in (GROUPS[0][1][0], GROUPS[0][1][2]):
            while not values[field.name]:
                values[field.name] = menu.edit(field, values[field.name])
        while True:
            menu.show("\n=== 主菜单：当前设置 ===")
            for i, (title, fields) in enumerate(GROUPS, 1):
                summary = "; ".join(f"{f.name}={display(values[f.name])}" for f in fields)
                menu.show(f"  {i}. {title}: {summary}")
            raw = menu.ask("9 预览完整输入与命令；0 校验并确认生成；q 取消；或选择组编号: ")
            if raw in ("0", "9"):
                try:
                    structure, updated = menu.review(values, full=raw == "9")
                except (KitError, OSError) as exc:
                    menu.show(f"校验失败（未写文件）: {exc}\n请返回菜单修改相关参数。")
                    continue
                if raw == "9":
                    continue
                answer = menu.ask("确认写入上述两个新文件？[y/N]（q 取消）: ").lower()
                if answer not in ("y", "yes"):
                    menu.show("未确认，返回菜单；未写文件。")
                    continue
                # Existing writer retains exit codes, collision protection and rollback.
                result = write_input(structure, updated, values["output"])
                menu.show(f"已生成 {result[0]} 和 {result[1]}")
                return 0
            if raw in tuple(str(i) for i in range(1, len(GROUPS)+1)):
                title, fields = GROUPS[int(raw)-1]
                menu.group(title, fields, values)
            else:
                menu.show("无效菜单编号")
    except Cancelled:
        menu.show("已取消；未生成文件。")
        return 0
    except (EOFError, KeyboardInterrupt) as exc:
        raise KitError("Interactive session interrupted; completed files, if any, are retained") from exc
