"""Associate explicit CP2K optimization steps with XYZ frame metadata, read-only."""
import math
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from sys import float_info

from . import __version__
from .errors import AmbiguousProject, KitError, ParseError
from .models import OPTIMIZATION_CRITERIA, SCHEMA_VERSION, Evidence, Run
from .parser import NUMBER, _parse_output_with_ranges, number
from .quality import quality_report
from .structure import Structure, read_xyz_frames

DEFAULT_ENERGY_TOL_HARTREE = 1e-6
_ATOM_COUNT_LINE = re.compile(r"(?:Total number of\s+)?-\s+Atoms(?=$|[^A-Za-z0-9_])(.*)", re.I)
_ATOM_COUNT_VALUE = re.compile(r":\s*([1-9][0-9]*)")


@dataclass
class TrajectoryFrame:
    frame_index: int
    line_start: int
    line_end: int
    comment: str
    trajectory_step: int | None
    trajectory_energy_hartree: float | None
    atom_count: int
    has_cell: bool
    has_pbc: bool
    structure: Structure

    def to_dict(self):
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name != "structure"}


@dataclass
class TrajectoryMatchReport:
    source: dict
    trajectory_source: dict
    segment: int
    segment_id: int
    energy_tol_hartree: float
    requested_step: int | None
    frames: list[TrajectoryFrame]
    matches: list[dict]
    frames_missing_step: list[dict]
    duplicate_trajectory_steps: list[dict]
    unmatched_output_steps: list[dict]
    unmatched_trajectory_frames: list[dict]
    converged_final_step: dict | None
    converged_final_status: str
    converged_final_reasons: list[str]
    strict_passed: bool
    warnings: list[str]
    output_atom_count: int | None = None
    output_atom_count_sources: list[dict] = field(default_factory=list)

    def to_dict(self):
        return {"schema_version": SCHEMA_VERSION, "operation": "trajectory_step_match",
                "parser": {"name": "cp2kkit", "version": __version__},
                **{f.name: getattr(self, f.name) for f in fields(self) if f.name != "frames"},
                "frames": [frame.to_dict() for frame in self.frames]}


# Consume other metadata assignments and quoted values as whole tokens. A quote
# left open consumes the rest of the line rather than exposing apparent metadata.
_QUOTED = r'''(?:"(?:[^"\\]|\\.)*(?:"|$)|'(?:[^'\\]|\\.)*(?:'|$))'''
_COMMENT_TOKEN = re.compile(
    r'''(?<![^\s,])(?P<key>[\w.-]+)\s*=\s*(?P<value>(?![\w.-]+\s*=)(?:'''
    + _QUOTED + r'''|[^\s,"']+)(?=[\s,]|$))?|''' + _QUOTED + r'''|[^\s,"']+'''
)


def parse_trajectory_comment(comment: str, *, source_path: str | Path,
                             line: int) -> tuple[int | None, float | None, list[str]]:
    """Return (explicit step, energy in hartree, warnings) from a raw comment."""
    evidence = Evidence(str(source_path), line, comment)
    values = {"step": None, "energy": None, "time": None}
    seen = set()
    warnings = []
    for match in _COMMENT_TOKEN.finditer(comment):
        key = {"Step": "step", "i": "step", "Energy": "energy", "energy": "energy",
               "E": "energy", "time": "time", "Time": "time"}.get(match["key"])
        if key is None:
            continue
        token = match["value"] or ""
        value = None
        if key == "step":
            if re.fullmatch(r"[+-]?[0-9]+", token):
                try:
                    value = int(token)
                except ValueError:
                    pass
        elif re.fullmatch(NUMBER, token):
            value = number(token, evidence)
        if value is None or key in seen:
            issue = "Duplicate" if key in seen else "Malformed"
            warnings.append(f"{issue} trajectory {key} metadata at {source_path}:{line}")
            value = None
        seen.add(key)
        values[key] = value
    return values["step"], values["energy"], warnings


def _output_steps(segment, tolerance):
    opts = {opt.step: opt for opt in segment.optimization_steps if opt.step is not None}
    energies = defaultdict(list)
    for energy in segment.energies:
        if energy.step is not None:
            energies[energy.step].append(energy.quantity)
    for step in sorted(opts.keys() | energies.keys()):
        records = energies[step]
        opt = opts.get(step)
        value = source = None
        selection = "unavailable"
        if not records:
            if opt is not None and opt.energy_hartree is not None:
                value, source, selection = opt.energy_hartree, opt.energy_source, "opt_summary"
        else:
            values = [q.value for q in records]
            if max(values) - min(values) <= tolerance:
                value, source, selection = records[0].value, records[0].source, "force_eval"
            else:
                selection = "ambiguous"
                if opt is not None and opt.energy_hartree is not None and opt.energy_source is not None:
                    before_opt = [q for q in records if q.source.line < opt.energy_source.line]
                    after_opt = [q for q in records if q.source.line > opt.energy_source.line]
                    post = [opt.energy_hartree, *(q.value for q in after_opt)]
                    if (len(before_opt) > 1
                            and any(abs(q.value - opt.energy_hartree) <= tolerance for q in before_opt)
                            and max(post) - min(post) <= tolerance):
                        value, source, selection = opt.energy_hartree, opt.energy_source, "opt_summary_line_search"
        yield step, opt, value, source, len(records), selection == "ambiguous", selection


