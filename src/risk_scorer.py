"""
Risk scorer – aggregates signals into a 0-100 risk score.
"""

from __future__ import annotations


class RiskScorer:
    """Computes a composite risk score for a Solana token."""

    # ------------------------------------------------------------------
    # Risk factor weights
    # ------------------------------------------------------------------
    _FACTORS = [
        {
            "id": "mint_authority_not_revoked",
            "points": 25,
            "description": "Mint authority has NOT been revoked – developer can mint unlimited tokens",
        },
        {
            "id": "freeze_authority_not_revoked",
            "points": 20,
            "description": "Freeze authority has NOT been revoked – developer can freeze holder wallets",
        },
        {
            "id": "top10_concentration_high",
            "points": 20,
            "description": "Top 10 holders own >80% of supply – extreme concentration risk",
        },
        {
            "id": "top10_concentration_medium",
            "points": 10,
            "description": "Top 10 holders own 50–80 % of supply – elevated concentration risk",
        },
        {
            "id": "bundler_percentage_high",
            "points": 15,
            "description": "More than 30 % of wallets are bundled – likely coordinated launch",
        },
        {
            "id": "bot_percentage_high",
            "points": 10,
            "description": "More than 50 % of active wallets appear to be bots",
        },
        {
            "id": "no_liquidity_info",
            "points": 10,
            "description": "No liquidity pool information found – token may be illiquid",
        },
        {
            "id": "rugcheck_high_risk",
            "points": 20,
            "description": "RugCheck.xyz flagged this token as high risk (score > 500)",
        },
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        token_data: dict,
        holder_analysis: dict,
        bundle_analysis: dict,
        rugcheck_data: dict,
    ) -> dict:
        """
        Compute the composite risk score.

        Parameters
        ----------
        token_data:       output of DataFetcher.get_token_info()
        holder_analysis:  list of holder dicts from DataFetcher.get_token_largest_accounts()
                          OR a dict with a ``holders`` key
        bundle_analysis:  output of BundlerDetector.detect()
        rugcheck_data:    output of DataFetcher.get_rugcheck_report()

        Returns a dict with total_score, risk_level, factors, and boolean flags.
        """
        # Normalise holder_analysis – accept either a list or a dict wrapper
        if isinstance(holder_analysis, dict):
            holders: list[dict] = holder_analysis.get("holders", [])
        else:
            holders = list(holder_analysis)

        accumulated_points = 0
        triggered_factors: list[dict] = []

        # --- Helper to register a factor ---
        def _add(factor_id: str):
            nonlocal accumulated_points
            for f in self._FACTORS:
                if f["id"] == factor_id:
                    accumulated_points += f["points"]
                    triggered_factors.append(
                        {
                            "name": factor_id,
                            "points": f["points"],
                            "description": f["description"],
                        }
                    )
                    return

        # ── Mint / freeze authority ──────────────────────────────────────
        mint_revoked = bool(token_data.get("mint_authority_revoked", False))
        freeze_revoked = bool(token_data.get("freeze_authority_revoked", False))

        if not mint_revoked:
            _add("mint_authority_not_revoked")
        if not freeze_revoked:
            _add("freeze_authority_not_revoked")

        # ── Holder concentration ─────────────────────────────────────────
        top10_pct = self._top10_concentration(holders)
        if top10_pct > 80:
            _add("top10_concentration_high")
        elif top10_pct > 50:
            _add("top10_concentration_medium")

        # ── Bundler activity ────────────────────────────────────────────
        bundled_pct = bundle_analysis.get("bundled_wallet_percentage", 0.0) if bundle_analysis else 0.0
        if bundled_pct > 30:
            _add("bundler_percentage_high")

        # ── Bot activity ─────────────────────────────────────────────────
        # bot_percentage lives in TraderAnalyzer output; passed via token_data or
        # direct key; handled gracefully if absent.
        bot_pct = float(token_data.get("bot_percentage", 0))
        if bot_pct > 50:
            _add("bot_percentage_high")

        # ── Liquidity info ───────────────────────────────────────────────
        liquidity_locked = self._has_liquidity(rugcheck_data)
        if not liquidity_locked:
            _add("no_liquidity_info")

        # ── RugCheck score ───────────────────────────────────────────────
        rugcheck_score = rugcheck_data.get("score", 0) if rugcheck_data else 0
        if rugcheck_score and rugcheck_score > 500:
            _add("rugcheck_high_risk")

        total_score = min(accumulated_points, 100)

        return {
            "total_score": total_score,
            "risk_level": self._get_risk_level(total_score),
            "factors": triggered_factors,
            "mint_authority_revoked": mint_revoked,
            "freeze_authority_revoked": freeze_revoked,
            "top10_concentration": round(top10_pct, 2),
            "liquidity_locked": liquidity_locked,
            "bot_percentage": bot_pct,
            "bundled_wallet_percentage": bundled_pct,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _top10_concentration(holders: list[dict]) -> float:
        """Sum percentages of the top 10 holders."""
        if not holders:
            return 0.0
        top10 = sorted(holders, key=lambda h: h.get("percentage", 0), reverse=True)[:10]
        return sum(h.get("percentage", 0) for h in top10)

    @staticmethod
    def _has_liquidity(rugcheck_data: dict) -> bool:
        """Return True if RugCheck reports any market/liquidity information."""
        if not rugcheck_data:
            return False
        markets = rugcheck_data.get("markets", [])
        if markets:
            return True
        # Some responses embed liquidity in token info
        token_info = rugcheck_data.get("tokenMeta", rugcheck_data.get("token", {}))
        return bool(token_info.get("markets") or token_info.get("liquidity"))

    @staticmethod
    def _get_risk_level(score: int) -> str:
        """Map score → risk label."""
        if score < 25:
            return "LOW"
        if score < 50:
            return "MEDIUM"
        if score < 75:
            return "HIGH"
        return "CRITICAL"
