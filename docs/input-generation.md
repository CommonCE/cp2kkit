# CP2K 输入生成

`generate-input` 是在原只读 MVP 外新增的显式写入入口，不运行或提交计算。
这是参考 Multiwfn `outCP2Kinp` 开发的 Python GPW 子集，不是 Fortran 全量移植或严格净室实现。
来源、官方自定义授权条款及必需的两篇论文引用见
[第三方声明](../THIRD_PARTY_NOTICES.md)、
[条款记录](../third_party/multiwfn/TERMS.md)及
[模块来源登记](../third_party/multiwfn/PROVENANCE.md)。生成的输入和 JSON 均带论文引用；
相关研究论文仍应按照官方条款在正文中恰当引用。

## 使用

```bash
# 普通 XYZ 不带周期信息，必须明确 NONE 或周期方向
cp2kkit generate-input water.xyz -o water.inp --project water --periodic NONE

# 几何优化：PBE-D3(BJ)，自动构造孤立盒子，每侧留 6 angstrom
cp2kkit generate-input water.xyz -o water-opt.inp --periodic NONE \
  --run-type GEO_OPT --dispersion d3bj --vacuum 6

# extXYZ / restart 的晶胞和周期方向默认保留，但不继承原计算方法/电荷/自旋
cp2kkit generate-input solid.extxyz -o solid.inp --run-type CELL_OPT \
  --scf diag --kpoints 3 3 3 --smearing 300 --added-mos 30

# 显式覆盖晶胞：三个正交边长，angstrom；电荷 +1、二重态
cp2kkit generate-input radical.xyz -o radical.inp --periodic NONE \
  --cell 20 20 20 --charge 1 --multiplicity 2 --functional BLYP

# 核对本地数据文件名字，并保存文件哈希；D3 还需 dftd3.dat
cp2kkit generate-input water.xyz -o checked.inp --periodic NONE \
  --data-dir /path/to/cp2k/data

cp2kkit generate-input --help
```

输出 `<output>` 和 `<output>.json`。任何一个已存在则拒绝覆盖（退出码 5），
sidecar 冲突时撤销本次新建输入；无 `--force`。父目录必须存在。

## Multiwfn 风格 TUI 选择模式

```bash
# 纯交互入口，提示填写结构和新输出路径
cp2kkit generate-input --tui
cp2kkit generate-input --interactive     # 同义选项

# 传参 + 交互：给定参数作为初值，没有不同的默认方法/网格
cp2kkit generate-input water.xyz -o water-opt.inp --periodic NONE \
  --run-type GEO_OPT --dispersion d3bj --electron-density --tui

# 在终端中，未提供结构和输出时自动进入菜单
cp2kkit generate-input
```

数字菜单逐项修改，每次显示当前值；不是必须从头走完的向导。
使用标准库行式交互，支持常规终端/SSH，不安装 curses 或额外 UI 依赖。
不依赖 Multiwfn 二进制或开发时邻目录源码。

| 主菜单 | 内容 |
|---:|---|
| 1 | 结构、XYZ 帧、新输出路径、项目名、目标 CP2K 版本 |
| 2 | ENERGY/ENERGY_FORCE/GEO_OPT/CELL_OPT、优化器、步数、外压 |
| 3 | GPW 泛函、MOLOPT-GTH 基组、色散、可选 data 目录 |
| 4 | 电荷和自旋多重度 |
| 5 | PBC、正交晶胞覆盖（angstrom）、孤立盒子 padding（angstrom） |
| 6 | OT/diag、EPS_SCF、步数、k 点、展宽（K）、空轨道 |
| 7 | CUTOFF / REL_CUTOFF（Ry） |
| 8 | 电子/自旋密度开关与 STRIDE |
| 9 | 校验并预览完整输入、来源相关告警和可复现 CLI 命令；不写文件 |
| 0 | 校验、显示有效参数与告警，明确输入 y/yes 后才生成 |
| q / quit | 取消整个会话，不生成文件 |

- 进入组后选择字段编号；组内 `0` 返回主菜单。字段编辑时回车保留原值。
- 枚举值接受列出的编号或名称；布尔值接受 y/n；三元参数用空格分隔。
- 可选字段输入 `auto` 恢复默认/取消覆盖。PBC 的 `auto` 是继承源 PBC，**不是 NONE**；
  smearing 的 `auto` 是关闭展宽；cell 的 `auto` 保留源晶胞；cube_stride 的 `auto` 恢复有效默认。
