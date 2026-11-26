"""Conservative line-oriented CP2K output parser (validated formats in fixtures)."""
import math
import re

from .discovery import CP2K_MARKER
from .errors import ParseError
from .io import read_text
from .models import (OPTIMIZATION_CRITERIA, ConvergenceCriterion, Energy, Evidence,
                     OptimizationStep, Quantity, Run, SCHEMA_VERSION, Segment)
from .output_settings import normalize_settings

NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?"
# Both explicit unit labels denote hartree; retain complete-token boundaries.
# Whitespace-delimited annotations are allowed, but adjacent garbage is not.
ENERGY = re.compile(r"ENERGY\|\s+Total FORCE_EVAL\s+\([^)]*\)\s+energy\s+\[(?:a\.u\.|hartree)\]\s*[:=]?\s*(" + NUMBER + r")(?=\s|$)", re.I)
STEP = re.compile(r"(?:OPTIMIZATION STEP\s*:|MD\|\s+Step number)\s*(\d+)", re.I)
SCF_OK = re.compile(r"SCF run converged in\s+(\d+)\s+steps", re.I)
SCF_FAIL = re.compile(r"SCF run NOT converged|SCF run did not converge|SCF NOT converged", re.I)
VERSION = re.compile(r"CP2K\|\s+version string:\s*(.+)", re.I)
PROJECT = re.compile(r"GLOBAL\|\s+Project name\s+(\S+)", re.I)
RUN_TYPE = re.compile(r"GLOBAL\|\s+Run type\s+(\S+)", re.I)
WALL_LABEL = re.compile(r"\b(?:Total wall time|WALL TIME)\s*\[s\]", re.I)
WALL = re.compile(WALL_LABEL.pattern + r"\s*[:=]?\s*(" + NUMBER + r")(?=\s|$)", re.I)
SETTING = re.compile(r"^\s*(DFT|QS|XC|CELL|GLOBAL)\|\s*(.*?)\s{2,}(\S.*)$")
DIAGNOSTIC = re.compile(r"\b(?:ERROR|WARNING|ABORT)\b|\*{3}\s*(?:ERROR|WARNING)", re.I)


def number(token, source):
    value = float(token.replace("D", "E").replace("d", "e"))
    if not math.isfinite(value):
        raise ParseError(f"Non-finite number at {source.path}:{source.line}")
    if value == 0 and any(c in '123456789' for c in re.split('[eEdD]', token, maxsplit=1)[0]):
        raise ParseError(f"Number underflows to zero at {source.path}:{source.line}")
    return value


# (criterion, member, unit), or (None, step member, None) for block metadata.
_OPT_LABELS = {
    "Step number": (None, "step", None),
    "Optimization method": (None, "method", None),
    "Total energy [hartree]": (None, "energy_hartree", None),
    "Total energy [a.u.]": (None, "energy_hartree", None),
    "Internal pressure [bar]": (None, "internal_pressure_bar", None),
    "Pressure deviation [bar]": ("pressure", "value", "bar"),
    "Pressure tolerance [bar]": ("pressure", "limit", "bar"),
    "Pressure is converged": ("pressure", "converged", "bar"),
    "Conv. for PRESSURE": ("pressure", "converged", "bar"),
}
_LEGACY_LABELS = {
    label: _OPT_LABELS[label] for label in ("Internal pressure [bar]", "Pressure deviation [bar]",
                                           "Pressure tolerance [bar]", "Conv. for PRESSURE")
}
for _name, _unit, _label, _legacy in (
    ("max_step", "bohr", "Maximum step size", ("Max. step size", "Conv. limit for step size", "Convergence in step size")),
    ("rms_step", "bohr", "RMS step size", ("RMS step size", "Conv. limit for RMS step", "Convergence in RMS step")),
    ("max_gradient", "hartree/bohr", "Maximum gradient", ("Max. gradient", "Conv. limit for gradients", "Conv. for gradients")),
    ("rms_gradient", "hartree/bohr", "RMS gradient", ("RMS gradient", "Conv. limit for RMS grad.", "Conv. for RMS grad.")),
):
    for _member, _modern, _old in zip(
        ("value", "limit", "converged"), (_label, "Convergence limit for " + _label, _label + " is converged"), _legacy
    ):
        _OPT_LABELS[_modern] = _LEGACY_LABELS[_old] = (_name, _member, _unit)


