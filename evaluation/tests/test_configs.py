"""Tests for evaluation.configs — config loading."""

from __future__ import annotations

from evaluation.configs import load_experiment_matrix, load_thresholds


class TestExperimentMatrix:
    """Validate experiment_matrix.json structure and content."""

    def test_loads_successfully(self) -> None:
        matrix = load_experiment_matrix()
        assert "scenarios" in matrix
        assert "variants" in matrix

    def test_contains_all_scenarios(self) -> None:
        matrix = load_experiment_matrix()
        expected = {"s1", "s2", "s3", "s4", "s5", "ss1", "ss2"}
        assert set(matrix["scenarios"].keys()) == expected

    def test_all_variants_defined(self) -> None:
        matrix = load_experiment_matrix()
        assert set(matrix["variants"]) == {
            "baseline",
            "design_only",
            "runtime_only",
            "full",
        }

    def test_each_scenario_has_metrics(self) -> None:
        matrix = load_experiment_matrix()
        for sid, cfg in matrix["scenarios"].items():
            assert "metrics" in cfg, f"{sid} missing 'metrics'"
            assert len(cfg["metrics"]) > 0, f"{sid} has empty metrics list"

    def test_each_scenario_has_stages_with_direction(self) -> None:
        matrix = load_experiment_matrix()
        for sid, cfg in matrix["scenarios"].items():
            assert "stages" in cfg, f"{sid} missing 'stages'"
            for metric_name, stage_cfg in cfg["stages"].items():
                has_stage = "stage" in stage_cfg or "stages" in stage_cfg
                assert has_stage, f"{sid}/{metric_name} missing 'stage' or 'stages'"
                has_direction = (
                    "lower_is_better" in stage_cfg or "higher_is_better" in stage_cfg
                )
                assert has_direction, f"{sid}/{metric_name} missing direction flag"

    def test_focus_tiers_defined(self) -> None:
        matrix = load_experiment_matrix()
        assert "focus_tiers" in matrix
        tiers = matrix["focus_tiers"]
        assert "full_dual_model" in tiers
        assert "design_focus" in tiers
        assert "runtime_focus" in tiers


class TestThresholds:
    """Validate thresholds.json structure and values."""

    def test_loads_successfully(self) -> None:
        thresholds = load_thresholds()
        assert "statistical" in thresholds
        assert "practical" in thresholds

    def test_statistical_defaults(self) -> None:
        thresholds = load_thresholds()
        stat = thresholds["statistical"]
        assert stat["alpha"] == 0.05
        assert stat["min_samples_per_variant"] == 10

    def test_effect_size_thresholds(self) -> None:
        thresholds = load_thresholds()
        es = thresholds["statistical"]["effect_size"]
        assert es["small"] == 0.2
        assert es["medium"] == 0.5
        assert es["large"] == 0.8

    def test_practical_thresholds_have_meaningful_delta(self) -> None:
        thresholds = load_thresholds()
        for metric_name, cfg in thresholds["practical"].items():
            assert (
                "meaningful_delta_pct" in cfg
            ), f"{metric_name} missing delta threshold"
            assert isinstance(cfg["meaningful_delta_pct"], (int, float))