- 路径可包含空格，菜单中输入字面路径、不加 shell 引号。`q`/`quit` 是取消命令，
  字面同名文件可用 `./q`/`./quit`。输出父目录需存在。
- 类型/范围错误就地重输；跨字段/结构错误在预览或生成时提示，并返回菜单供修改。
  例如开自旋密度而未启用 UKS、OT + 非 Gamma k 点、未知 PBC，都不自动改变其他参数来修复。
- 生成确认默认否，空回车返回菜单。目标已存在仍退出 5；不提供覆盖按钮。
  EOF/Ctrl-C 以错误码 2 结束；未完成写入沿用原 writer 回滚，已完成文件保留。
- TUI 要求 stdin 为 TTY，不能用管道伪装交互式确认；脚本应使用原 CLI。
  stdout 可重定向保存菜单/预览记录。带完整结构/输出的普通调用即使在终端也不会进入 TUI。

两种模式使用同一个 `InputSettings`、`generate_input`、`write_input`。
相同结构/参数生成相同输入和 JSON；无额外 TUI 特有的物理默认值，schema 保持不变。
预览给出 shell 引用后的可复现命令，仅显示，不执行。菜单只覆盖当前 GPW 子集，
不暗示已实现 Multiwfn 全部任务/方法；CP2K 版本和科学限制与下面的 CLI 相同。

## 范围与默认值

| 设置 | 支持 / 默认 |
|---|---|
| 结构 | `.xyz` / `.extxyz` / 文本 `.restart`；继承现有严格读取限制；XYZ 默认末帧 |
| 任务 | ENERGY（默认）、ENERGY_FORCE、GEO_OPT、CELL_OPT |
| 方法 | Quickstep / GPW；PBE（默认）、BLYP |
| 基组 | 默认 DZVP-MOLOPT-SR-GTH；另有 SZV-MOLOPT-SR-GTH、DZVP/TZVP/TZV2P-MOLOPT-GTH |
| 赝势 | GTH-PBE / GTH-BLYP；基组与赝势显式匹配 `-qN` |
| 色散 | none（默认）、D3、D3(BJ)；使用 dftd3.dat 与 REFERENCE_FUNCTIONAL |
| 电荷 / 自旋 | 0 / 1（默认）；显式价电子计数检查奇偶性，multiplicity > 1 时 UKS |
| SCF | OT + FULL_ALL/DIIS + outer SCF（默认）；或对角化 + Broyden mixing |
| SCF 阈值 | ENERGY 为 5e-6，其余任务为 1e-6；可覆盖 |
| SCF 步数 | 内层 / 对角化最大 128，OT outer SCF 最大 20 |
| 网格 | CUTOFF 350 Ry、REL_CUTOFF 50 Ry；非 SR 基组 NGRIDS 5，SR 为 4 |
| k 点 | 默认 Gamma；非 Gamma 仅支持 XYZ + 对角化 |
| 展宽 | 可选 Fermi-Dirac 温度（K）；要求对角化和正的 ADDED_MOS |
| 优化 | BFGS（默认）、LBFGS、CG；最大 400 步 |
| CELL_OPT | 要求 XYZ、下三角晶胞，输出解析应力；默认外压 1.01325 bar |
| 目标版本 | `--cp2k-version` 默认 2026.2；密度输出共同语法配置提供 2024.1/2/3、2025.1/2、2026.1/2，不是运行认证 |
| 密度 cube | 可选电子密度及适用 UKS 自旋密度；有效 STRIDE 默认 1 1 1；最终步策略见 [cube 文档](cube.md) |

SR 基组/PBE 预设覆盖 71 个元素：

```text
H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar
K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr
Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba
Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn
```

非 SR 基组仅覆盖 H C N O F Si P S Cl。
BLYP 不提供 Nb Tc Cd Sn Hf Ta Re Os Ir Pt Hg Tl Po At Rn 的预设，缺项直接拒绝。
这不是任意元素或任意赝势的自动推断；实际安装库必须含匹配名字。

## 周期性、晶胞与科学限制

- 不把普通 XYZ 默认为孤立分子。未知周期性必须提供 `--periodic`。
- 优先使用结构中晶胞；`--cell A B C` 显式覆盖成正交晶胞。
- 仅在 NONE 且无晶胞时自动构造盒子：各轴原子跨度 + 两侧 vacuum；
  坐标平移到盒内，原结构与实际生成坐标均记录。不修改源文件。
