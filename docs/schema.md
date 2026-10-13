# 交换格式 v0.1.0

所有 JSON 顶层包含 `schema_version: "0.1.0"`。
数值不允许 NaN/Infinity；JSON 未知值使用 `null`，CSV 使用空字段，零保留为零。

## Parse JSON

- `software`、`software_version`、`project`：来自输出；缺失版本/项目为 null。
- `source`：path（绝对路径）、sha256、size_bytes。
- `exit_status`：null；本版没有调度器/进程元数据。
- `segments`：按文件中的顺序，id 从 0 起。
- `parser_warnings`：未支持格式、片段/缺失证据告警。
- `settings`：顶层预留；当前设置保存在各 segment，不隐式跨片段合并。
- CLI parse 额外嵌入 `quality`，与 report 同结构。

Segment 含 started/completed、scf_converged、geometry_converged、
run_type、evidence、diagnostics、settings、energies、scf_iterations、
final_energy、wall_time、unparsed_energy_records（不支持/损坏的能量行证据）。
final_energy 是最后一个成功解析的能量；若有未解析能量行，它不代表可靠的最终结果，
对应片段 energy_usable=false。

Quantity 格式：

```json
{
  "value": -12.3,
  "unit": "hartree",
  "source": {
    "path": "/absolute/path/run.out",
    "line": 10,
    "text": "original source line"
  }
}
```

Energy：segment、index、step（可空）、quantity、scf_converged（本条能量关联的状态）。
SCF 汇总次数单位为 iteration；wall_time 为 s；结构及晶胞为 angstrom。
settings 值为原文字符串，带 source 和可空 unit，不自动数值化未知语义。

## CSV

长表记录类型为 `energy` 和 `scf_iterations`；不把缺失数据虚构成行。

字段：
`schema_version, software, software_version, project, source_path, source_sha256,
segment, run_type, segment_status, energy_usable, scf_converged, settings_json,
record, index, step, value, unit, source_line, source_text`。

`energy_usable` 是该片段保守质量判定；它不是物理合理性认证。
SCF 次数行的 energy_usable 和 scf_converged 为空。
`settings_json` 为有序 JSON 字符串，保留该片段已解析设置与证据。
`step` 缺失时用 index 绘图；index 不是累计 MD 时间。

## Quality JSON

顶层 status：passed 或 not_passed。
片段 status：passed / failed / incomplete_or_unknown。
电子收敛与几何收敛独立，ENERGY 的 geometry_converged 可以为 null，
通过 geometry_required=false 表示该规则不要求几何优化。

包含 reasons、energy_usable、证据数组、原始来源和限制说明。
命令执行成功退出码与计算质量状态相互独立。

## Structure JSON

symbols、positions、cell（3×3 行矢量或 null）、pbc（三布尔值或 null）、
coordinate_unit、cell_unit、atom_count、source、frame。
XYZ 的 frame 从 0 起，restart 为 null。
source 对 XYZ 额外包含所选帧的 line_start / line_end。
导出 sidecar 增加 export_format 和 warnings。
不存在晶胞时 pbc=null，不将未知解释为非周期。

## Plot manifest

source、kind、x_label、y_label、segments_connected=false、
data/path/sha256、image/path/sha256、run、quality。
CSV 包含所有两类记录；kind 指示图片实际使用的子集。
每个片段独立绘制，禁止跨片段画连接线。

## Generated input JSON：密度输出扩展

本阶段在 schema 0.1.0 中增加新通道与可选/新增字段，不改变既有结果模型的含义。

- `target_version` / `settings.cp2k_version`：明确请求的 CP2K 语法目标，默认 2026.2。
  `runtime_version=null` / `runtime_validated=false`：未实际运行，不将目标版本当执行版本。
- `settings.electron_density` / `spin_density` / `cube_stride`：原始请求；stride 未请求时为 null。
- `density_output`：有效设置。`enabled`、`electron_density`、`spin_density`；UKS 下后两者同时为 true。
  `stride`（三正整数）、`each`（QS_SCF/JUST_ENERGY/GEO_OPT/CELL_OPT）、`add_last`、`append`、
  `filename_override`。未启用时 stride/each/add_last 为 null，不增加 PRINT。
