# 密度 cube 输出、检查与密度差

本阶段只实现输入生成、标量 cube 检查和已对齐网格的相减，不运行 CP2K。
不提供 Bader、插值、配准、网格重排、平面平均、DOS/能带或作业提交。

## 1. 先定义可比较的物理参考

密度差定义为 `Δρ = ρAB − Σρfragment`，第一个文件是复合体系，其余均减去。
总电子密度差和自旋密度差是不同物理量，禁止混合相减。

- AB 与各片段应具有一致晶胞、原点、采样网格及可比较的计算设置。
- 分析结合导致的电子重排时，片段保留其在 AB 中的构型；单独优化片段的密度相减
  会额外包含几何变化贡献。优化 AB 后优先做最终固定构型的 AB/片段单点。
- 保持泛函、赝势、基组策略、网格精度、k 点及适用占据/展宽设置一致；
  相同 STRIDE 不保证网格相同，必须检查实际 cube。
- 片段电荷和自旋必须对应物理合理的参考态。总电子数守恒需要相应参考电荷组合；
  自旋密度还涉及一致的自旋定义/量子化方向和合理的片段自旋态。
- GPW 的局域基组随原子组成改变：使用片段自身基组还是借助 ghost atoms 保留 AB 基组，
  会影响可比性和基组误差。应明确策略；本版不自动添加 ghost atoms，也不声称所有分析必须使用它们。
- 程序可验证格式、数值与网格，**通常不能仅凭 cube 验证上述计算设置或参考态**。

电子密度差正值代表相对于选定片段参考的电子积累，负值代表耗减；
不直接等于某个原子的电荷变化。全空间积分、正负部分积分均不能直接称为片段净电荷转移量。
总密度输出是电子数密度而非带负号的电子电荷密度；自旋密度为 `ρα − ρβ`。

## 2. generate-input 密度输出

```bash
export PYTHONPATH="$PWD/src"
python -m cp2kkit generate-input AB.extxyz -o AB.inp --project AB \
  --cp2k-version 2026.2 --run-type ENERGY --electron-density --cube-stride 1 1 1

# 示例假定体系电荷 +1、二重态确实合理；不自动修改电荷/多重度
python -m cp2kkit generate-input radical.extxyz -o radical.inp --project radical \
  --charge 1 --multiplicity 2 --spin-density --cube-stride 1 1 1

# 老版本的共同 GPW 密度输出语法
python -m cp2kkit generate-input AB.extxyz -o AB-2024.inp --project AB2024 \
  --cp2k-version 2024.1 --electron-density
```

`--cp2k-version` 默认 2026.2，允许 2024.1、2024.2、2024.3、2025.1、2025.2、2026.1、2026.2。
这是已核对的**密度输出语法配置**和目标版本记录，不是整个生成器/解析器的真实运行认证。
更老或更新版本暂不加入该选择范围。cube 格式读取本身不需要版本号。

`--electron-density` 或 `--spin-density` 启用：

```text
&FORCE_EVAL
  &DFT
    ...
    &PRINT
      &E_DENSITY_CUBE ON
        STRIDE 1 1 1
        APPEND F
        ADD_LAST NUMERIC
        &EACH
          QS_SCF 0
          JUST_ENERGY 1
          GEO_OPT 0
          CELL_OPT 0
        &END EACH
      &END E_DENSITY_CUBE
    &END PRINT
  &END DFT
&END FORCE_EVAL
```

- 未请求时不增加密度 PRINT 节，原来的默认输入行为不变。
- CP2K `E_DENSITY_CUBE` 在 UKS 下同时写电子与自旋密度，没有本功能使用的独立
  `SPIN_DENSITY_CUBE` 开关。`--spin-density` 必须满足当前生成器的 UKS 条件
  （multiplicity > 1），否则报错，不悄悄改变磁态。
- UKS 下仅请求电子密度也会产生自旋 cube；仅请求自旋也会产生电子 cube。
  JSON 的 `settings` 保存请求，`density_output` 保存实际有效输出。
- ENERGY/ENERGY_FORCE：`JUST_ENERGY 1` 输出单点结果。GEO_OPT/CELL_OPT：常规步频为 0，
  `ADD_LAST NUMERIC` 请求被程序识别的最终步；SCF 常规步频也为 0。
  官方指出并非每个迭代层都能及时识别最后一步，因此不能保证异常终止也写出最终 cube。
  最后一步不意味着收敛；必须检查任务输出。用于相减时推荐固定构型的 ENERGY 单点。
