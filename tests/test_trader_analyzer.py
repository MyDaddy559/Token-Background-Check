"""
Unit tests for TraderAnalyzer.
"""

from __future__ import annotations

import time
import pytest

from src.trader_analyzer import TraderAnalyzer


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_txn(
    fee_payer: str = "wallet_A",
    timestamp: float | None = None,
    slot: int = 100,
    token_mint: str = "mint123",
    direction: str = "buy",
    amount: float = 100.0,
) -> dict:
    """Build a minimal mock transaction dict."""
    ts = timestamp if timestamp is not None else time.time()
    to_acct = fee_payer if direction == "buy" else ""
    from_acct = "" if direction == "buy" else fee_payer
    return {
        "signature": f"sig_{fee_payer}_{ts}",
        "feePayer": fee_payer,
        "timestamp": ts,
        "slot": slot,
        "tokenTransfers": [
            {
                "mint": token_mint,
                "tokenAmount": amount,
                "toUserAccount": to_acct,
                "fromUserAccount": from_acct,
            }
        ],
    }


def _make_high_freq_txns(wallet: str, count: int = 10, interval_secs: float = 5.0) -> list[dict]:
    """Create high-frequency transactions spaced `interval_secs` apart."""
    base_ts = 1_700_000_000.0
    return [
        _make_txn(fee_payer=wallet, timestamp=base_ts + i * interval_secs, slot=200 + i)
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# Bot detection
# ---------------------------------------------------------------------------

class TestBotDetection:
    def test_bot_detected_high_frequency(self):
        """Wallet with >5 txns and avg interval <30s should be flagged as bot."""
        txns = _make_high_freq_txns("bot_wallet", count=10, interval_secs=5)
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        detail = next(d for d in result["trader_details"] if d["wallet"] == "bot_wallet")
        assert detail["is_bot"] is True
        assert detail["label"] == "bot"

    def test_bot_not_flagged_low_frequency(self):
        """Wallet with adequate spacing between txns should NOT be flagged as bot."""
        base_ts = 1_700_000_000.0
        txns = [
            _make_txn(fee_payer="real_wallet", timestamp=base_ts + i * 120, slot=300 + i)
            for i in range(8)
        ]
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        detail = next(d for d in result["trader_details"] if d["wallet"] == "real_wallet")
        assert detail["is_bot"] is False

    def test_bot_not_flagged_too_few_txns(self):
        """Wallet with <= BOT_MIN_TXNS transactions should never be flagged as bot."""
        txns = _make_high_freq_txns("small_wallet", count=3, interval_secs=1)
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        detail = next(d for d in result["trader_details"] if d["wallet"] == "small_wallet")
        assert detail["is_bot"] is False

    def test_bot_percentage_calculated_correctly(self):
        bot_txns = _make_high_freq_txns("bot1", count=10, interval_secs=2)
        real_txns = [
            _make_txn("real1", timestamp=1_700_000_000.0 + i * 200, slot=500 + i)
            for i in range(8)
        ]
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(bot_txns + real_txns, [])
        # 1 bot out of 2 wallets = 50%
        assert result["bot_percentage"] == 50.0
        assert result["bots"] == 1


# ---------------------------------------------------------------------------
# Wash trader detection
# ---------------------------------------------------------------------------

class TestWashTraderDetection:
    def test_wash_trader_detected(self):
        """Wallet with 2+ buy→sell cycles within 1 hour should be a wash trader."""
        base = 1_700_000_000.0
        txns = []
        # 2 buy→sell cycles with 10-minute gap
        for cycle in range(2):
            offset = cycle * 1200  # 20-min between cycles
            txns.append(_make_txn("wash_wallet", timestamp=base + offset, direction="buy"))
            txns.append(_make_txn("wash_wallet", timestamp=base + offset + 600, direction="sell"))

        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        detail = next(d for d in result["trader_details"] if d["wallet"] == "wash_wallet")
        assert detail["is_wash_trader"] is True
        assert detail["label"] == "wash_trader"

    def test_wash_trader_not_flagged_single_cycle(self):
        """Single buy→sell should not be flagged."""
        base = 1_700_000_000.0
        txns = [
            _make_txn("trader", timestamp=base, direction="buy"),
            _make_txn("trader", timestamp=base + 300, direction="sell"),
        ]
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        detail = next(d for d in result["trader_details"] if d["wallet"] == "trader")
        assert detail["is_wash_trader"] is False

    def test_wash_trader_outside_window_not_flagged(self):
        """Cycles outside the wash window (>1 hr apart) should NOT be flagged."""
        base = 1_700_000_000.0
        txns = []
        # buy then sell 2 hours later – outside wash window
        for cycle in range(2):
            offset = cycle * 7200  # 2 hours between cycles
            txns.append(_make_txn("long_holder", timestamp=base + offset, direction="buy"))
            txns.append(_make_txn("long_holder", timestamp=base + offset + 4000, direction="sell"))
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        detail = next(d for d in result["trader_details"] if d["wallet"] == "long_holder")
        assert detail["is_wash_trader"] is False


# ---------------------------------------------------------------------------
# Sybil detection
# ---------------------------------------------------------------------------

class TestSybilDetection:
    def _make_cluster(self, slot: int, wallets: list[str], amount: float = 50.0) -> list[dict]:
        return [
            _make_txn(fee_payer=w, timestamp=1_700_000_000.0, slot=slot, amount=amount)
            for w in wallets
        ]

    def test_sybil_detected_large_cluster_same_amounts(self):
        """5 wallets in same slot with identical amounts should trigger sybil for each."""
        wallets = [f"wallet_{i}" for i in range(5)]
        txns = self._make_cluster(slot=42, wallets=wallets, amount=100.0)
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        # At least some should be flagged (cluster size = 4 others per wallet >= SYBIL_CLUSTER_SIZE=3)
        sybil_details = [d for d in result["trader_details"] if d["is_sybil"]]
        assert len(sybil_details) > 0

    def test_sybil_not_flagged_small_cluster(self):
        """2 wallets in same slot is too small to trigger sybil."""
        txns = self._make_cluster(slot=99, wallets=["w1", "w2"], amount=100.0)
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        for detail in result["trader_details"]:
            assert detail["is_sybil"] is False

    def test_sybil_not_flagged_varied_amounts(self):
        """Large cluster with varied amounts should NOT be sybil."""
        base_ts = 1_700_000_000.0
        txns = [
            _make_txn(f"wallet_{i}", timestamp=base_ts, slot=50, amount=float(i * 37 + 1))
            for i in range(5)
        ]
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        # With varied amounts, sybil flag should be False
        for d in result["trader_details"]:
            assert d["is_sybil"] is False


# ---------------------------------------------------------------------------
# Real trader classification
# ---------------------------------------------------------------------------

class TestRealTraderClassification:
    def test_real_trader_normal_activity(self):
        """Normal wallet with moderate spacing should be classified as real."""
        base = 1_700_000_000.0
        txns = [
            _make_txn("normal_guy", timestamp=base + i * 3600, slot=1000 + i)
            for i in range(4)
        ]
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        detail = next(d for d in result["trader_details"] if d["wallet"] == "normal_guy")
        assert detail["label"] == "real"
        assert result["real_traders"] >= 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_transactions(self):
        """Empty transaction list should return sensible zero defaults."""
        analyzer = TraderAnalyzer()
        result = analyzer.analyze([], [])
        assert result["total_wallets"] == 0
        assert result["bots"] == 0
        assert result["bot_percentage"] == 0.0
        assert result["trader_details"] == []

    def test_single_transaction(self):
        """Single transaction should not crash and classify the wallet."""
        txns = [_make_txn("lone_wallet")]
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        assert result["total_wallets"] == 1
        assert len(result["trader_details"]) == 1

    def test_transactions_without_timestamps(self):
        """Transactions missing timestamp field should not cause crashes."""
        txns = [{"feePayer": "wallet_notimestamp", "slot": 10, "tokenTransfers": []}]
        analyzer = TraderAnalyzer()
        result = analyzer.analyze(txns, [])
        assert result["total_wallets"] == 1

    def test_returns_expected_keys(self):
        """Result dict must always contain all expected keys."""
        analyzer = TraderAnalyzer()
        result = analyzer.analyze([], [])
        for key in ("total_wallets", "real_traders", "bots", "wash_traders",
                    "sybil_wallets", "trader_details", "bot_percentage"):
            assert key in result, f"Missing key: {key}"
