"""Headless curves; segments are independent and data is exported alongside images."""
import hashlib
from contextlib import ExitStack
from pathlib import Path

from .errors import KitError, MissingDependency
from .export import write_convergence_csv, write_csv
from .io import json_text, new_file
from .models import OPTIMIZATION_CRITERIA
from .quality import quality_report


def _convergence_axes(figure, run):
    segments = []
    for segment in run.segments:
        steps = [opt for opt in segment.optimization_steps
                 if any(getattr(opt, name) is not None for name in OPTIMIZATION_CRITERIA)]
        if steps:
            segments.append((segment.id, steps))
    if not segments:
        raise KitError("No convergence criteria records to plot")

    use_steps = all(opt.step is not None for _, steps in segments for opt in steps)
    xlabel = ("Optimization step (per segment)" if use_steps else
              "Optimization observation index (per segment)")
    series = {name: [] for name in OPTIMIZATION_CRITERIA}
    for segment, steps in segments:
        x = [opt.step if use_steps else opt.index for opt in steps]
        for name in series:
            criteria = [getattr(opt, name) for opt in steps]
            if any(c is not None for c in criteria):
                series[name].append((segment, x, criteria))

    ylabel = "Cartesian criteria [bohr or hartree/bohr]"
    panels = [(OPTIMIZATION_CRITERIA[:-1], ylabel)]
    if series["pressure"]:
        axes = figure.subplots(2, 1, sharex=True)
        panels.append((("pressure",), "Pressure deviation / tolerance [bar]"))
    else:
        axes = [figure.subplots()]
    for axis, (names, label) in zip(axes, panels):
        criteria = [c for name in names for _, _, cs in series[name] for c in cs if c is not None]
        values = [c.value for c in criteria if c.value is not None]
        limits = [c.limit for c in criteria if c.limit is not None]
        # Pressure may be signed. For Cartesian criteria use a linear scale
        # when no positive measurement is available, preserving exact zeros.
        log_scale = names != ("pressure",) and any(value > 0 for value in values)
        if log_scale:
            axis.set_yscale("log")
        for name in names:
            positive_limits = set()
            for segment, x, cs in series[name]:
                y = [c.value if c is not None and c.value is not None
                     and (not log_scale or c.value > 0) else float("nan") for c in cs]
                if any(value == value for value in y):
                    axis.plot(x, y, "o-", label=f"segment {segment}: {name}")
                positive_limits.update(c.limit for c in cs if c is not None and c.limit is not None and c.limit > 0)
            for limit in sorted(positive_limits):
                axis.axhline(limit, color="0.5", linestyle="--", label=f"{name} limit: {limit:g}")
        if log_scale and any(v <= 0 for v in values + limits):
            axis.text(0.02, 0.02, "Nonpositive values/limits omitted on log scale; see CSV",
                      transform=axis.transAxes, fontsize="small")
        elif not values:
            axis.text(0.02, 0.02, "No numeric values observed; see CSV", transform=axis.transAxes)
        axis.set_ylabel(label)
        axis.grid(alpha=0.25)
        if axis.lines:
            axis.legend()
    axes[-1].set_xlabel(xlabel)
    figure.suptitle("CP2K convergence criteria - inspect quality report before use")
    return xlabel, ylabel


def plot_run(run, output, kind="energy"):
    if not isinstance(kind, str) or kind not in {"energy", "scf", "convergence"}:
        raise KitError("Plot kind must be 'energy', 'scf' or 'convergence'")
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
    except ImportError as exc:
        raise MissingDependency("Plotting requires matplotlib; install cp2kkit[plot]") from exc
    output = Path(output)
    if output.suffix.lower() != ".png":
        raise KitError("v0.1 plot output must be a .png file")
    figure = Figure(figsize=(7, 7 if kind == "convergence" else 4.5), layout="constrained")
    FigureCanvasAgg(figure)
    quality = quality_report(run)
    if kind == "convergence":
        xlabel, ylabel = _convergence_axes(figure, run)
    else:
        xlabel, ylabel = _standard_axis(figure, run, kind, quality)
    csv_path = output.with_suffix(".csv")
    manifest_path = output.with_suffix(".json")
    # Reserve all files first; a collision/error removes only newly created files.
    with ExitStack() as stack:
        image = stack.enter_context(new_file(output, binary=True))
        data = stack.enter_context(new_file(csv_path))
        manifest = stack.enter_context(new_file(manifest_path))
        writer = write_convergence_csv if kind == "convergence" else write_csv
        writer(data, run)
        data.flush()
        figure.savefig(image, format="png", metadata={"Software": "cp2kkit"})
        image.flush()
        manifest.write(json_text({
            "schema_version": run.schema_version, "source": run.source,
            "kind": kind, "x_label": xlabel, "y_label": ylabel,
            "segments_connected": False,
            "data": {"path": str(csv_path.resolve()), "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest()},
            "image": {"path": str(output.resolve()), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()},
            "run": run.to_dict(), "quality": quality,
        }))
    return [output, csv_path, manifest_path]


def _standard_axis(figure, run, kind, quality):
    axis = figure.subplots()
    energy_records = [e for s in run.segments for e in s.energies]
    use_steps = bool(energy_records) and all(e.step is not None for e in energy_records)
    points = 0
    statuses = {report["segment"]: report["status"] for report in quality["segments"]}
    for segment in run.segments:
        if kind == "energy":
            x = [e.step if use_steps else e.index for e in segment.energies]
            y = [e.quantity.value for e in segment.energies]
        else:
            x = list(range(1, len(segment.scf_iterations)+1))
            y = [q.value for q in segment.scf_iterations]
        if x:
            status = statuses[segment.id]
            axis.plot(x, y, "o-" if status == "passed" else "o--",
                      label=f"segment {segment.id} [{status}]")
            points += len(x)
    if not points:
        raise KitError(f"No {kind} records to plot")
    xlabel = ("Optimization/MD step (per segment)" if use_steps else "Energy record index (per segment)") if kind == "energy" else "SCF cycle index (per segment)"
    ylabel = "Total energy [hartree]" if kind == "energy" else "SCF iterations [iteration]"
    axis.set(xlabel=xlabel, ylabel=ylabel, title=f"CP2K {kind} — inspect quality report before use")
    axis.grid(alpha=0.25)
    axis.legend()
    return xlabel, ylabel