- 不覆盖 `FILENAME`，保留项目名、ELECTRON_DENSITY/SPIN_DENSITY 中间名及迭代编号/扩展名；
  实际文件名查看 CP2K 日志。避免 `=filename` 导致不同输出碰撞；`APPEND F` 避免多帧追加。
  cp2kkit 的覆盖保护仅约束自己的写入，不能保证将来 CP2K 在旧运行目录中不覆盖文件。
- STRIDE 必须三个正整数；密度开启时有效默认值为 1 1 1，无密度开关时单独指定报错。
  更大 stride 减少采样，可能降低积分和后处理精度；1 1 1 也不是收敛认证。
- 当前 GPW/GTH 输出为**赝势显式价电子密度**，不包含所有核电子，不等同全电子密度。
  GAPW 的硬/软密度选项在旧版本有 `TOTAL_DENSITY`、新版本有 `DENSITY_INCLUDE` 的差异；
  本阶段不启用 GAPW 或这些分支，也不使用 `TOT_DENSITY_CUBE` 代替电子数密度。
- JSON 记录有效 stride/频率/单位/自旋约定、目标版本、版本固定语法定义源码 URL/哈希、
  手册来源和未运行验证状态。2024.3 的独立手册对应地址不存在，manual_source 为 null，
  使用已核对的 v2024.3 源码定义（该文件内容与 v2024.2 一致）。

## 3. cube-check

```bash
python -m cp2kkit cube-check AB.cube
python -m cp2kkit cube-check AB.cube -o AB-check.json

# 一般 cube 只有结构/网格，不能仅凭注释含 density 或文件名推断标量语义
python -m cp2kkit cube-check generic.cube --scalar-type electron-density \
  --scalar-unit 'e/bohr^3' -o generic-check.json

# 显式采用负计数表示 angstrom 的约定，不误用 Gaussian cubegen 的输入单位规则
python -m cp2kkit cube-check signed.cube --dialect signed \
  --scalar-type electron-density --scalar-unit 'e/angstrom^3'
```

报告注释、原子数/1-based 序号/原子序数/原子字段/坐标、原点、维度、步进矢量、采样与求积跨度、
数值数量、最小/最大/总和、体积元、积分及正负部分积分，附完整源文件字节 SHA-256 和解释依据。
原子字段原样保留为 `atom_field`；可能为零，**不据此猜赝势价电子数或判定损坏**。
非法文件退出 4，诊断写 stderr，不生成“成功检查”JSON；缺失路径/参数问题退出 2。
JSON 目标存在时拒绝覆盖，退出 5。

### 支持格式和单位策略

- UTF-8 格式化单标量 CUBE：NATOMS >= 0，NVAL 缺省或 1；每点一个数。
- 支持空原子表、负标量、E/e/D/d 指数、非正交/左手网格。
- 三维计数须全正或全负，不能为零；矩阵不能退化/近共线。
- 标准遍历：X 外层、Y 中层、Z 最快；显式声明其他顺序的文件拒绝，不自动重排。
- 拒绝负 NATOMS/轨道 cube、多数据集/矢量、多帧追加、截断、多余数据、NaN/Inf、
  不合法原子/网格字段、数值溢出、单行超过 1 MiB、非文本/其他格式。
- 逐行迭代、每行限长、补偿求和；不保存全文件文本、全网格词元或浮点数组。
  同时保留的主要是原子/网格头部，以及每个输入的一行。文件读取期间发生可检测的修改会拒绝。

| 解释模式 | 空间单位 | 标量含义/单位 |
|---|---|---|
| auto，首行精确 `-Quickstep-` | 正计数 bohr；负计数拒绝 | 仅识别 ELECTRON/SPIN DENSITY 及 TOTAL 前缀的已核对标题，e/bohr³ |
| cp2k（显式生产者断言） | 正计数 bohr | 同上；其他标题保留 unknown |
| gaussian | 正计数 bohr | 不猜 scalar；需要人工声明 |
| signed（显式选择） | 正计数 bohr，负计数 angstrom | 空间符号不能确定密度单位，仍需声明 |
| auto，一般正计数 | 标准空间约定 bohr | unknown，除非人工声明 |
| auto，一般负计数 | null/不确定 | 原始数值积分，需显式空间解释才可相减 |
| cp2kkit 差分输出 | 读取本工具写入的明确元数据 | 电子/自旋密度差及单位由元数据记录 |