- `density_meaning`：GPW pseudopotential valence electron density；`spin_convention`：alpha minus beta。
- `spatial_unit=bohr`、`scalar_unit=e/bohr^3`、`stride_unit=grid index increment`。
- `reference_version`、`source`（版本固定官方源码 URL）、`definition_sha256`、`manual_source`：
  语法定义文件与核对来源；2024.3 手册对应地址不存在，manual_source 为 null，使用已核对的版本源码。
- `syntax_reference_checked`、`runtime_validated`：密度输出语法核对范围及实际验证边界；
  不是整个生成器兼容认证。

## Cube check JSON

- `schema_version`、`source`（绝对路径、原始字节 sha256、size_bytes）。
- `comments`：两行注释；`atom_count`、`atoms`（index 为 1-based 序号，atomic_number、atom_field、position）。
  atom_field 只保存数值，不推断实际赝势或价电子数；允许零。
- `origin`、`shape`（正维度）、`signed_counts`（原始符号）、`vectors`（三行步进矢量）。
  头部坐标保持文件数值，用 `length_unit` 解释，不隐式标准化到 angstrom。
- `sample_span_vectors=(N-1)*v`、`quadrature_span_vectors=N*v`；不是由原子包围盒计算的模拟晶胞。
- `voxel_volume`：value 为 abs(det(vectors))，unit 为对应空间单位的三次方。
- `dialect`、`length_unit`（不确定时 null）、`scalar_type`、`scalar_unit`、`interpretation`。
  scalar_type/unit 的 `unknown` 是显式枚举状态，不是数值零；它不证明标量是密度。
  `interpretation` 包含请求参数、人工断言前推断、空间/标量依据。
- `expected_value_count`、`traversal`（X outer, Y middle, Z inner）、`statistics`、`warnings`、`supported_format`。
- `validation.format_valid=true` 仅在完整读取/核对后给出；
  calculation_settings_verified / real_cp2k_runtime_validated 为 false。

statistics 含 `value_count`、minimum、maximum、sum、sum_unit、integral、positive_integral、negative_integral。
积分字段为 value、unit、quantity、convention；负部分保留负号。
已知电子数密度与兼容单位时 quantity 为 electron_number、unit 为 electron；
自旋则 quantity 为 spin_excess_electrons，不直接转换磁矩。
未知标量或空间单位时 quantity 为 raw_numerical_integral，unit 描述原始标量乘空间体积。
统一采用 Σf × abs(det(step vectors))，无额外端点权重、归一化或数据修正。
损坏/不支持文件以既有 CLI 错误机制退出，不生成 format_valid=true 的 JSON。

## Cube difference JSON sidecar

- `operation=density_difference`、`expression`（rho[0] 减去其余）、`expression_sources`（有序路径）。
- `inputs`：按运算顺序保存各 Cube check 报告，含独立哈希、原子表、网格/单位和积分。
- `output`：路径、sha256、size_bytes、electron-density-difference 或 spin-density-difference 类型，
  scalar_unit、length_unit、shape、origin、vectors、atoms_from=rho[0]、atom_fields_preserved=true。
- `canonical_grid`：比较时规范化的 bohr 网格；实际输出仍沿用 AB 的数值网格/单位。
- `tolerances`：grid_atol_bohr、grid_rtol、nonzero_integral_warning_electrons。
- `grid_deviations`：每个片段原点/矢量最大组件偏差与远端样本位置偏差保守上界。
  `max_grid_component_deviation_bohr`：所有原点/步进矢量组件的最大偏差。
- `density_conversion_factors_to_output_unit`：各输入标量转换至 AB 标量单位的因子。
- `statistics`：输出差分的范围、总和、积分及正负部分积分。
- `generator`、`warnings`、`validation`：生成器版本、物理/数值限制及未验证计算设置/运行的状态。

cube 注释写入本工具的类型、空间/标量单位及遍历顺序，允许独立回读，不能据此宣称原计算参数已认证。
完整格式/单位策略与流程见 [cube 文档](cube.md)。
