"""Stable long-form CSV: units, nulls, segmentation and provenance."""
import csv
import json
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


def write_csv(stream, run):
    writer = csv.DictWriter(stream, FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(data_rows(run))