`--length-unit` 是人工**单位断言**，不是请求改变文件坐标；若与已选生产者/约定冲突则报错。
`--scalar-type` 与 `--scalar-unit` 同理，不得覆盖已识别的相反密度类型/单位。
人工声明记录在 JSON 的 `interpretation.requested`，程序不替用户证明声明成立。
CP2K 格式身份与密度标题也不能证明其实际方法为 GPW 或密度包含全部核电子。
未知量积分标为 `raw_numerical_integral`，不会称为电子数。

### 积分约定

```text
I = Σ f(i,j,k) × abs(det(v1,v2,v3))
```

体积元来自三个**网格步进矢量**的行列式，不是三个长度的乘积；
不使用原子包围盒，不把单步矢量当成晶胞。
`sample_span_vectors` 为 `(N−1)*v`，`quadrature_span_vectors` 为 `N*v`；
这描述采样/求积区域，不证明模拟晶胞。
每个点一份完整体积权重，不额外重复周期端点、不做梯形端点权重或归一化。

明确为电子数密度及其差分、且空间/密度单位已知时，先匹配 bohr/angstrom 体积后报告电子数；
自旋密度积分为 alpha-minus-beta 的电子数差，不自动当作磁矩。
其余报告原始 `Σf × 原始体积元`。负部分积分保留负号。

CP2K cube 网格矢量和数值有文本舍入；粗 STRIDE 可能遗漏密度细节，
原网格维度不能整除 stride 时，输出计数的向上取整还可能改变名义求积跨度。
因此离散积分偏差不等于 SCF 失败或电子数发生物理变化。

## 4. cube-diff

```bash
python -m cp2kkit cube-diff AB.cube A.cube B.cube -o delta-density.cube
python -m cp2kkit cube-diff AB.cube A.cube B.cube C.cube -o delta-many.cube
python -m cp2kkit cube-diff AB-spin.cube A-spin.cube B-spin.cube \
  --scalar-type spin-density -o delta-spin.cube

# 显式确认的一般 cube
python -m cp2kkit cube-diff generic-AB.cube generic-A.cube generic-B.cube \
  --scalar-type electron-density --scalar-unit 'e/bohr^3' -o delta-generic.cube
```

至少两个输入。相减前必须维度相同、已知的电子密度或自旋密度类型相同、单位可比较。
未知空间/密度单位、未知类型或电子/自旋混合拒绝（退出 2），不因原子表不同拒绝。
不允许把已经是密度差的文件当原始片段密度再次相减。

网格先规范到 bohr，按组件比较：
`abs(a−b) <= grid_atol + grid_rtol*max(abs(a),abs(b))`。
默认 `--grid-atol 1e-6` bohr、`--grid-rtol 0`；记录每个片段原点/矢量最大偏差、
最大组件偏差及远端采样位置偏差的保守上界。大网格的微小步进差可能累计，需人工评估。
不移动、插值、配准或重排数据；仅允许经明确单位解释的数值转换。

不同单位的一般 cube 可采用共同 signed 约定，或按输入顺序声明：

```bash
python -m cp2kkit cube-diff AB-bohr.cube A-angstrom.cube B-bohr.cube \
  --scalar-type electron-density --input-length-units bohr angstrom bohr \
  --input-scalar-units 'e/bohr^3' 'e/angstrom^3' 'e/bohr^3' -o delta-units.cube
```

逐文件参数数量须等于输入数。断言不能与已识别生产者冲突；不用于强行让实际不同网格相同。

输出沿用 AB 原点/网格/空间和标量单位，原子记录行保持不变，评论明确是密度差并记录单位。
`<output>.json` 记录表达式、输入顺序/哈希、网格比较/容差、单位换算因子、各输入积分、
差分积分、正负积分及警告；输出哈希对应实际写入字节。
当差分积分绝对值大于 `--integral-atol`（默认 1e-3 电子）时给解释性告警：
可能来自电荷/自旋参考、设置差异、盒子尾部、stride/离散采样。不会自动归一化，也不会仅据此判定计算失败。

