"""Completion != convergence != physical validity. Unknown is never success."""
import re

from .models import OPTIMIZATION_CRITERIA, SCHEMA_VERSION


def _last_criteria(segment):
    for opt in reversed(segment.optimization_steps):
        criteria = {}
        for name in OPTIMIZATION_CRITERIA:
            criterion = getattr(opt, name)
            if criterion is not None:
                criteria[name] = {key: getattr(criterion, key) for key in ("value", "limit", "unit", "converged")}
        if criteria:
            return {"step": opt.step, "all_cartesian_converged": opt.all_cartesian_converged,
                    "all_observed_converged": opt.all_observed_converged, "criteria": criteria}
    return None


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
        if segment.energies and segment.energies[-1].scf_association == "ambiguous":
            reasons.append("Final observed energy has multiple preceding SCF summaries")
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
        last_criteria = _last_criteria(segment)
        if segment.unparsed_optimization_records:
            reasons.append("Unsupported or malformed optimization criteria record in segment")
        contradicted = (needs_geometry and segment.geometry_converged is True and last_criteria is not None
                        and last_criteria["all_observed_converged"] is False)
        if contradicted:
            reasons.append("Observed optimization criteria are not converged despite completion marker")
        if not supported:
            reasons.append("Run type is unknown or outside the v0.1 quality rules")
        if fatal:
            reasons.append("Error/abort diagnostics present")
        status = "passed" if not reasons else ("failed" if fatal or earlier_scf_failure or segment.scf_converged is False
                    or segment.geometry_converged is False or contradicted else "incomplete_or_unknown")
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
            "evidence": [e.__dict__ for e in segment.evidence + segment.diagnostics
                         + segment.unparsed_energy_records + segment.unparsed_optimization_records],
            "optimization_step_count": len(segment.optimization_steps),
            "last_optimization_criteria": last_criteria,
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
