"""
Param Constraint Validator — validates proposed params against the causal graph.

Deterministic module: loads the causal graph YAML and checks that proposed
parameter values are within bounds and in the correct direction.
Runs AFTER proposal generation, BEFORE storage.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger("design-agent.param_validator")

_CAUSAL_GRAPH_PATH = Path(__file__).resolve().parent / "causal_graph.yaml"

_graph_cache: dict | None = None


def _load_graph() -> dict:
    """Load and cache the causal graph YAML."""
    global _graph_cache
    if _graph_cache is not None:
        return _graph_cache
    try:
        with open(_CAUSAL_GRAPH_PATH, encoding="utf-8") as f:
            _graph_cache = yaml.safe_load(f)
        return _graph_cache or {}
    except Exception:
        logger.warning("Failed to load causal graph", exc_info=True)
        return {}


def validate_params(params: dict[str, str], active_params: dict[str, dict]) -> dict:
    """Validate proposed params against causal graph constraints.

    Args:
        params: Proposed parameter overrides (e.g. {"S3_RECOVER_POLL_SEC": "0.5"}).
        active_params: Current active params per scenario
            (e.g. {"S3": {"S3_RECOVER_POLL_SEC": "1"}}).

    Returns:
        Dict with 'valid', 'errors', 'warnings', and 'adjustments' lists.
    """
    graph = _load_graph()
    param_defs = graph.get("parameters", {})

    errors: list[str] = []
    warnings: list[str] = []
    adjustments: list[dict] = []

    for param_name, proposed_str in params.items():
        pdef = param_defs.get(param_name)
        if not pdef:
            warnings.append(f"Unknown param {param_name} — not in causal graph")
            continue

        # Skip non-numeric params (e.g. S2_PLATFORM)
        if pdef.get("type") == "enum":
            allowed = pdef.get("allowed_values", [])
            if proposed_str not in allowed:
                errors.append(
                    f"{param_name}={proposed_str} not in allowed values {allowed}"
                )
            continue

        try:
            proposed = float(proposed_str)
        except (ValueError, TypeError):
            errors.append(f"{param_name}={proposed_str} is not a valid number")
            continue

        # Bounds check
        bounds = pdef.get("bounds", [])
        if len(bounds) == 2:
            lo, hi = bounds
            if proposed < lo:
                errors.append(
                    f"{param_name}={proposed} below minimum {lo}"
                )
                adjustments.append({
                    "param": param_name,
                    "proposed": proposed,
                    "adjusted_to": lo,
                    "reason": f"clamped to minimum bound",
                })
            elif proposed > hi:
                errors.append(
                    f"{param_name}={proposed} above maximum {hi}"
                )
                adjustments.append({
                    "param": param_name,
                    "proposed": proposed,
                    "adjusted_to": hi,
                    "reason": f"clamped to maximum bound",
                })

        # Direction check — proposed should be BETTER than current
        direction = pdef.get("param_direction", "")
        scenario = pdef.get("scenario", "")
        current_params = active_params.get(scenario, {})
        current_str = current_params.get(param_name)

        if current_str and direction:
            try:
                current = float(current_str)
            except (ValueError, TypeError):
                continue

            if direction == "LOWER_IS_BETTER" and proposed > current:
                errors.append(
                    f"{param_name}: proposed {proposed} > current {current} "
                    f"but direction is LOWER_IS_BETTER (would worsen metric)"
                )
            elif direction == "HIGHER_IS_BETTER" and proposed < current:
                errors.append(
                    f"{param_name}: proposed {proposed} < current {current} "
                    f"but direction is HIGHER_IS_BETTER (would worsen metric)"
                )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "adjustments": adjustments,
    }


def get_causal_context() -> str:
    """Return a human-readable summary of the causal graph for LLM context.

    This is injected into the build_context output so the LLM knows
    the causal relationships between params and metrics.
    """
    graph = _load_graph()
    param_defs = graph.get("parameters", {})
    overhead = graph.get("architectural_overhead", {})

    lines = ["## Parameter-Metric Causal Relationships\n"]

    for param_name, pdef in param_defs.items():
        scenario = pdef.get("scenario", "?")
        direction = pdef.get("param_direction", "?")
        bounds = pdef.get("bounds", [])
        current_seed = pdef.get("current_seed", "?")
        baseline = pdef.get("baseline_value", "?")
        variants = pdef.get("affects_variants", [])

        lines.append(f"### {param_name} (Scenario {scenario})")
        lines.append(f"- Direction: {direction}")
        lines.append(f"- Baseline: {baseline}, Current: {current_seed}")
        if bounds:
            lines.append(f"- Bounds: [{bounds[0]}, {bounds[1]}]")
        lines.append(f"- Affects variants: {', '.join(variants)}")

        for effect in pdef.get("affects", []):
            metric = effect.get("metric", "?")
            max_impact = effect.get("max_expected_impact_pct", "?")
            mechanism = effect.get("mechanism", "").strip()
            bottleneck = effect.get("bottleneck_note", "").strip()

            lines.append(f"  - → {metric}: max -{max_impact}%")
            if mechanism:
                lines.append(f"    Mechanism: {mechanism[:200]}")
            if bottleneck:
                lines.append(f"    ⚠️ BOTTLENECK: {bottleneck[:200]}")

        note = pdef.get("note", "")
        if note:
            lines.append(f"  NOTE: {note}")
        lines.append("")

    # Architectural overhead
    if overhead:
        lines.append("## Architectural Overhead (NOT tunable by params)\n")
        for name, odef in overhead.items():
            desc = odef.get("description", "")
            latency = odef.get("typical_latency_sec", "?")
            lines.append(f"### {name}")
            lines.append(f"- {desc}")
            lines.append(f"- Typical latency: {latency}s")
            for effect in odef.get("affects", []):
                metric = effect.get("metric", "?")
                variant = effect.get("variant", "?")
                pct = effect.get("overhead_pct", "?")
                explanation = effect.get("explanation", "")
                lines.append(f"  - {metric} ({variant}): {pct} — {explanation[:150]}")
            note = odef.get("note", "").strip()
            if note:
                lines.append(f"  ⚠️ {note[:300]}")
            lines.append("")

    return "\n".join(lines)
