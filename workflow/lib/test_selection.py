from typing import Any


def _parse_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list of strings, got {type(value).__name__}.")
    return [str(item) for item in value]


def _parse_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be a mapping, got {type(value).__name__}.")
    return value


def _build_official_lit_args(raw_official: dict[str, Any]) -> list[str]:
    lit_args: list[str] = []

    for pattern in _parse_string_list(
        raw_official.get("filters", []),
        "test_selection.official.filters",
    ):
        lit_args.extend(["--filter", pattern])

    for pattern in _parse_string_list(
        raw_official.get("exclude_filters", []),
        "test_selection.official.exclude_filters",
    ):
        lit_args.extend(["--filter-out", pattern])

    lit_args.extend(
        _parse_string_list(
            raw_official.get("lit_args", []),
            "test_selection.official.lit_args",
        )
    )
    return lit_args


def _build_raja_extra_args(raw_raja: dict[str, Any]) -> list[str]:
    extra_args: list[str] = []

    kernels = _parse_string_list(
        raw_raja.get("kernels", []),
        "test_selection.raja.kernels",
    )
    if kernels:
        extra_args.extend(["--kernels", *kernels])

    extra_args.extend(
        _parse_string_list(
            raw_raja.get("extra_args", []),
            "test_selection.raja.extra_args",
        )
    )
    return extra_args


def normalize_test_selection(config: dict[str, Any]) -> dict[str, Any]:
    raw_selection = _parse_mapping(config.get("test_selection", {}), "test_selection")
    raw_official = _parse_mapping(raw_selection.get("official", {}), "test_selection.official")
    raw_raja = _parse_mapping(raw_selection.get("raja", {}), "test_selection.raja")

    official_filters = _parse_string_list(
        raw_official.get("filters", []),
        "test_selection.official.filters",
    )
    official_lit_args = _parse_string_list(
        raw_official.get("lit_args", []),
        "test_selection.official.lit_args",
    )
    official_exclude_filters = _parse_string_list(
        raw_official.get("exclude_filters", []),
        "test_selection.official.exclude_filters",
    )
    raja_kernels = _parse_string_list(
        raw_raja.get("kernels", []),
        "test_selection.raja.kernels",
    )
    raja_extra_args = _parse_string_list(
        raw_raja.get("extra_args", []),
        "test_selection.raja.extra_args",
    )

    return {
        "official": {
            "filters": official_filters,
            "exclude_filters": official_exclude_filters,
            "lit_args": official_lit_args,
            "resolved_lit_args": _build_official_lit_args(raw_official),
        },
        "raja": {
            "kernels": raja_kernels,
            "extra_args": raja_extra_args,
            "resolved_extra_args": _build_raja_extra_args(raw_raja),
        },
    }
