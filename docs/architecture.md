# cp2kkit v0.1 架构

## 设计原则

分析 MVP 以 `cp2kkit-mvp.md` 为原始范围依据；根据后续需求额外加入
[输入生成](input-generation.md) 子集。不建设提交系统，不开展 Bader/PDOS/NEB 等暂缓模块。

1. **只读源文件**：分析函数不运行外部计算、不写回源文件。
2. **数据与判断分离**：解析事实、质量规则、显示/导出各自独立。
3. **证据优先**：来源绝对路径、SHA-256、字节数、行号与原文可追查。
4. **保守判定**：null 为未知；未知、失败、截断不能成为 passed。
5. **不隐式选项目或拼重启**：候选按名称排序，不按时间/大小猜测。
6. **非破坏性输出**：独占创建；多文件导出失败时撤销本次新建文件。
7. **最少依赖**：核心为标准库；绘图依赖隔离，不要求 ASE。

## 模块和依赖方向

```text
cli.py
 ├─ discovery.py ── io.py / errors.py
 ├─ parser.py ───── models.py / io.py
 ├─ quality.py ──── models.py（解析事实 → 规则判定）
 ├─ export.py ───── models.py / quality.py（CSV）
 ├─ structure.py ── models.py / io.py（独立结构通道）
 ├─ plot.py ─────── export.py / quality.py / 可选 matplotlib
 └─ inputgen.py ─── structure.py / models.py / io.py（纯生成 + 独占写入）

models.py  数据结构与 schema 版本
io.py      严格读取、哈希、稳定 JSON、独占输出
errors.py  领域异常与机器可读退出码
__main__.py / pyproject.toml  Python 模块与 console script 入口
```

采用常规 `src/` 布局。暂不引入插件、数据库、工作流引擎或配置框架，
避免初期复杂度大于 MVP 价值。

## 结果通道

```text
输出文件/目录 → 确定选择文件 → 逐行格式匹配 → Run/Segment/Quantity/Evidence
                                                   ├→ quality_report
                                                   ├→ JSON / 长表 CSV
                                                   └→ PNG + 同源 CSV + manifest
```

- Segment 以启动标记和不递增的优化/MD 步号分割。
- 能量记录保留独立 record index 与可为空的计算 step。
- 每个能量关联前面的 SCF 汇总；不会把前一步的 SCF 成功复用给后一步。
- 任一历史 SCF 失败保留为失败证据，即便之后恢复也不能静默洗成成功。
- 不推断进程返回码，不从总能量反推电荷或自旋。
- 原始设置以字符串保留；标准化语义/跨输入合并为后续工作。

质量 positive rules：正常结束 + 最后电子收敛 + 最后能量关联的 SCF 收敛 +
存在总能量 + 支持的 run type + 无错误/历史 SCF 失败；
GEO_OPT / CELL_OPT 还必须有几何成功证据。
“最大优化步数”失败标记优先于通用几何结束标记。

## 结构通道

```text
XYZ/extXYZ/restart → Structure（angstrom + cell + PBC + source）
                         ├→ extXYZ（优先，保留晶胞）
                         └→ 普通 XYZ（有晶胞时要求显式许可）
两种导出均生成完整结构 JSON sidecar
```

支持三矢量或 ABC/ALPHA_BETA_GAMMA 晶胞、UNIT、SCALED 与 KIND/ELEMENT 映射；
不猜测种类标签，不截断损坏的最后一帧，也不展开 CP2K 预处理。

## 输入生成通道

```text
XYZ/extXYZ/restart → Structure + InputSettings → 校验 → CP2K 文本 + manifest
                                                      → 新 .inp / .inp.json
```

生成器不继承原输入计算设置；未知 PBC、电子数/多重度冲突、不支持的组合均拒绝。
元素预设显式匹配基组与赝势价电子数，可读取本地 CP2K data 核对名字与哈希。
不执行外部计算，不依赖 Multiwfn 程序或相邻源码路径。

## 安全与可复现性

- 不记录运行当前时间，保证同一输入在同一路径的 JSON/CSV 结果一致。
- 哈希针对原始文件字节；移动文件会改变来源路径，内容哈希保持不变。
- 行号为 1-based，片段为 0-based，能量与 SCF record index 为 1-based。
- 图片 manifest 记录 PNG/CSV 哈希、坐标轴标签、原始解析结果和质量报告。
- 多文件写入有异常回滚，但不承诺机器断电时的事务原子性；不覆盖仍是硬保证。
- schema 变更须同步文档与测试；不引入大二进制样例或昂贵计算输出。

## 验证策略

标准库 unittest：正常/截断/未收敛、零值、科学记数、能量来源、
多项目/重复输出、重启片段、晶胞/PBC 回读、单位转换、损坏输入、
覆盖保护、sidecar 碰撞回滚与绘图数据对应。

当前证据级别为**合成格式测试通过**。真实 CP2K 文件版本矩阵是发布前提，
不可把测试 fixture 的版本字符串当成兼容认证。