def _optimization_pattern(labels, prefix, separator):
    alternatives = "|".join(re.escape(label).replace(r"\ ", r"\s+")
                            for label in sorted(labels, key=len, reverse=True))
    return re.compile(r"^\s*" + prefix + "(" + alternatives + ")" + separator + r"(.*)$", re.I)


_OPT_LABELS = {key.lower(): value for key, value in _OPT_LABELS.items()}
_LEGACY_LABELS = {key.lower(): value for key, value in _LEGACY_LABELS.items()}
_OPT_RECORDS = (
    (_optimization_pattern(_OPT_LABELS, r"OPT\|\s*", r"(?=\s|$)"), _OPT_LABELS),
    (_optimization_pattern(_LEGACY_LABELS, r"(?:Convergence\s+check\s*:\s*)?", r"\s*="), _LEGACY_LABELS),
)


def _optimization_record(line):
    for pattern, labels in _OPT_RECORDS:
        match = pattern.match(line)
        if match:
            return (*labels[" ".join(match[1].lower().split())], match[2].strip())
    return None


def _optimization_value(member, token, evidence):
    if member == "step":
        if re.fullmatch(r"[+-]?[0-9]+", token):
            try:
                return int(token)
            except ValueError:
                pass
        return None
    if member == "method":
        return token if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", token) else None
    if member == "converged":
        return token.upper() == "YES" if token.upper() in {"YES", "NO"} else None
    return number(token, evidence) if re.fullmatch(NUMBER, token) else None


def _record_optimization_value(opt, name, member, unit, value, evidence):
    if name is None:
        setattr(opt, member, value)
        if member in {"energy_hartree", "internal_pressure_bar"}:
            source_field = "energy_source" if member == "energy_hartree" else "internal_pressure_source"
            setattr(opt, source_field, evidence if value is not None else None)
        return
    criterion = getattr(opt, name)
    if criterion is None:
        criterion = ConvergenceCriterion(unit=unit)
        setattr(opt, name, criterion)
    setattr(criterion, member, value)
    if member != "value":
        setattr(criterion, member + "_source", evidence if value is not None else None)
    if member == "value" and value is not None:
        criterion.source = evidence
    elif criterion.value is None:
        sources = (criterion.limit_source, criterion.converged_source)
        criterion.source = min((s for s in sources if s is not None), key=lambda s: s.line, default=None)


def _finalize_optimization(segment):
    def flags(criteria):
        if all(c is not None and c.converged is not None for c in criteria):
            return all(c.converged is True for c in criteria)
        return None

    for opt in segment.optimization_steps:
        four = tuple(getattr(opt, name) for name in OPTIMIZATION_CRITERIA[:-1])
        required = (*four, opt.pressure) if segment.run_type == "CELL_OPT" or opt.pressure is not None else four
        opt.all_cartesian_converged = flags(four)
        opt.all_observed_converged = flags(required)
    if segment.optimization_steps:
        segment.last_optimization_step = segment.optimization_steps[-1]


