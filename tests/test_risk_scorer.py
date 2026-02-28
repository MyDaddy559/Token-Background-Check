"""
Unit tests for RiskScorer.
"""

from __future__ import annotations

import pytest

from src.risk_scorer import RiskScorer


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _safe_token(extra: dict | None = None) -> dict:
    """Return a token_data dict representing a safe token."""
    base = {
        "mint_authority_revoked": True,
        "freeze_authority_revoked": True,
        "bot_percentage": 0.0,
    }
    if extra:
        base.update(extra)
    return base


def _holders(percentages: list[float]) -> list[dict]:
    """Build a list of holder dicts from a list of percentages."""
    return [{"address": f"wallet_{i}", "percentage": p} for i, p in enumerate(percentages)]


def _empty_bundle() -> dict:
    return {"bundled_wallet_percentage": 0.0, "total_bundles": 0, "suspicious_bundles": 0, "bundle_groups": []}


def _empty_rugcheck() -> dict:
    return {}


# ---------------------------------------------------------------------------
# Individual factor tests
# ---------------------------------------------------------------------------

class TestMintAuthority:
    def test_mint_not_revoked_adds_25_points(self):
        scorer = RiskScorer()
        result = scorer.score(
            _safe_token({"mint_authority_revoked": False}),
            _holders([1.0] * 10),
            _empty_bundle(),
            _empty_rugcheck(),
        )
        factor_names = [f["name"] for f in result["factors"]]
        assert "mint_authority_not_revoked" in factor_names
        assert result["total_score"] >= 25

    def test_mint_revoked_no_factor(self):
        scorer = RiskScorer()
        result = scorer.score(
            _safe_token({"mint_authority_revoked": True}),
            _holders([1.0] * 10),
            _empty_bundle(),
            _empty_rugcheck(),
        )
        factor_names = [f["name"] for f in result["factors"]]
        assert "mint_authority_not_revoked" not in factor_names

    def test_mint_not_revoked_flag_in_result(self):
        scorer = RiskScorer()
        result = scorer.score(
            _safe_token({"mint_authority_revoked": False}),
            [], _empty_bundle(), _empty_rugcheck(),
        )
        assert result["mint_authority_revoked"] is False


class TestFreezeAuthority:
    def test_freeze_not_revoked_adds_20_points(self):
        scorer = RiskScorer()
        result = scorer.score(
            _safe_token({"freeze_authority_revoked": False}),
            _holders([1.0] * 10),
            _empty_bundle(),
            _empty_rugcheck(),
        )
        factor_names = [f["name"] for f in result["factors"]]
        assert "freeze_authority_not_revoked" in factor_names

    def test_freeze_revoked_no_factor(self):
        scorer = RiskScorer()
        result = scorer.score(
            _safe_token({"freeze_authority_revoked": True}),
            _holders([1.0] * 10),
            _empty_bundle(),
            _empty_rugcheck(),
        )
        factor_names = [f["name"] for f in result["factors"]]
        assert "freeze_authority_not_revoked" not in factor_names


class TestHolderConcentration:
    def test_high_concentration_above_80_adds_20(self):
        """Top 10 holders owning > 80% should add 20 points (high tier)."""
        # 10 holders each with 9% = 90%
        holders = _holders([9.0] * 10)
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), holders, _empty_bundle(), _empty_rugcheck())
        factor_names = [f["name"] for f in result["factors"]]
        assert "top10_concentration_high" in factor_names
        assert "top10_concentration_medium" not in factor_names

    def test_medium_concentration_50_to_80_adds_10(self):
        """Top 10 owning between 50% and 80% should add 10 points (medium tier)."""
        # 10 holders each with 6% = 60%
        holders = _holders([6.0] * 10)
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), holders, _empty_bundle(), _empty_rugcheck())
        factor_names = [f["name"] for f in result["factors"]]
        assert "top10_concentration_medium" in factor_names
        assert "top10_concentration_high" not in factor_names

    def test_low_concentration_no_factor(self):
        """Top 10 owning < 50% should not add concentration factor."""
        holders = _holders([3.0] * 10)  # 30%
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), holders, _empty_bundle(), _empty_rugcheck())
        factor_names = [f["name"] for f in result["factors"]]
        assert "top10_concentration_high" not in factor_names
        assert "top10_concentration_medium" not in factor_names

    def test_top10_concentration_returned_in_result(self):
        holders = _holders([9.0] * 10)
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), holders, _empty_bundle(), _empty_rugcheck())
        assert result["top10_concentration"] == pytest.approx(90.0)


class TestBundlerPercentage:
    def test_high_bundler_percentage_adds_15(self):
        """bundled_wallet_percentage > 30% should add 15 points."""
        bundle = {"bundled_wallet_percentage": 40.0, "total_bundles": 5, "suspicious_bundles": 3, "bundle_groups": []}
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), [], bundle, _empty_rugcheck())
        factor_names = [f["name"] for f in result["factors"]]
        assert "bundler_percentage_high" in factor_names

    def test_low_bundler_percentage_no_factor(self):
        bundle = {"bundled_wallet_percentage": 20.0, "total_bundles": 2, "suspicious_bundles": 0, "bundle_groups": []}
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), [], bundle, _empty_rugcheck())
        factor_names = [f["name"] for f in result["factors"]]
        assert "bundler_percentage_high" not in factor_names


