"""Headless curves; segments are independent and data is exported alongside images."""
import hashlib
from contextlib import ExitStack
from pathlib import Path

from .errors import KitError, MissingDependency
from .export import write_csv
from .io import json_text, new_file
from .quality import quality_report


def plot_run(run, output, kind="energy"):
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg
    except ImportError as exc:
        raise MissingDependency("Plotting requires matplotlib; install cp2kkit[plot]") from exc
    output = Path(output)
    if output.suffix.lower() != ".png":
        raise KitError("v0.1 plot output must be a .png file")
    figure = Figure(figsize=(7, 4.5), layout="constrained")
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    energy_records = [e for s in run.segments for e in s.energies]
    use_steps = bool(energy_records) and all(e.step is not None for e in energy_records)
    points = 0
    quality = quality_report(run)
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
    csv_path = output.with_suffix(".csv")
    manifest_path = output.with_suffix(".json")
    # Reserve all files first; a collision/error removes only newly created files.
    with ExitStack() as stack:
        image = stack.enter_context(new_file(output, binary=True))
        data = stack.enter_context(new_file(csv_path))
        manifest = stack.enter_context(new_file(manifest_path))
        write_csv(data, run)
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
