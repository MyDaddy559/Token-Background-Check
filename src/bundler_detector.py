"""
Bundler detector – identifies coordinated wallet bundles in transaction data.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class BundlerDetector:
    """Detects groups of wallets that transact together in the same slot (block)."""

    BUNDLE_MIN_SIZE = 3        # min wallets in same slot to call it a bundle
    SUSPICIOUS_MIN_SIZE = 5    # bundles this large are suspicious
    EARLY_SLOT_WINDOW = 10     # first N unique slots are considered "early"

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def detect(self, transactions: list[dict]) -> dict:
        """
        Detect wallet bundles from a list of transactions.

        Returns a dict with: total_bundles, bundle_groups, suspicious_bundles,
        bundled_wallet_percentage.
        """
        if not transactions:
            return self._empty_result()

        slot_groups = self._group_by_slot(transactions)
        bundles = self._identify_bundles(slot_groups)

        # Determine early-launch slots (first EARLY_SLOT_WINDOW unique slots seen)
        all_slots = sorted(slot_groups.keys())
        early_slots: set[Any] = set(all_slots[: self.EARLY_SLOT_WINDOW])

        # Enrich bundles with suspicion flags
        for bundle in bundles:
            bundle["suspicious"] = self._is_suspicious_bundle(bundle, early_slots)

        suspicious_count = sum(1 for b in bundles if b["suspicious"])

        # Compute bundled wallet percentage
        bundled_wallets: set[str] = set()
        for bundle in bundles:
            bundled_wallets.update(bundle["wallets"])

        all_fee_payers: set[str] = set()
        for txn in transactions:
            fp = txn.get("feePayer") or txn.get("fee_payer")
            if fp:
                all_fee_payers.add(fp)

        total_wallets = len(all_fee_payers) or 1
        bundled_pct = round(len(bundled_wallets) / total_wallets * 100, 2)

        return {
            "total_bundles": len(bundles),
            "bundle_groups": bundles,
            "suspicious_bundles": suspicious_count,
            "bundled_wallet_percentage": bundled_pct,
        }

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _group_by_slot(self, transactions: list[dict]) -> dict[Any, list[dict]]:
        """Group transactions by slot number."""
        groups: dict[Any, list[dict]] = defaultdict(list)
        for txn in transactions:
            slot = txn.get("slot")
            if slot is not None:
                groups[slot].append(txn)
        return dict(groups)

    def _identify_bundles(self, slot_groups: dict[Any, list[dict]]) -> list[dict]:
        """
        Return bundles: sets of 3+ wallets all transacting in the same slot.
        """
        bundles: list[dict] = []
        for slot, txns in slot_groups.items():
            wallets: set[str] = set()
            for txn in txns:
                fp = txn.get("feePayer") or txn.get("fee_payer")
                if fp:
                    wallets.add(fp)

            if len(wallets) >= self.BUNDLE_MIN_SIZE:
                bundles.append(
                    {
                        "slot": slot,
                        "wallets": list(wallets),
                        "size": len(wallets),
                        "txn_count": len(txns),
                        "suspicious": False,  # filled in later
                    }
                )

        return sorted(bundles, key=lambda b: b["size"], reverse=True)

    def _is_suspicious_bundle(self, bundle: dict, early_slots: set[Any]) -> bool:
        """
        Flag as suspicious if:
        - Size >= SUSPICIOUS_MIN_SIZE wallets, OR
        - The slot is one of the first EARLY_SLOT_WINDOW slots (launch bundles)
        """
        if bundle["size"] >= self.SUSPICIOUS_MIN_SIZE:
            return True
        if bundle["slot"] in early_slots:
            return True
        return False

    # ---------------------------------------------------------------------------
    # Utility
    # ---------------------------------------------------------------------------

    @staticmethod
    def _empty_result() -> dict:
        return {
            "total_bundles": 0,
            "bundle_groups": [],
            "suspicious_bundles": 0,
            "bundled_wallet_percentage": 0.0,
        }