所有目标先预检（含悬空符号链接），同目录临时文件完成写入后用独占硬链接发布。
冲突退出 5；写入/发布失败清理本次临时文件和仍属于本次写入的输出，不删除已有用户文件。
要求文件系统支持硬链接；不承诺断电时双文件事务原子性。

## 5. AB/A/B 使用流程（不自动构建或运行计算）

假定用户已准备 `AB.extxyz`、`A-in-AB.extxyz`、`B-in-AB.extxyz`：
三者带相同晶胞/PBC，片段采用 AB 中构型；以下示例仅适用于三个参考态确实均为中性单重态。
其他情况应明确修改电荷/多重度，金属体系还需合理设置对角化、k 点/展宽和空轨道数。

```bash
export PYTHONPATH="$PWD/src"
python -m cp2kkit generate-input AB.extxyz -o AB-density.inp --project AB \
  --run-type ENERGY --functional PBE --charge 0 --multiplicity 1 \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1
python -m cp2kkit generate-input A-in-AB.extxyz -o A-density.inp --project A \
  --run-type ENERGY --functional PBE --charge 0 --multiplicity 1 \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1
python -m cp2kkit generate-input B-in-AB.extxyz -o B-density.inp --project B \
  --run-type ENERGY --functional PBE --charge 0 --multiplicity 1 \
  --cp2k-version 2026.2 --electron-density --cube-stride 1 1 1

# 用户自行审核并在独立新目录完成三次计算；此处没有运行或提交命令。
# 以下变量明确指向日志中确认的最终电子密度文件，不用模糊 glob 选多个迭代结果。
AB_CUBE=/path/to/AB/ELECTRON_DENSITY.cube
A_CUBE=/path/to/A/ELECTRON_DENSITY.cube
B_CUBE=/path/to/B/ELECTRON_DENSITY.cube
python -m cp2kkit cube-check "$AB_CUBE" -o AB-cube-check.json
python -m cp2kkit cube-check "$A_CUBE" -o A-cube-check.json
python -m cp2kkit cube-check "$B_CUBE" -o B-cube-check.json
python -m cp2kkit cube-diff "$AB_CUBE" "$A_CUBE" "$B_CUBE" -o delta-density.cube
python -m cp2kkit cube-check delta-density.cube -o delta-cube-check.json
```

实际文件名通常含项目/迭代编号，不是示例路径中的通用名字；必须替换为实际文件。

## 6. 来源与验证等级

- 手册：[2026.2 E_DENSITY_CUBE](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/PRINT/E_DENSITY_CUBE.html)、
  [EACH](https://manual.cp2k.org/cp2k-2026_2-branch/CP2K_INPUT/FORCE_EVAL/DFT/PRINT/E_DENSITY_CUBE/EACH.html)、
  [2024.1 对照](https://manual.cp2k.org/cp2k-2024_1-branch/CP2K_INPUT/FORCE_EVAL/DFT/PRINT/E_DENSITY_CUBE.html)。
- 版本固定源码：[CP2K v2026.2](https://github.com/cp2k/cp2k/tree/v2026.2/src)，
  `input_cp2k_print_dft.F`、`input/cp_output_handling.F`、`qs_scf_post_gpw.F`、
  `pw/realspace_grid_cube.F`；另核对 v2024.1/v2026.1 的输出与迭代规则，以及中间版本的输入节定义。
  仅核对接口/格式事实，不复制或分发 CP2K 源码实现。
- 格式：[Gaussian cubegen](https://gaussian.com/cubegen/)（输出单位与输入单位规则不可混淆）、
  [Paul Bourke signed-count 约定](https://paulbourke.net/dataformats/cube/)。
- Multiwfn 参考：2026.10.1 `cp2kmate.f90` 的 E_DENSITY_CUBE/STRIDE 分支；
  来源与引用见 [登记](../third_party/multiwfn/PROVENANCE.md)。频率策略另按 CP2K 文档/源码核对。

官方语法/格式核对、合成回归和实际 CP2K 运行是不同等级。
当前环境未发现 CP2K 可执行程序，未安装或运行；实现前在 `tests/` 与授权 `test-workspace/`
未找到可用真实 cube，因此尚无真实样例回归或 CP2K 运行认证。
合成测试的预期值来自常数场行列式积分及手算差分，不能作为科学计算结果。
