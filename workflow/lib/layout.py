from pathlib import Path
from typing import Any


def get_layout_paths(
    base_dir: Path,
    llvm_tag: str,
    official_tag: str,
    raja_tag: str,
    llvm_version: str,
    label: str,
    sample: str,
    experiment_id: str,
) -> dict[str, Path]:
    return {
        "sources_root": base_dir / "sources",
        "builds_root": base_dir / "builds",
        "installs_root": base_dir / "installs",
        "results_root": base_dir / "results",
        "parsed_root": base_dir / "parsed",
        "reports_root": base_dir / "reports",
        "logs_root": base_dir / "logs",
        "metadata_root": base_dir / "metadata",
        "llvm_source": base_dir / "sources" / "llvm-project" / llvm_tag,
        "official_source": base_dir / "sources" / "official" / official_tag,
        "raja_source": base_dir / "sources" / "raja" / raja_tag,
        "llvm_build": base_dir / "builds" / "llvm" / llvm_tag,
        "official_build": base_dir / "builds" / "official" / official_tag / f"llvm-{llvm_tag}",
        "raja_build": base_dir / "builds" / "raja" / raja_tag / f"llvm-{llvm_tag}",
        "llvm_install": base_dir / "installs" / "llvm" / llvm_tag,
        "official_result": base_dir / "results" / f"official-{official_tag}" / llvm_tag / label / sample,
        "raja_result": base_dir / "results" / f"raja-{raja_tag}" / llvm_tag / label / sample,
        "parsed_run_dir": base_dir / "parsed" / experiment_id,
        "reports_run_dir": base_dir / "reports" / experiment_id,
        "logs_run_dir": base_dir / "logs" / experiment_id,
        "metadata_run_dir": base_dir / "metadata" / experiment_id,
    }


def get_experiment_layout_paths(base_dir: Path, experiment: dict[str, Any]) -> dict[str, Path]:
    return get_layout_paths(
        base_dir=base_dir,
        llvm_tag=str(experiment["llvm_tag"]),
        official_tag=str(experiment["official_tag"]),
        raja_tag=str(experiment["raja_tag"]),
        llvm_version=str(experiment["llvm_version"]),
        label=str(experiment["label"]),
        sample=str(experiment["sample"]),
        experiment_id=str(experiment["experiment_id"]),
    )
