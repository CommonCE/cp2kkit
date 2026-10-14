# 变更记录

软件版本与数据 schema 分开维护。本文件记录实际实现变化，不代表已经发布到软件包仓库，
也不代表完成真实 CP2K 运行认证。

版本规则为 **A.B.C**：A 仅由用户人工决定；新增/更新功能递增 B 并将 C 归零；
修复功能/bug 递增 C，A/B 不变。同一轮同时包含功能更新与修复时统一递增 B。

## 0.2.0

### 新增

- `cp2kkit` 默认进入应用主菜单；`cp2kkit STRUCTURE` 加载结构后进入主菜单。
  支持选择/更换文件、输入生成、extXYZ 导出和 CP2K 输出质量报告。
- 标准库结构读取扩展：Cartesian GJF/COM、CIF、VASP5 POSCAR/CONTCAR，
  以及 `.vasp` / `.poscar` 文件；保留已有 XYZ/extXYZ/restart 支持。
- diag + smearing 且未显式指定空轨道时，根据原子数自动设置
  `ADDED_MOS = max(30, NINT(原子数/2))`；UKS 分别写入 alpha/beta 数量。
- 可配置 OT 外层上限 `--max-outer-scf`，默认 20。
- `.agents/prompts/update-version-docs.md`：新增功能完成后统一更新版本与文档的提示词，
  已接入通用开发约束、功能实现及 Multiwfn 参考模板；遵循用户规定的 A.B.C 升版规则。

### 默认值与交互变化

- PROJECT 默认由固定 `cp2kkit` 改为结构文件名去后缀；可显式覆盖。
- CUTOFF / REL_CUTOFF 从 350/50 Ry 改为 **400/55 Ry**。
- 默认 OT 内外 SCF 上限为 **25/20**；对角化默认上限仍为 128。
- 空轨道从固定默认 20 改为自动值：diag + 展宽采用上述公式，否则默认 0。
- 外压仅 CELL_OPT 显示；孤立盒子 padding 仅有效周期性 NONE 显示。
  OT 隐藏展宽与空轨道；显式请求展宽或非零空轨道会报错，不再静默忽略空轨道。

### 迁移与限制

- 原有批处理子命令保留；默认应用菜单要求 TTY，脚本应继续使用子命令。
- 需要复现旧网格/项目名时显式传入 `--cutoff 350 --rel-cutoff 50 --project cp2kkit`；
  OT 旧内层上限可显式指定 `--max-scf 128`。旧 diag 空轨道可指定 `--added-mos 20`；
  不要给 OT 传入非零空轨道。
- GJF 电荷/多重度、POSCAR 约束等只记录来源，不继承为 CP2K 计算设置。
  CIF 要求显式对称操作或明确 P1；部分占据/无序、旧式缺元素 POSCAR、GJF 内坐标等拒绝。
- 空轨道公式是 Multiwfn 通常用于 300 K 展宽的经验规则，不保证所有体系/温度充分。
- 软件版本升为 **0.2.0**；数据 schema 保持 **0.1.0**，目标 CP2K 默认仍为 2026.2。
- 完整回归 128 项通过，无跳过；compileall、`git diff --check` 与 CLI 版本检查通过。
  版本一致性测试覆盖项目元数据、模块、README/变更记录、CLI 与生成器。
- 未运行 CP2K/Multiwfn 计算；回归使用合成格式样例，真实软件认证和参数收敛仍待验证。
