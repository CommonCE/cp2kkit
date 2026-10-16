"""Shared protected structure export and stable long-form CSV with provenance."""
import csv
import json
from contextlib import ExitStack
from pathlib import Path

from .errors import KitError
from .io import json_text, new_file
from .structure import xyz_text
from .models import SCHEMA_VERSION
from .quality import quality_report

FIELDS = ["schema_version", "software", "software_version", "project", "source_path", "source_sha256",
          "segment", "run_type", "segment_status", "energy_usable", "scf_converged", "settings_json",
          "record", "index", "step", "value", "unit", "source_line", "source_text"]


def data_rows(run):
    reports = {r["segment"]: r for r in quality_report(run)["segments"]}
    for segment in run.segments:
        for record, quantities in (
            ("energy", [(e.index, e.step, e.quantity) for e in segment.energies]),
            ("scf_iterations", [(i, None, q) for i, q in enumerate(segment.scf_iterations, 1)]),
        ):
            for index, step, quantity in quantities:
                yield {
                    "schema_version": SCHEMA_VERSION, "software": run.software,
                    "software_version": segment.settings.get("software_version", {}).get("value", ""),
                    "project": run.project or "", "source_path": run.source["path"],
                    "source_sha256": run.source["sha256"], "segment": segment.id,
                    "run_type": segment.run_type or "", "segment_status": reports[segment.id]["status"],
                    "energy_usable": reports[segment.id]["energy_usable"] if record == "energy" else "",
                    "scf_converged": ("" if segment.energies[index-1].scf_converged is None
                                      else segment.energies[index-1].scf_converged) if record == "energy" else "",
                    "settings_json": json.dumps(segment.settings, sort_keys=True, ensure_ascii=False),
                    "record": record, "index": index, "step": "" if step is None else step,
                    "value": quantity.value, "unit": quantity.unit,
                    "source_line": quantity.source.line, "source_text": quantity.source.text,
                }


def export_structure_files(structure, output, fmt='extxyz', allow_cell_loss=False):
    """Write geometry/sidecar exclusively; CLI and menus share warnings/rollback.

    Returns (output_path, sidecar_path, warnings). The source Structure is unchanged.
    As before, this is exception rollback, not crash-atomic multi-file publication.
    """
    if fmt not in {'extxyz', 'xyz'}:
        raise KitError(f'Unsupported structure export format: {fmt}')
    if fmt == 'xyz' and structure.cell is not None and not allow_cell_loss:
        raise KitError('Plain XYZ loses the cell; use extxyz or explicitly pass --allow-cell-loss')
    warnings = []
    if structure.cell is None:
        warnings.append('Source has no cell: periodicity is unknown, not assumed non-periodic')
    if fmt == 'xyz' and structure.cell is not None:
        warnings.append('Plain XYZ omits cell/PBC; full values retained in provenance JSON')
    output = Path(output)
    sidecar = Path(str(output)+'.json')
    with ExitStack() as stack:
        stream = stack.enter_context(new_file(output))
        manifest = stack.enter_context(new_file(sidecar))
        stream.write(xyz_text(structure, extended=fmt == 'extxyz'))
        manifest.write(json_text({**structure.to_dict(), 'export_format': fmt, 'warnings': warnings}))
    return output, sidecar, warnings


def write_csv(stream, run):
    writer = csv.DictWriter(stream, FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(data_rows(run))
