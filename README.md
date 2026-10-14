# cp2kkit

连接 CP2K 结果读取、可追溯后处理与非破坏性输入生成的 Python 工具。根据
[`cp2kkit-mvp.md`](cp2kkit-mvp.md) 开发的 **v0.2.2 初步实现**，不是已完成真实版本认证的生产发布。

- 分析命令保持只读；不提交或运行 CP2K，不改已有输入、restart 或原始输出。
- 六项 MVP 已有实现入口；另有 `generate-input`、`cube-check`、`cube-diff`；不自动运行计算。
- 核心仅使用 Python 标准库；绘图可选依赖 Matplotlib。
- 输出带 schema、单位、文件 SHA-256、行号与原文；缺失值不等同于零。
- 任何已有目标文件都拒绝覆盖，包括派生 CSV、JSON 和图片。
- 能量数值可以从失败任务提取，但不自动成为有效结果。

## 当前版本：0.2.2

应用主菜单显示 `cp2kkit Main menu`，输入编辑主菜单及所有子菜单、标签、提示、预览和确认信息
统一为英文；菜单编号、功能与计算默认参数不变。版本按用户指定更新为 0.2.2。
保留 0.2.1 的简洁 EPS 科学计数法与 CELL/COORD 固定 8 位小数格式。
完整变化与迁移提示见 [变更记录](CHANGELOG.md)。软件版本为 0.2.2，数据 schema 仍为 0.1.0；
不代表 CP2K 运行认证。

## 快速开始

Python >= 3.10。无需安装即可在项目根目录运行：

```bash
export PYTHONPATH="$PWD/src"
python -m cp2kkit --help
python -m cp2kkit discover tests/fixtures
python -m cp2kkit parse tests/fixtures/normal.out
python -m cp2kkit report tests/fixtures/unconverged.out --strict
```

安装到现有 Python 环境：

```bash
uv pip install -e .
# 仅需绘图时安装可选依赖
uv pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e '.[plot]'
cp2kkit --help
```

以上 `tests/fixtures` **都是合成格式样例，不是科学计算结果**。

## 默认主菜单与 CLI

```bash
cp2kkit                 # 进入主菜单，可按编号选择当前目录文件或输入路径
cp2kkit crystal.cif     # 加载结构后进入主菜单
cp2kkit water.gjf
cp2kkit POSCAR
```

主菜单提供加载/更换结构、CP2K 输入生成、extXYZ 导出和输出质量报告。
输入生成完成或取消后回到应用主菜单；加载失败不会替换已加载结构。
交互入口要求 TTY；脚本仍使用以下子命令，原有批处理接口保留。

## CLI 子命令

```bash
# 目录识别：仅扫描一层；无项目时返回空列表
cp2kkit discover /path/to/run

# 多项目目录必须指定项目；同项目多个输出必须指定具体文件
cp2kkit parse /path/to/run --project water -o parsed.json
cp2kkit parse /path/to/run/water.out --format csv -o energy.csv

# 电子 / 几何收敛分开记录；--strict 未通过时退出码为 7
cp2kkit report /path/to/run/water.out --strict -o quality.json

# 结构：最后一帧默认值为 -1；推荐 extXYZ 保留晶胞
cp2kkit export-structure /path/to/run/water.restart -o water.extxyz
cp2kkit export-structure /path/to/run/water-pos-1.xyz --frame 0 -o first.extxyz
# 有晶胞的结构转普通 XYZ 必须明确同意信息丢失
cp2kkit export-structure water.restart --format xyz --allow-cell-loss -o water.xyz

# 输出 curve.png + curve.csv + curve.json，任一文件已存在则全部拒绝
cp2kkit plot /path/to/run/water.out -o curve.png
cp2kkit plot /path/to/run/water.out --kind scf -o scf.png
```

未提供 `--output` 时，discover / parse / report / cube-check 向 stdout 写机器可读数据，
诊断向 stderr 输出。目标父目录需事先存在，不会自动创建大量目录。
结构导出额外生成 `<完整输出文件名>.json`，其中保留原晶胞、坐标、来源和告警。

### 退出码

| 码 | 含义 |
|---:|---|
| 0 | 命令执行完成（不代表计算质量合格） |
| 2 | 参数、路径或文件系统问题 |
| 3 | 项目 / 输出选择歧义 |
| 4 | 不支持、损坏或无法解析的数据 |
| 5 | 输出已存在，拒绝覆盖 |
| 6 | 缺少绘图可选依赖 |
| 7 | `report --strict` 的质量检查未通过 |

## CP2K 输入生成

参照 Multiwfn `cp2kmate.f90` 新增 GPW 输入生成子集：

```bash
cp2kkit generate-input water.xyz -o water.inp --periodic NONE --project water
cp2kkit generate-input water.xyz -o water-opt.inp --periodic NONE \
  --run-type GEO_OPT --dispersion d3bj
cp2kkit generate-input solid.extxyz -o solid.inp --run-type CELL_OPT \
  --scf diag --kpoints 3 3 3 --smearing 300
```

另有 Multiwfn 风格的数字菜单模式，原有传参方式保持不变：

```bash
cp2kkit generate-input --tui
# 已传参数作为菜单初值，可以继续修改
cp2kkit generate-input water.xyz -o water.inp --periodic NONE --tui
# 终端中直接运行 generate-input（不提供结构/输出）也进入菜单
cp2kkit generate-input
```

支持分组编辑、完整输入预览、可复现命令及写入前明确确认；q 取消不生成文件。
仅需标准库，不依赖 curses/Multiwfn；是数字选择的行式 TUI，不是全屏方向键界面。
非终端批处理仍使用原 CLI，不会自动进入菜单。详情见 [输入生成文档](docs/input-generation.md)。