def _segment_atom_count(lines, span, source_path):
    start_line, end_line = span
    records, warnings = [], []
    for line_no in range(start_line, end_line + 1):
        raw = lines[line_no - 1]
        match = _ATOM_COUNT_LINE.fullmatch(raw.strip())
        if match is None:
            continue
        value = _ATOM_COUNT_VALUE.fullmatch(match[1])
        if value is not None:
            try:
                count = int(value[1])
            except ValueError:
                pass
            else:
                records.append((count, Evidence(source_path, line_no, raw)))
                continue
        warnings.append(f"Malformed output - Atoms: record at {source_path}:{line_no}")
    counts = {count for count, _ in records}
    if len(counts) > 1:
        locations = ", ".join(str(ev.line) for _, ev in records)
        warnings.append(f"Conflicting output - Atoms: counts at {source_path}, lines {locations}")
    count = records[0][0] if records and not warnings else None
    return count, [asdict(ev) for _, ev in records], warnings


def _match_status_reason(step, matches, unmatched):
    for entry in matches:
        if entry["step"] == step:
            if entry["status"] == "matched":
                return None
            if entry["status"] == "atom_count_mismatch":
                return f"Step {step}: atom count mismatch"
            status = entry["status"].replace("_", " ")
            if entry["output_energy_ambiguous"]:
                status += "; multiple FORCE_EVAL energies disagree"
            return f"Step {step}: {status}"
    for entry in unmatched:
        if entry["step"] == step:
            return f"Step {step}: {entry['reason'].replace('_', ' ')}"
    return f"Step {step}: missing from output step records"