class TestBotPercentage:
    def test_high_bot_percentage_adds_10(self):
        scorer = RiskScorer()
        result = scorer.score(
            _safe_token({"bot_percentage": 60.0}),
            [], _empty_bundle(), _empty_rugcheck(),
        )
        factor_names = [f["name"] for f in result["factors"]]
        assert "bot_percentage_high" in factor_names

    def test_low_bot_percentage_no_factor(self):
        scorer = RiskScorer()
        result = scorer.score(
            _safe_token({"bot_percentage": 30.0}),
            [], _empty_bundle(), _empty_rugcheck(),
        )
        factor_names = [f["name"] for f in result["factors"]]
        assert "bot_percentage_high" not in factor_names


class TestLiquidity:
    def test_no_liquidity_info_adds_10(self):
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), [], _empty_bundle(), {})
        factor_names = [f["name"] for f in result["factors"]]
        assert "no_liquidity_info" in factor_names

    def test_has_liquidity_no_factor(self):
        rugcheck = {"markets": [{"id": "market1"}]}
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), [], _empty_bundle(), rugcheck)
        factor_names = [f["name"] for f in result["factors"]]
        assert "no_liquidity_info" not in factor_names


class TestRugcheckScore:
    def test_rugcheck_high_score_adds_20(self):
        """RugCheck score > 500 should add 20 points."""
        rugcheck = {"score": 750, "markets": [{"id": "m1"}]}
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), [], _empty_bundle(), rugcheck)
        factor_names = [f["name"] for f in result["factors"]]
        assert "rugcheck_high_risk" in factor_names

    def test_rugcheck_low_score_no_factor(self):
        rugcheck = {"score": 200, "markets": [{"id": "m1"}]}
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), [], _empty_bundle(), rugcheck)
        factor_names = [f["name"] for f in result["factors"]]
        assert "rugcheck_high_risk" not in factor_names


# ---------------------------------------------------------------------------
# Combined factors
# ---------------------------------------------------------------------------

class TestCombinedFactors:
    def test_multiple_factors_accumulate(self):
        """Score should be sum of all triggered factors."""
        # mint NOT revoked (+25) + freeze NOT revoked (+20) = 45
        token = {"mint_authority_revoked": False, "freeze_authority_revoked": False, "bot_percentage": 0}
        scorer = RiskScorer()
        result = scorer.score(token, [], _empty_bundle(), _empty_rugcheck())
        assert result["total_score"] >= 45

    def test_score_capped_at_100(self):
        """Score must never exceed 100 regardless of how many factors trigger."""
        # Trigger everything possible
        token = {
            "mint_authority_revoked": False,   # +25
            "freeze_authority_revoked": False,  # +20
            "bot_percentage": 80.0,            # +10
        }
        holders = _holders([9.0] * 10)         # +20 high concentration
        bundle = {"bundled_wallet_percentage": 50.0, "total_bundles": 5, "suspicious_bundles": 5, "bundle_groups": []}  # +15
        rugcheck = {"score": 900}              # +20 rugcheck; no markets → +10 no_liquidity
        scorer = RiskScorer()
        result = scorer.score(token, holders, bundle, rugcheck)
        assert result["total_score"] <= 100

    def test_perfectly_safe_token_scores_zero(self):
        """A fully safe token with liquidity should score 0."""
        token = {"mint_authority_revoked": True, "freeze_authority_revoked": True, "bot_percentage": 0}
        holders = _holders([2.0] * 10)  # 20% concentration
        bundle = _empty_bundle()
        rugcheck = {"score": 100, "markets": [{"id": "m1"}]}
        scorer = RiskScorer()
        result = scorer.score(token, holders, bundle, rugcheck)
        assert result["total_score"] == 0
        assert result["risk_level"] == "LOW"


# ---------------------------------------------------------------------------
# Risk level thresholds
# ---------------------------------------------------------------------------

class TestRiskLevels:
    @pytest.mark.parametrize("score,expected", [
        (0, "LOW"),
        (24, "LOW"),
        (25, "MEDIUM"),
        (49, "MEDIUM"),
        (50, "HIGH"),
        (74, "HIGH"),
        (75, "CRITICAL"),
        (100, "CRITICAL"),
    ])
    def test_risk_level_boundaries(self, score: int, expected: str):
        scorer = RiskScorer()
        assert scorer._get_risk_level(score) == expected

    def test_risk_level_in_result(self):
        scorer = RiskScorer()
        result = scorer.score(
            {"mint_authority_revoked": False, "freeze_authority_revoked": False, "bot_percentage": 0},
            [], _empty_bundle(), _empty_rugcheck(),
        )
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

class TestResultStructure:
    def test_result_contains_required_keys(self):
        scorer = RiskScorer()
        result = scorer.score(_safe_token(), [], _empty_bundle(), _empty_rugcheck())
        for key in (
            "total_score", "risk_level", "factors",
            "mint_authority_revoked", "freeze_authority_revoked",
            "top10_concentration", "liquidity_locked",
        ):
            assert key in result, f"Missing key: {key}"

    def test_factors_have_required_keys(self):
        scorer = RiskScorer()
        result = scorer.score(
            _safe_token({"mint_authority_revoked": False}),
            [], _empty_bundle(), _empty_rugcheck(),
        )
        for f in result["factors"]:
            assert "name" in f
            assert "points" in f
            assert "description" in f
