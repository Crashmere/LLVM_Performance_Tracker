from datetime import datetime
from itertools import product
import re
import subprocess
from pathlib import Path
from typing import Any, Callable

import yaml


RunCommand = Callable[[list[str], Path | None, dict[str, str] | None], bool]
StatusCallback = Callable[[str], None]


def load_config(config_file: Path) -> dict[str, Any]:
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Configuration at {config_file} must be a mapping.")

    return config


def _ensure_list(value: Any, *, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return [str(item) for item in list(value)]


def _parse_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list of strings, got {type(value).__name__}.")
    return [str(item) for item in value]


def _slugify(value: Any) -> str:
    text = str(value).strip()
    slug = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    slug = re.sub(r"_+", "_", slug).strip("._-")
    return slug or "value"


def _normalize_label(value: Any) -> str:
    if value is None:
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    if isinstance(value, list):
        raise TypeError("label must be a single string, not a list.")
    return str(value)


def _parse_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be a boolean, got {type(value).__name__}.")
    return value


def normalize_test_selection(config: dict[str, Any]) -> dict[str, Any]:
    raw_selection = config.get("test_selection", {})
    if raw_selection is None:
        raw_selection = {}
    if not isinstance(raw_selection, dict):
        raise TypeError(f"test_selection must be a mapping, got {type(raw_selection).__name__}.")

    raw_official = raw_selection.get("official", {})
    if raw_official is None:
        raw_official = {}
    if not isinstance(raw_official, dict):
        raise TypeError(f"test_selection.official must be a mapping, got {type(raw_official).__name__}.")

    raw_raja = raw_selection.get("raja", {})
    if raw_raja is None:
        raw_raja = {}
    if not isinstance(raw_raja, dict):
        raise TypeError(f"test_selection.raja must be a mapping, got {type(raw_raja).__name__}.")

    return {
        "official": {
            "lit_args": _parse_string_list(
                raw_official.get("lit_args", []),
                "test_selection.official.lit_args",
            ),
        },
        "raja": {
            "extra_args": _parse_string_list(
                raw_raja.get("extra_args", []),
                "test_selection.raja.extra_args",
            ),
        },
    }


def _build_experiment_id(llvm_tag: str, official_tag: str, raja_tag: str, label: str) -> str:
    return "__".join(
        [
            f"llvm_{_slugify(llvm_tag)}",
            f"official_{_slugify(official_tag)}",
            f"raja_{_slugify(raja_tag)}",
            f"label_{_slugify(label)}",
        ]
    )


def _normalize_simple_experiments(
    llvm_tags: list[str],
    official_tags: list[str],
    raja_tags: list[str],
    label: str,
) -> list[dict[str, Any]]:
    experiments: list[dict[str, Any]] = []
    for llvm_tag, official_tag, raja_tag in product(llvm_tags, official_tags, raja_tags):
        experiments.append(
            {
                "llvm_tag": llvm_tag,
                "official_tag": official_tag,
                "raja_tag": raja_tag,
                "label": label,
            }
        )
    return experiments


def _normalize_explicit_experiments(
    raw_experiments: list[Any],
    default_platform: str | None,
    label: str,
) -> list[dict[str, Any]]:
    experiments: list[dict[str, Any]] = []
    required_keys = ["llvm_tag", "official_tag", "raja_tag"]

    for index, raw_experiment in enumerate(raw_experiments, start=1):
        if not isinstance(raw_experiment, dict):
            raise ValueError(f"experiments[{index - 1}] must be a mapping.")

        missing_keys = [key for key in required_keys if key not in raw_experiment]
        if missing_keys:
            raise ValueError(
                f"experiments[{index - 1}] is missing required key(s): {', '.join(missing_keys)}"
            )

        llvm_tag = str(raw_experiment["llvm_tag"])
        official_tag = str(raw_experiment["official_tag"])
        raja_tag = str(raw_experiment["raja_tag"])

        experiments.append(
            {
                "llvm_tag": llvm_tag,
                "official_tag": official_tag,
                "raja_tag": raja_tag,
                "label": label,
                "platform": raw_experiment.get("platform", default_platform),
            }
        )

    return experiments


def _finalize_experiments(raw_experiments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    experiments: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_keys: set[tuple[str, str, str, str]] = set()

    for raw_experiment in raw_experiments:
        llvm_tag = str(raw_experiment["llvm_tag"])
        official_tag = str(raw_experiment["official_tag"])
        raja_tag = str(raw_experiment["raja_tag"])
        label = str(raw_experiment["label"])
        llvm_version = resolve_llvm_version(llvm_tag)
        experiment_id = _build_experiment_id(llvm_tag, official_tag, raja_tag, label)
        experiment_key = (llvm_tag, official_tag, raja_tag, label)

        if experiment_key in seen_keys:
            raise ValueError(
                "Duplicate experiment combination detected for "
                f"llvm_tag={llvm_tag!r}, official_tag={official_tag!r}, "
                f"raja_tag={raja_tag!r}, label={label!r}."
            )
        if experiment_id in seen_ids:
            raise ValueError(f"Duplicate experiment_id generated: {experiment_id}")

        seen_keys.add(experiment_key)
        seen_ids.add(experiment_id)

        experiments.append(
            {
                "experiment_id": experiment_id,
                "llvm_tag": llvm_tag,
                "llvm_version": llvm_version,
                "official_tag": official_tag,
                "raja_tag": raja_tag,
                "label": label,
                "platform": raw_experiment.get("platform"),
            }
        )

    return experiments


def normalize_workflow_config(config: dict[str, Any]) -> dict[str, Any]:
    project = config["project"]
    build = config["build"]
    repositories = config["repositories"]
    compilers = config["compilers"]
    suite_defaults = config["suite_defaults"]
    test_selection = normalize_test_selection(config)
    raw_experiments = config.get("experiments", [])
    label = _normalize_label(config.get("label"))

    if raw_experiments:
        llvm_tags: list[str] = []
        official_tags: list[str] = []
        raja_tags: list[str] = []
    else:
        llvm = config["llvm"]
        test_suite = config["test_suite"]
        official = test_suite["official"]
        raja = test_suite["raja"]

        llvm_tags = _ensure_list(llvm["tags"])
        official_tags = _ensure_list(official["tags"])
        raja_tags = _ensure_list(raja["tags"])

    default_platform = project.get("default_platform")

    if raw_experiments:
        normalized_raw_experiments = _normalize_explicit_experiments(
            raw_experiments=raw_experiments,
            default_platform=default_platform,
            label=label,
        )
        experiment_mode = "explicit"
    else:
        normalized_raw_experiments = _normalize_simple_experiments(
            llvm_tags=llvm_tags,
            official_tags=official_tags,
            raja_tags=raja_tags,
            label=label,
        )
        experiment_mode = "simple"

    experiments = _finalize_experiments(normalized_raw_experiments)

    return {
        "project": {
            "base_dir": project["base_dir"],
            "default_platform": default_platform,
        },
        "build": {
            "ninja_jobs": build["ninja_jobs"],
            "clean_build": _parse_bool(build["clean_build"], "build.clean_build"),
            "reconfigure": _parse_bool(build["reconfigure"], "build.reconfigure"),
        },
        "label": label,
        "llvm": {
            "repo_url": repositories["llvm"],
            "tags": llvm_tags,
            "build": {
                "c_compiler": compilers["host"]["c"],
                "cxx_compiler": compilers["host"]["cxx"],
            },
        },
        "test_suite": {
            "official": {
                "repo_url": repositories["official"],
                "tags": official_tags,
                "cxx_standard": str(suite_defaults["official"]["cxx_standard"]),
            },
            "raja": {
                "repo_url": repositories["raja"],
                "tags": raja_tags,
                "cxx_standard": str(suite_defaults["raja"]["cxx_standard"]),
            },
        },
        "test_selection": test_selection,
        "experiments": experiments,
        "experiment_mode": experiment_mode,
    }


def resolve_llvm_version(llvm_tag: str) -> str:
    if "-" in llvm_tag:
        return llvm_tag.split("-", 1)[1]
    return llvm_tag


def get_resolved_tag(
    repo_url: str,
    configured_tag: str,
    status_callback: StatusCallback | None = None,
) -> str:
    if configured_tag.lower() != "latest":
        return configured_tag

    if status_callback:
        status_callback(f"Resolving 'latest' commit hash for {repo_url}...")

    try:
        output = subprocess.check_output(["git", "ls-remote", repo_url, "HEAD"], text=True)
        if output:
            short_hash = output.split()[0][:7]
            if status_callback:
                status_callback(f"Resolved to short hash: {short_hash}")
            return short_hash
    except Exception as e:
        if status_callback:
            status_callback(f"[WARNING] Failed to resolve remote hash. Using fallback 'latest'. Error: {e}")

    return "latest"


def prepare_git_repo(
    repo_url: str,
    target_dir: Path,
    tag_or_branch: str | None,
    run_cmd: RunCommand,
    status_callback: StatusCallback | None = None,
    recursive: bool = False,
) -> bool:
    if not (target_dir / ".git").exists():
        if status_callback:
            status_callback(f"Cloning {repo_url} into {target_dir}...")
        clone_cmd = ["git", "clone"]
        if recursive:
            clone_cmd.append("--recursive")
        clone_cmd.extend([repo_url, str(target_dir)])
        if not run_cmd(clone_cmd, target_dir.parent, None):
            return False

    if tag_or_branch:
        if tag_or_branch.lower() == "latest":
            if not run_cmd(["git", "fetch", "origin"], target_dir, None):
                return False
            if not run_cmd(["git", "remote", "set-head", "origin", "-a"], target_dir, None):
                return False
            if not run_cmd(["git", "reset", "--hard", "origin/HEAD"], target_dir, None):
                return False
        else:
            if not run_cmd(["git", "fetch", "--tags"], target_dir, None):
                return False
            if not run_cmd(["git", "checkout", tag_or_branch], target_dir, None):
                return False

        if recursive and not run_cmd(["git", "submodule", "update", "--init", "--recursive"], target_dir, None):
            return False

    try:
        current_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=target_dir,
            text=True,
        ).strip()
        if status_callback:
            status_callback(f"Repository {target_dir.name} successfully set to commit hash: {current_hash}")
    except subprocess.CalledProcessError:
        if status_callback:
            status_callback(f"[WARNING] Failed to retrieve current commit hash for {target_dir.name}")

    return True
