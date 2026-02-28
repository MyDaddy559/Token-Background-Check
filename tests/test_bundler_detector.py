"""
Unit tests for BundlerDetector.
"""

from __future__ import annotations

import pytest

from src.bundler_detector import BundlerDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_txn(fee_payer: str, slot: int, amount: float = 100.0) -> dict:
    return {
        "feePayer": fee_payer,
        "slot": slot,
        "timestamp": 1_700_000_000.0,
        "tokenTransfers": [
            {
                "mint": "token_mint_123",
                "tokenAmount": amount,
                "toUserAccount": fee_payer,
                "fromUserAccount": "",
            }
        ],
    }


def _make_bundle(slot: int, size: int, amount: float = 100.0) -> list[dict]:
    """Create `size` transactions from distinct wallets all in the same slot."""
    return [_make_txn(f"wallet_{slot}_{i}", slot=slot, amount=amount) for i in range(size)]


# ---------------------------------------------------------------------------
# Bundle detection
# ---------------------------------------------------------------------------

class TestBundleDetection:
    def test_detects_bundle_same_slot(self):
        """3+ wallets in the same slot should form a bundle."""
        txns = _make_bundle(slot=500, size=4)
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["total_bundles"] == 1
        assert result["bundle_groups"][0]["size"] == 4
        assert result["bundle_groups"][0]["slot"] == 500

    def test_no_bundle_single_wallet_per_slot(self):
        """Only one wallet per slot → no bundles."""
        txns = [_make_txn(f"wallet_{i}", slot=i) for i in range(10)]
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["total_bundles"] == 0

    def test_no_bundle_two_wallets_per_slot(self):
        """Two wallets per slot is below the BUNDLE_MIN_SIZE threshold (3)."""
        txns = _make_bundle(slot=100, size=2)
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["total_bundles"] == 0

    def test_multiple_bundles_different_slots(self):
        """Bundles in different slots are counted separately."""
        txns = _make_bundle(slot=1, size=3) + _make_bundle(slot=2, size=5)
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["total_bundles"] == 2

    def test_bundle_wallets_list_correct(self):
        """bundle_groups entry should list all wallets."""
        wallets = [f"wallet_{i}" for i in range(4)]
        txns = [_make_txn(w, slot=77) for w in wallets]
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert len(result["bundle_groups"]) == 1
        detected_wallets = set(result["bundle_groups"][0]["wallets"])
        assert detected_wallets == set(wallets)


# ---------------------------------------------------------------------------
# Suspicious bundle flagging
# ---------------------------------------------------------------------------

class TestSuspiciousBundleFlagging:
    def test_large_bundle_is_suspicious(self):
        """Bundle with >= 5 wallets should be flagged suspicious."""
        txns = _make_bundle(slot=200, size=6)
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["bundle_groups"][0]["suspicious"] is True
        assert result["suspicious_bundles"] == 1

    def test_small_bundle_not_suspicious_if_late(self):
        """Bundle with 3 wallets in a late slot (not in first 10) should not be suspicious."""
        # Create 11+ unique slots before the bundle to push it out of early window
        early_txns = [_make_txn(f"solo_{i}", slot=i) for i in range(11)]
        late_bundle = _make_bundle(slot=999, size=3)
        txns = early_txns + late_bundle
        detector = BundlerDetector()
        result = detector.detect(txns)
        late_group = next(g for g in result["bundle_groups"] if g["slot"] == 999)
        assert late_group["suspicious"] is False

    def test_early_slot_bundle_is_suspicious(self):
        """Bundle in one of the first 10 slots should be flagged suspicious."""
        txns = _make_bundle(slot=1, size=3)  # slot 1 is early
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["bundle_groups"][0]["suspicious"] is True

    def test_suspicious_bundles_count(self):
        """suspicious_bundles count reflects only flagged groups."""
        txns = (
            _make_bundle(slot=1, size=6)   # suspicious (early + large)
            + _make_bundle(slot=2, size=3)  # suspicious (early)
        )
        # Push these into early slots by not adding other transactions first
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["suspicious_bundles"] == 2


# ---------------------------------------------------------------------------
# Bundled wallet percentage
# ---------------------------------------------------------------------------

class TestBundledWalletPercentage:
    def test_percentage_calculation(self):
        """bundled_wallet_percentage should reflect bundled wallets / total wallets."""
        # 4 bundled wallets + 1 solo wallet = 80%
        bundled = _make_bundle(slot=10, size=4)
        solo = [_make_txn("solo_wallet", slot=20)]
        txns = bundled + solo
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["bundled_wallet_percentage"] == pytest.approx(80.0)

    def test_zero_percentage_no_bundles(self):
        """With no bundles, bundled_wallet_percentage should be 0."""
        txns = [_make_txn(f"w{i}", slot=i) for i in range(5)]
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["bundled_wallet_percentage"] == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_transactions(self):
        detector = BundlerDetector()
        result = detector.detect([])
        assert result["total_bundles"] == 0
        assert result["bundle_groups"] == []
        assert result["suspicious_bundles"] == 0
        assert result["bundled_wallet_percentage"] == 0.0

    def test_transactions_without_slot(self):
        """Transactions missing slot field should not crash."""
        txns = [{"feePayer": "wallet_no_slot", "tokenTransfers": []}]
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["total_bundles"] == 0

    def test_returns_expected_keys(self):
        detector = BundlerDetector()
        result = detector.detect([])
        for key in ("total_bundles", "bundle_groups", "suspicious_bundles",
                    "bundled_wallet_percentage"):
            assert key in result, f"Missing key: {key}"

    def test_bundle_groups_sorted_by_size_desc(self):
        """bundle_groups should be sorted largest first."""
        txns = _make_bundle(slot=1, size=3) + _make_bundle(slot=2, size=7)
        detector = BundlerDetector()
        result = detector.detect(txns)
        sizes = [g["size"] for g in result["bundle_groups"]]
        assert sizes == sorted(sizes, reverse=True)

    def test_duplicate_fee_payer_in_same_slot(self):
        """Same wallet appearing in multiple txns in same slot should count once."""
        txns = [
            _make_txn("wallet_A", slot=5),
            _make_txn("wallet_A", slot=5),  # duplicate
            _make_txn("wallet_B", slot=5),
            _make_txn("wallet_C", slot=5),
        ]
        detector = BundlerDetector()
        result = detector.detect(txns)
        assert result["bundle_groups"][0]["size"] == 3  # 3 unique wallets