支持 ENERGY / ENERGY_FORCE / GEO_OPT / CELL_OPT，PBE/BLYP、MOLOPT-GTH、
D3/D3(BJ)、电荷/多重度、晶胞/PBC、OT/对角化与 k 点。
输出输入文件及 `<output>.json`，两者均拒绝覆盖。
结构支持 XYZ/extXYZ、restart、Cartesian GJF/COM、CIF 与 VASP5 POSCAR/CONTCAR。
默认 PROJECT 为结构文件名去后缀，网格为 400/55 Ry；OT 内/外 SCF 上限为 25/20。
diag 开启展宽后自动设空轨道 `max(30, NINT(原子数/2))`，可手动覆盖。
普通 XYZ 必须明确指定周期性；仅从源文件继承结构而非计算设置。
可用 `--data-dir` 核对基组/赝势名字并记录数据文件哈希。
**未运行 CP2K 验证；不等于完整移植 Multiwfn。**
范围、默认参数与限制见 [输入生成文档](docs/input-generation.md)。
Multiwfn 来源、自定义授权条款及必需引用见 [第三方声明](THIRD_PARTY_NOTICES.md)；
这不代表已取得单独授权或确认再许可/收费分发边界。

## 密度 cube 输出与差分

```bash
# 在仓库根目录，无需安装即可调用
export PYTHONPATH="$PWD/src"
python -m cp2kkit generate-input AB.extxyz -o AB-density.inp --project AB \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1
python -m cp2kkit cube-check AB.cube -o AB-cube-check.json
python -m cp2kkit cube-diff AB.cube A.cube B.cube -o delta-density.cube
python -m cp2kkit cube-check delta-density.cube
```

输入生成增加 `--electron-density`、`--spin-density`、`--cube-stride`。
GPW/GTH 输出是赝势显式价电子密度；UKS 同时附带 alpha-minus-beta 自旋密度。
目标版本默认 2026.2，密度输出共同语法兼顾 2024.1–2026.2 的显式版本配置；
这不是实际程序认证。优化关闭常规步 cube 输出，请求最终步；用于相减优先最终固定构型单点。

cube 逐行读取，报告网格、哈希、单位依据和积分；未知标量只报告原始数值积分。
差分为 `rho[0] - sum(rho[1:])`，允许多个片段及不同原子数，严格比较规范化单位后的网格，
不插值/配准。输出 cube + JSON 先临时写入，再独占发布，已有目标拒绝覆盖。
**密度差正负部分积分不是片段净电荷转移；网格相同也不能证明计算参考态一致。**
格式、单位策略、物理条件、完整 AB/A/B 示例及验证边界见 [cube 文档](docs/cube.md)。

## 已实现范围与限制

| MVP 功能 | 初步实现 |
|---|---|
| CLI 与项目识别 | 确定性排序、单层扫描、多项目显式选择、稳定退出码 |
| CP2K 输出解析 | 总能量、SCF 汇总、几何结束/失败标记、版本/项目/run type、诊断与部分设置 |
| 结构与晶胞导出 | 严格 XYZ/extXYZ、文本 restart 子集、三斜晶胞、bohr 转换、scaled 坐标 |
| 计算质量报告 | 完成状态、电子/几何状态、证据链接；未知/截断不可成功 |
| CSV / JSON 与来源 | schema `0.1.0`、显式单位、null/空 CSV 值、原文/行号/哈希、质量标记 |
| 能量与收敛曲线 | 能量和每轮 SCF 迭代次数；片段不连线；CSV 与 JSON sidecar |

### 兼容性声明

**当前仅完成合成格式回归；尚无经真实计算样例认证的 CP2K 版本。**
解析器按明确的输出标记工作，不根据文件后缀或版本号猜测成功。
样例中的 “2026.1” 不是认证证据。真实样例与源格式核对是下一阶段的发布门槛。

- 支持 `ENERGY| Total FORCE_EVAL (...) energy [a.u.]`，能量保留 hartree。
- `PROGRAM ENDED AT` 只证明正常结束标记存在，不能单独证明收敛。
- 正向质量规则仅覆盖 ENERGY / ENERGY_FORCE / GEO_OPT / CELL_OPT；
  MD、BAND/NEB 等可有可解析记录，但不能由本版规则判为 passed。
- `passed` 仅表示文本证据通过，不等于基组、赝势、泛函、色散、k 点、
  电荷、自旋或周期设置适合研究目标。应人工核对。
- 缺少版本、力/应力、设置、时间、进程退出码时不推断；
  当前仅识别显式 `Total wall time [s]` / `WALL TIME [s]`，不解析 CP2K 的完整 TIMER 表。
- 设置按原文保存，不将缺失项补成 CP2K 默认值，也不从输入文件隐式合并。
- “收敛曲线”目前是 SCF **迭代次数**曲线，不是 SCF 残差或优化梯度曲线。
- 新启动标记或步号不递增会拆分片段；不做重启能量连续性的推断。
- XYZ 中没有晶胞时明确告警；默认不会把它当成非周期结构。
- restart 仅支持一个 SUBSYS，显式 CELL/COORD 与 KIND/ELEMENT；
  不展开预处理指令、外部坐标文件或 CELL/COORD 子节。未知相关语法拒绝解析。
- 输入按 UTF-8 严格读取；现有输出/restart 解析读取全文件，超大输出的流式解析为后续优化项。
  新 cube 通道使用逐行限长迭代，不保留完整标量数组；当前仅支持单标量子集。

## 测试

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m compileall -q src tests
```

测试不执行量化计算、不需要 pytest；Matplotlib 缺失时仅跳过绘图测试。
详见 [架构](docs/architecture.md)、[schema](docs/schema.md)、
[开发路线](docs/roadmap.md) 与 [样例来源](tests/fixtures/README.md)。