- 已有或显式晶胞不自动居中；孤立体系须自行保证电子密度在边界消失。
- CELL 与 POISSON 周期方向一致。XYZ 用 PERIODIC，NONE 用 WAVELET，
  1D/2D 用 ANALYTIC。后者收敛可能慢，需检查真空与静电误差。
- 本版 OT 不带金属所需的高级旋转/占据配置。金属应选择 diag、适当 k 点、展宽及空轨道数。
- 电荷/多重度检查仅保证显式电子数的一致性，不保证正确磁态。
  不支持反铁磁、破缺对称单重态或逐 KIND MAGNETIZATION。
- restart **只提供结构**；原 KIND 标签按元素合并，原方法、U、约束、磁矩、
  电荷、溶剂等不继承。这是新计算模板，不是原任务的完整续算输入。
- 未实现混合泛函/ADMM、DFT+U、MD、频率、NEB、TDDFT、溶剂、外场、
  原子约束等 Multiwfn 高级选项；电子/自旋密度 cube 已加入，其他势/ELF/MO cube 等尚未实现。
- 默认 cutoff / 基组 / 真空 / k 点不是经目标体系收敛验证的参数。
  不输出已废弃的 CELL_OPT TYPE DIRECT_CELL_OPT。

## 电子/自旋密度输出

```bash
cp2kkit generate-input AB.extxyz -o AB-density.inp --project AB \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1
```

不开启时不增加密度 PRINT；`--spin-density` 要求当前生成器的 UKS 条件（multiplicity > 1）。
CP2K 在同一个 E_DENSITY_CUBE 节控制电子与自旋密度，因此 UKS 下两者都会写出。
优化常规步频为 0，ADD_LAST NUMERIC 请求最终步；不保证异常终止产生 cube 或最后一步已收敛。
完整频率、文件行为、GPW 价电子密度含义及老版本差异见 [cube 文档](cube.md)。

## 可复现性与验证等级

JSON 记录生成器版本、完整输入及其 SHA-256、全部参数与单位、有效 SCF 阈值、
每种元素的基组/赝势/显式电子数、源结构路径/哈希/帧、实际生成结构、平移与警告。
`runtime_version=null`、`runtime_validated=false`，不把目标软件当成实际运行版本。

提供 `--data-dir` 时读取本地 BASIS_MOLOPT、GTH_POTENTIALS，核对元素/名字头行并记录哈希；
D3 时也记录 dftd3.dat。它不认证文件系数或参数内容。
不提供该参数时使用文件 basename，由运行环境 CP2K_DATA_DIR 查找，不声称已核对实际安装库。
运行时的 CP2K 二进制版本仍需由后续计算记录。

已完成合成回归、节平衡与结构回读；没有启动 CP2K，尚未通过真实程序的语法/运行认证。

## 参考

- 用户提供的 `../Multiwfn_2026.10.1_src_Linux/cp2kmate.f90`：
  `outCP2Kinp`，行 68–3448；参考基组名字、Nval、任务与节结构。
  阅读时文件 SHA-256：`f533bcfe3db73265a1d768bbc68097c9a7851bdd6fbcde9c0600f151ea609402`。
  不复制或分发原 Fortran 源文件，不依赖邻目录存在。
- CP2K 数据库头行核对（不是运行认证）：
  [BASIS_MOLOPT](https://github.com/cp2k/cp2k/blob/master/data/BASIS_MOLOPT)、
  [GTH_POTENTIALS](https://github.com/cp2k/cp2k/blob/master/data/GTH_POTENTIALS)。
- 官方输入参考：
  [POISSON](https://manual.cp2k.org/trunk/CP2K_INPUT/FORCE_EVAL/DFT/POISSON.html)、
  [OT](https://manual.cp2k.org/trunk/CP2K_INPUT/FORCE_EVAL/DFT/SCF/OT.html)、
  [CELL_OPT](https://manual.cp2k.org/trunk/CP2K_INPUT/MOTION/CELL_OPT.html)、
  [PAIR_POTENTIAL](https://manual.cp2k.org/trunk/CP2K_INPUT/FORCE_EVAL/DFT/XC/VDW_POTENTIAL/PAIR_POTENTIAL.html)。
  trunk 文档会变化，实际提交仍应核对所用版本。
