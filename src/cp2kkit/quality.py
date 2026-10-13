"""Completion != convergence != physical validity. Unknown is never success."""
import re

from .models import SCHEMA_VERSION


def quality_report(run):
    reports = []
    for segment in run.segments:
        reasons = []
        fatal = [d for d in segment.diagnostics if re.search(r"\b(?:ERROR|ABORT)\b", d.text, re.I)]
        needs_geometry = segment.run_type in {"GEO_OPT", "CELL_OPT"}
        supported = segment.run_type in {"ENERGY", "ENERGY_FORCE", "GEO_OPT", "CELL_OPT"}
        if not segment.completed:
            reasons.append("Missing normal-termination marker")
        if segment.scf_converged is not True:
            reasons.append("Final electronic convergence is false or unknown")
        if segment.energies and segment.energies[-1].scf_converged is not True:
            reasons.append("Final energy lacks an associated converged SCF cycle")
        # An earlier SCF failure is retained even if a later SCF converges.
        earlier_scf_failure = any(re.search(r"SCF.*(?:NOT converged|did not converge)", e.text, re.I) for e in segment.evidence)
        if earlier_scf_failure:
            reasons.append("Segment contains an unconverged SCF cycle")
        if needs_geometry and segment.geometry_converged is not True:
            reasons.append("Geometry convergence is false or unknown")
        if segment.final_energy is None:
            reasons.append("No supported total-energy record")
        if segment.unparsed_energy_records:
            reasons.append("Unsupported/malformed total-energy record in segment")
        if not supported:
            reasons.append("Run type is unknown or outside the v0.1 quality rules")
        if fatal:
            reasons.append("Error/abort diagnostics present")
        status = "passed" if not reasons else ("failed" if fatal or earlier_scf_failure or segment.scf_converged is False
                    or segment.geometry_converged is False else "incomplete_or_unknown")
        reports.append({
            "segment": segment.id, "status": status, "completed": segment.completed,
            "electronic_converged": segment.scf_converged,
            "geometry_converged": segment.geometry_converged,
            "geometry_required": needs_geometry, "run_type": segment.run_type,
            "settings": segment.settings,
            "wall_time": None if segment.wall_time is None else {
                "value": segment.wall_time.value, "unit": segment.wall_time.unit,
                "source": segment.wall_time.source.__dict__},
            "energy_usable": status == "passed", "reasons": reasons,
            "final_energy": None if segment.final_energy is None else {
                "value": segment.final_energy.value, "unit": segment.final_energy.unit,
                "source": segment.final_energy.source.__dict__},
            "evidence": [e.__dict__ for e in segment.evidence + segment.diagnostics + segment.unparsed_energy_records],
        })
    return {
        "schema_version": SCHEMA_VERSION, "source": run.source,
        "software": run.software, "software_version": run.software_version, "project": run.project,
        "exit_status": run.exit_status,
        "status": "passed" if reports and all(r["status"] == "passed" for r in reports) else "not_passed",
        "segments": reports, "parser_warnings": run.parser_warnings,
        "limitations": [
            "Passed means the supported text checks passed, not physical/chemical validation.",
            "Missing settings, force/stress, wall time and process exit status are not inferred.",
            "Version compatibility is fixture-based; real CP2K version certification is pending.",
        ],
    }
