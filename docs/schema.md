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