def match_trajectory(output: Run | str | Path, trajectory_path: str | Path, *, segment: int | None = None,
                     energy_tol_hartree: float = DEFAULT_ENERGY_TOL_HARTREE,
                     requested_step: int | None = None) -> TrajectoryMatchReport:
    """Classify output/frame associations without assuming restart continuity."""
    if (isinstance(energy_tol_hartree, bool) or not isinstance(energy_tol_hartree, (int, float))
            or not 0 <= energy_tol_hartree <= float_info.max):
        raise KitError("Energy tolerance must be finite and nonnegative (hartree)")
    if requested_step is not None and type(requested_step) is not int:
        raise KitError("Requested optimization step must be an integer")
    if isinstance(output, Run):
        run = output
    else:
        run, lines, ranges = _parse_output_with_ranges(output)
    if segment is None:
        if len(run.segments) > 1:
            choices = ", ".join(str(i) for i in range(1, len(run.segments) + 1))
            raise AmbiguousProject(f"Multiple output segments; set --segment. Candidates (1-based): {choices}")
        segment = 1
    if type(segment) is not int or not 1 <= segment <= len(run.segments):
        raise KitError(f"Segment must be a 1-based integer in 1..{len(run.segments)}")
    seg = run.segments[segment - 1]
    if Path(trajectory_path).suffix.lower() not in {".xyz", ".extxyz"}:
        raise KitError("Trajectory must be an explicit .xyz or .extxyz file")

    frames, missing = [], []
    by_step = defaultdict(list)
    warnings = list(run.parser_warnings)
    output_atom_count, output_atom_count_sources = None, []
    if not isinstance(output, Run):
        output_atom_count, output_atom_count_sources, issues = _segment_atom_count(
            lines, ranges[segment - 1], run.source["path"])
        warnings.extend(issues)
    for structure, comment in read_xyz_frames(trajectory_path):
        source = structure.source
        step, energy, issues = parse_trajectory_comment(comment, source_path=source["path"],
                                                       line=source["line_start"] + 1)
        warnings.extend(issues)
        frame = TrajectoryFrame(structure.frame, source["line_start"], source["line_end"], comment,
                                step, energy, len(structure.symbols), structure.cell is not None,
                                structure.pbc is not None, structure)
        frames.append(frame)
        if step is None:
            missing.append(frame.to_dict())
        else:
            by_step[step].append(frame)
    duplicates = [{"step": step, "frame_indices": [f.frame_index for f in group]}
                  for step, group in sorted(by_step.items()) if len(group) > 1]
    matches, unmatched = [], []
    observed_steps = set()
    for step, opt, value, source, count, ambiguous, selection in _output_steps(seg, energy_tol_hartree):
        observed_steps.add(step)
        group = by_step.get(step, [])
        if len(group) != 1:
            unmatched.append({"step": step, "reason": "duplicate_in_trajectory" if group else "missing_in_trajectory"})
            continue
        frame = group[0]
        energy = frame.trajectory_energy_hartree
        atom_count_matches = None if output_atom_count is None else frame.atom_count == output_atom_count
        diff = None
        if atom_count_matches is False:
            status = "atom_count_mismatch"
            warnings.append(f"Step {step}: atom count mismatch "
                            f"(trajectory has {frame.atom_count}, output reports {output_atom_count})")
        elif energy is None:
            status = "energy_unavailable_in_trajectory"
        elif value is None:
            status = "energy_unavailable_in_output"
        else:
            diff = energy - value
            if not math.isfinite(diff):
                raise ParseError(f"Energy difference is not finite at trajectory comment line {frame.line_start + 1}")
            status = "matched" if abs(diff) <= energy_tol_hartree else "energy_mismatch"
        matches.append({"step": step, "status": status, "frame_index": frame.frame_index,
                        "line_start": frame.line_start, "line_end": frame.line_end, "comment": frame.comment,
                        "output_energy_hartree": value, "output_energy_source": asdict(source) if source else None,
                        "trajectory_energy_hartree": energy, "energy_diff_hartree": diff,
                        "output_energy_count": count, "output_energy_ambiguous": ambiguous,
                        "output_energy_selection": selection, "atom_count_matches": atom_count_matches,
                        "all_cartesian_converged": opt.all_cartesian_converged if opt else None,
                        "all_observed_converged": opt.all_observed_converged if opt else None})
    extra = [f.to_dict() for f in frames if f.trajectory_step is not None
             and f.trajectory_step not in observed_steps and len(by_step[f.trajectory_step]) == 1]
    if extra:
        warnings.append(f"{len(extra)} trajectory frame(s) have explicit steps not present in the selected output segment")

    reasons = []
    quality = quality_report(run)["segments"][segment - 1]
    if quality["status"] != "passed":
        reasons.extend(f"Segment quality: {reason}" for reason in quality["reasons"])
    if seg.geometry_converged is not True:
        reasons.append("No successful geometry convergence marker")
    candidate = seg.optimization_steps[-1].step if seg.optimization_steps else None
    if candidate is None and seg.last_observed_energy is not None:
        candidate = seg.last_observed_energy.step
    candidate_opt = next((o for o in seg.optimization_steps if o.step == candidate), None) if candidate is not None else None
    if candidate_opt and any(getattr(candidate_opt, name) is not None for name in OPTIMIZATION_CRITERIA):
        if candidate_opt.all_observed_converged is not True:
            reasons.append(f"Step {candidate}: required optimization criteria are not all observed converged")
    if candidate is None:
        reasons.append("No explicit final output step")
    else:
        issue = _match_status_reason(candidate, matches, unmatched)
        if issue is not None:
            reasons.append(issue)
    final = next(entry.copy() for entry in matches if entry["step"] == candidate) if not reasons else None
    strict = (not duplicates and not missing
              and not any(m["status"] in {"energy_mismatch", "atom_count_mismatch"} for m in matches)
              and (final is not None if requested_step is None
                   else _match_status_reason(requested_step, matches, unmatched) is None))
    trajectory_source = {key: frames[0].structure.source[key] for key in ("path", "sha256", "size_bytes")}
    return TrajectoryMatchReport(run.source, trajectory_source, segment, seg.id, energy_tol_hartree,
                                 requested_step, frames, matches, missing, duplicates, unmatched, extra,
                                 final, "matched" if final else "unavailable", reasons, strict, warnings,
                                 output_atom_count=output_atom_count, output_atom_count_sources=output_atom_count_sources)


def select_matched_frame(report: TrajectoryMatchReport, *, step: int | None = None) -> tuple[TrajectoryFrame, dict]:
    """Return only an energy-verified frame; never substitute another step."""
    if step is None:
        match = report.converged_final_step
        if match is None:
            raise KitError("Converged final step unavailable: " + "; ".join(report.converged_final_reasons))
    else:
        if type(step) is not int:
            raise KitError("Requested optimization step must be an integer")
        issue = _match_status_reason(step, report.matches, report.unmatched_output_steps)
        if issue is not None:
            raise KitError(issue)
        match = next(entry for entry in report.matches if entry["step"] == step)
    return report.frames[match["frame_index"]], match
