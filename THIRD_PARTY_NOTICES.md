# 第三方来源与授权说明

本文件汇总 cp2kkit 使用或参考的第三方材料。它不是整个项目的许可证，
不向使用者授予超出上游授权的额外权利，也不证明许可证兼容性已得到确认。
后续参考新实现时，应同时登记模块来源，而不是只在这里追加软件名称。

## Multiwfn

### 上游信息

- 软件：Multiwfn
- 作者：Tian Lu
- 官网：http://sobereva.com/multiwfn/
- 官方自定义条款：http://sobereva.com/multiwfn/download.html

### 使用范围与来源

部分 cp2kkit 模块参考 Multiwfn 的实现开发，涉及内容可包括程序组织、
数值流程、参数表、默认设置或改写的代码。具体使用内容应逐模块如实登记。

- [条款记录](third_party/multiwfn/TERMS.md)：核对时的官方条款原文摘录、来源及日期。
- [模块来源登记](third_party/multiwfn/PROVENANCE.md)：本地模块、上游版本/文件/子程序、
  源文件哈希、使用内容、实现差异与授权状态；附后续登记模板。

当前登记的模块为 `src/cp2kkit/inputgen.py`（CP2K 输入生成）。
不分发原 Fortran 文件、不依赖 Multiwfn 二进制，并不等同于严格净室实现，
也不能据此断定不受上游条件约束。

### 授权状态

Multiwfn 发布自定义条款，而不是 MIT/BSD/GPL 许可证。
条款原文见上述记录；发布前应核对其是否更新。

本项目未取得作者针对本次集成的单独授权。除非来源登记明确记录了已取得的许可，
否则不得假定再许可、收费分发或与其他许可证组合的边界已经得到确认。
引用和来源说明不能替代必要的授权，也不能用本项目未来选定的许可证覆盖上游条件。

若参考的 Multiwfn 文件包含其他作者的代码，应另行核对、登记并保留其版权及授权声明，
不能一律归入 Multiwfn 自定义条款。

### 官方条款要求保留的论文引用

1. Tian Lu, Feiwu Chen, **Multiwfn: A multifunctional wavefunction analyzer**,
   *Journal of Computational Chemistry*, **33**, 580–592 (2012).
   DOI: https://doi.org/10.1002/jcc.22885
2. Tian Lu, **A comprehensive electron wavefunction analysis toolbox for chemists, Multiwfn**,
   *Journal of Chemical Physics*, **161**, 082503 (2024).
   DOI: https://doi.org/10.1063/5.0216272

当前输入生成模块及其生成的输入/JSON 中保留了这两篇引用。
相关研究使用时应按官方条款在论文正文恰当引用；代码中的引用不能替代论文中的引用。
不同功能若有额外方法论文或上游要求，应在相应来源登记中补充。

## CP2K 输入规范和数据文件

生成器根据 CP2K 官方输入参考和数据库头行核对关键字、节层级与基组/赝势名字，
来源见 [输入生成文档](docs/input-generation.md)。
仓库不包含 CP2K 基组系数、赝势参数或 dftd3.dat 副本。
用户提供的 `--data-dir` 文件仅只读检查并记录哈希；实际使用与分发这些文件应遵守其适用条款。
