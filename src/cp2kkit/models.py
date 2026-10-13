"""Versioned interchange model; null is distinct from numerical zero."""
from dataclasses import asdict, dataclass, field
from typing import Any

SCHEMA_VERSION = "0.1.0"


@dataclass
class Evidence:
    path: str
    line: int
    text: str


@dataclass
class Quantity:
    value: float
    unit: str
    source: Evidence


@dataclass
class Energy:
    segment: int
    index: int
    step: int | None
    quantity: Quantity
    scf_converged: bool | None = None


@dataclass
class Segment:
    id: int
    started: bool = False
    completed: bool = False
    scf_converged: bool | None = None
    geometry_converged: bool | None = None
    run_type: str | None = None
    evidence: list[Evidence] = field(default_factory=list)
    energies: list[Energy] = field(default_factory=list)
    scf_iterations: list[Quantity] = field(default_factory=list)
    final_energy: Quantity | None = None
    wall_time: Quantity | None = None
    diagnostics: list[Evidence] = field(default_factory=list)
    unparsed_energy_records: list[Evidence] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class Run:
    schema_version: str
    software: str
    software_version: str | None
    project: str | None
    source: dict[str, Any]
    segments: list[Segment]
    settings: dict[str, Any] = field(default_factory=dict)
    parser_warnings: list[str] = field(default_factory=list)
    # Process exit status is not inferred from a text output.
    exit_status: int | None = None

    def to_dict(self):
        return asdict(self)
