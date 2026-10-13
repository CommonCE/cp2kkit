# cp2kkit

连接 CP2K 结果读取与可追溯后处理的 Python 工具。根据
[`cp2kkit-mvp.md`](cp2kkit-mvp.md) 开发的 **v0.1 初步实现**，不是已完成真实版本认证的生产发布。

- 默认只读，不提交或运行 CP2K，不改输入、restart 或原始输出。
- 六项 MVP 已有实现入口；暂缓功能不纳入本次开发。
- 核心仅使用 Python 标准库；绘图可选依赖 Matplotlib。
- 输出带 schema、单位、文件 SHA-256、行号与原文；缺失值不等同于零。
- 任何已有目标文件都拒绝覆盖，包括派生 CSV、JSON 和图片。
- 能量数值可以从失败任务提取，但不自动成为有效结果。

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

## CLI

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

未提供 `--output` 时，discover / parse / report 向 stdout 写机器可读数据，
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
- 输入按 UTF-8 严格读取；当前读取全文件，超大输出的流式解析为后续优化项。

## 测试

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m compileall -q src tests
```

测试不执行量化计算、不需要 pytest；Matplotlib 缺失时仅跳过绘图测试。
详见 [架构](docs/architecture.md)、[schema](docs/schema.md)、
[开发路线](docs/roadmap.md) 与 [样例来源](tests/fixtures/README.md)。
