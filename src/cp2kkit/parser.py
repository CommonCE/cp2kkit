"""Conservative line-oriented CP2K output parser (validated formats in fixtures)."""
import math
import re

from .discovery import CP2K_MARKER
from .errors import ParseError
from .io import read_text
from .models import Energy, Evidence, Quantity, Run, SCHEMA_VERSION, Segment
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
WALL = re.compile(r"(?:Total wall time|WALL TIME)\s*\[s\]\s*[:=]?\s*(" + NUMBER + r")", re.I)
SETTING = re.compile(r"^\s*(DFT|QS|XC|CELL|GLOBAL)\|\s*(.*?)\s{2,}(\S.*)$")
DIAGNOSTIC = re.compile(r"\b(?:ERROR|WARNING|ABORT)\b|\*{3}\s*(?:ERROR|WARNING)", re.I)


def number(token, source):
    value = float(token.replace("D", "E").replace("d", "e"))
    if not math.isfinite(value):
        raise ParseError(f"Non-finite number at {source.path}:{source.line}")
    return value


def parse_output(path):
    text, provenance = read_text(path)
    if not CP2K_MARKER.search(text):
        raise ParseError(f"No recognizable CP2K output markers: {path}")
    segments = []
    current = None
    step = None
    pending_scf = None
    scf_evidence = []
    step_source = None
    version = project = None
    warnings = []

    def begin(started=False):
        nonlocal current, step, pending_scf, scf_evidence, step_source
        current = Segment(id=len(segments), started=started)
        segments.append(current)
        step = None
        step_source = None
        pending_scf = None
        scf_evidence = []

    for line_no, line in enumerate(text.splitlines(), 1):
        evidence = Evidence(provenance["path"], line_no, line)
        if current is not None and current.completed and (VERSION.search(line) or RUN_TYPE.search(line)
                or STEP.search(line) or SCF_OK.search(line) or SCF_FAIL.search(line)
                or SETTING.match(line) or re.search(r"ENERGY\|\s+Total FORCE_EVAL", line, re.I)):
            begin()
        if "PROGRAM STARTED AT" in line:
            if current is None:
                begin(True)
            elif current.started or current.energies or current.completed:
                begin(True)
            else:
                current.started = True
            current.evidence.append(evidence)
        if current is None:
            begin()
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
            if current.completed or (step is not None and new_step <= step):
                old_run_type = current.run_type
                begin()
                current.run_type = old_run_type
                warnings.append(f"Step reset at line {line_no}: new segment, no inferred restart continuity")
            step = new_step
            step_source = evidence
            pending_scf = None
            scf_evidence = []
            current.scf_converged = None
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
        match = WALL.search(line)
        if match:
            current.wall_time = Quantity(number(match[1], evidence), "s", evidence)
        if DIAGNOSTIC.search(line):
            current.diagnostics.append(evidence)
        if "PROGRAM ENDED AT" in line:
            current.completed = True
            current.evidence.append(evidence)
    for segment in segments:
        segment.normalized_settings = normalize_settings(segment.settings_records)
        for field, setting in segment.normalized_settings.items():
            if field != "uks" and setting["status"] in {"unsupported", "conflicting"}:
                lines = ", ".join(str(source["line"]) for source in setting["sources"])
                warnings.append(f"{setting['status'].capitalize()} setting {field} "
                                f"in segment {segment.id} at lines {lines}")
    if not version:
        warnings.append("CP2K version not found; compatibility cannot be established")
    if any(not segment.completed for segment in segments):
        warnings.append("At least one segment lacks PROGRAM ENDED AT (partial/aborted/unknown)")
    return Run(SCHEMA_VERSION, "CP2K", version, project, provenance, segments,
               parser_warnings=warnings)