def _parse_output_with_ranges(path):
    text, provenance = read_text(path)
    if not CP2K_MARKER.search(text):
        raise ParseError(f"No recognizable CP2K output markers: {path}")
    lines = text.splitlines()
    segments = []
    ranges = []
    current = None
    step = None
    pending_scf = None
    scf_evidence = []
    step_source = None
    version = project = None
    warnings = []

    opt = None
    last_opt_step = None
    opt_number_seen = False

    def begin(line_no, started=False):
        nonlocal current, step, pending_scf, scf_evidence, step_source, opt, last_opt_step, opt_number_seen
        current = Segment(id=len(segments), started=started)
        segments.append(current)
        ranges.append([line_no, line_no])
        step = None
        step_source = None
        pending_scf = None
        scf_evidence = []
        opt = None
        last_opt_step = None
        opt_number_seen = False

    def begin_opt(number, source):
        nonlocal opt, last_opt_step, opt_number_seen
        opt = OptimizationStep(current.id, len(current.optimization_steps) + 1, number, source)
        current.optimization_steps.append(opt)
        if number is not None:
            last_opt_step = number
        opt_number_seen = False

    def reset(line_no):
        old_run_type = current.run_type
        begin(line_no)
        current.run_type = old_run_type
        warnings.append(f"Step reset at line {line_no}: new segment, no inferred restart continuity")

    for line_no, line in enumerate(lines, 1):
        evidence = Evidence(provenance["path"], line_no, line)
        was_completed = current is not None and current.completed
        opt_record = _optimization_record(line)
        if was_completed and (opt_record or VERSION.search(line) or RUN_TYPE.search(line)
                or STEP.search(line) or SCF_OK.search(line) or SCF_FAIL.search(line)
                or SETTING.match(line) or re.search(r"ENERGY\|\s+Total FORCE_EVAL", line, re.I)):
            begin(line_no)
            was_completed = False
        if "PROGRAM STARTED AT" in line:
            if current is None:
                begin(line_no, True)
                was_completed = False
            elif current.started or current.energies or current.optimization_steps or current.completed:
                begin(line_no, True)
                was_completed = False
            else:
                current.started = True
            current.evidence.append(evidence)
        if current is None:
            begin(line_no)
            was_completed = False
        match = VERSION.search(line)
        if match:
            new_version = match[1].strip()
            if version and version != new_version:
                warnings.append("Concatenated output contains different CP2K versions")
            version = new_version
            current.settings["software_version"] = {"value": version, "source": evidence.__dict__}
        match = PROJECT.search(line)
        if match:
            new_project = match[1]
            if project and project != new_project:
                warnings.append("Concatenated output contains different project names")
            project = new_project
        match = RUN_TYPE.search(line)
        if match:
            current.run_type = match[1].upper()
            current.evidence.append(evidence)
        match = SETTING.match(line)
        if match:
            key = match[1] + "|" + match[2].strip()
            explicit_unit = re.search(r"\[([^\]]+)\]", key)
            record = {"value": match[3].strip(),
                      "unit": explicit_unit[1] if explicit_unit else None,
                      "source": evidence.__dict__}
            current.settings[key] = record
            current.settings_records.append({"key": key, **record})
        match = STEP.search(line)
        if match:
            new_step = int(match[1])
            is_opt_banner = match[0].upper().startswith("OPTIMIZATION")
            if (current.completed or (step is not None and new_step <= step)
                    or (is_opt_banner and last_opt_step is not None and new_step <= last_opt_step)):
                reset(line_no)
                was_completed = False
            if is_opt_banner:
                begin_opt(new_step, evidence)
            step = new_step
            step_source = evidence
            pending_scf = None
            scf_evidence = []
            current.scf_converged = None
        if opt_record:
            name, member, unit, token = opt_record
            value = _optimization_value(member, token, evidence)
            if value is None:
                current.unparsed_optimization_records.append(evidence)
                warnings.append(f"Unsupported or malformed optimization record at {evidence.path}:line {line_no}")
            if member == "step":
                if value is None:
                    # Do not attach records from an unidentifiable block to a
                    # previous explicit optimization step.
                    begin_opt(None, None)
                else:
                    confirms_banner = opt is not None and opt.step == value and not opt_number_seen
                    if last_opt_step is not None and value <= last_opt_step and not confirms_banner:
                        reset(line_no)
                    if opt is None or opt.step != value:
                        begin_opt(value, evidence)
                    # A banner and its first OPT| step label describe one step.
                    # Do not change the legacy FORCE_EVAL step / SCF association.
                    opt_number_seen = True
            else:
                if opt is None:
                    begin_opt(None, None)
                _record_optimization_value(opt, name, member, unit, value, evidence)
        match = SCF_OK.search(line)
        if match:
            current.scf_converged = pending_scf = True
            current.scf_iterations.append(Quantity(int(match[1]), "iteration", evidence))
            current.evidence.append(evidence)
            scf_evidence.append(evidence)
        elif SCF_FAIL.search(line):
            current.scf_converged = pending_scf = False
            current.evidence.append(evidence)
            scf_evidence.append(evidence)
        if "GEOMETRY OPTIMIZATION COMPLETED" in line:
            if current.geometry_converged is not False:
                current.geometry_converged = True
            current.evidence.append(evidence)
        if re.search(r"MAXIMUM NUMBER OF OPTIMIZATION STEPS|GEOMETRY OPTIMIZATION.*(?:NOT CONVERGED|FAILED)", line, re.I):
            current.geometry_converged = False
            current.evidence.append(evidence)
        match = ENERGY.search(line)
        if match:
            quantity = Quantity(number(match[1], evidence), "hartree", evidence)
            energy = Energy(
                current.id, len(current.energies) + 1, step, quantity, pending_scf,
                step_source=step_source,
                scf_source=scf_evidence[0] if len(scf_evidence) == 1 else None,
                scf_evidence=list(scf_evidence),
                scf_association=("preceding_summary" if len(scf_evidence) == 1 else
                                 "ambiguous" if scf_evidence else "unknown"))
            current.energies.append(energy)
            current.last_observed_energy = energy
            current.final_energy = quantity
            current.scf_converged = pending_scf
            pending_scf = None
            scf_evidence = []
        elif re.search(r"ENERGY\|\s+Total FORCE_EVAL", line, re.I):
            current.unparsed_energy_records.append(evidence)
            current.unparsed_energy_context.append({
                "segment": current.id, "step": step,
                "step_source": None if step_source is None else step_source.__dict__,
                "source": evidence.__dict__,
                "scf_evidence": [item.__dict__ for item in scf_evidence],
                "reason": "unsupported_or_malformed"})
            warnings.append(f"Unsupported or malformed energy record at line {line_no}")
            # A damaged observation consumes its summaries too; never transfer
            # their convergence to a later, unrelated energy record.
            pending_scf = None
            scf_evidence = []
        if WALL_LABEL.search(line):
            current.wall_time = None
            match = WALL.search(line)
            if match:
                try:
                    current.wall_time = Quantity(number(match[1], evidence), "s", evidence)
                except ParseError as exc:
                    warnings.append(f"Invalid wall-time record at line {line_no}: {exc}")
            else:
                warnings.append(f"Malformed wall-time record at line {line_no}")
        if DIAGNOSTIC.search(line):
            current.diagnostics.append(evidence)
        if "PROGRAM ENDED AT" in line:
            current.completed = True
            current.evidence.append(evidence)
        if not was_completed:
            ranges[-1][1] = line_no
    for segment in segments:
        _finalize_optimization(segment)
        segment.normalized_settings = normalize_settings(segment.settings_records)
        for field, setting in segment.normalized_settings.items():
            if field != "uks" and setting["status"] in {"unsupported", "conflicting"}:
                setting_lines = ", ".join(str(source["line"]) for source in setting["sources"])
                warnings.append(f"{setting['status'].capitalize()} setting {field} "
                                f"in segment {segment.id} at lines {setting_lines}")
    if not version:
        warnings.append("CP2K version not found; compatibility cannot be established")
    if any(not segment.completed for segment in segments):
        warnings.append("At least one segment lacks PROGRAM ENDED AT (partial/aborted/unknown)")
    run = Run(SCHEMA_VERSION, "CP2K", version, project, provenance, segments,
              parser_warnings=warnings)
    return run, lines, tuple(tuple(span) for span in ranges)


def parse_output(path):
    return _parse_output_with_ranges(path)[0]
