"""
Trader analyzer – classifies wallets as real traders, bots, wash traders, or sybil wallets.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class TraderAnalyzer:
    """Analyses on-chain transaction data to classify wallet behaviour."""

    # Thresholds
    BOT_MIN_TXNS = 5
    BOT_AVG_INTERVAL_SECS = 30      # avg seconds between txns to flag as bot
    WASH_WINDOW_SECS = 3600         # 1-hour window for wash trading check
    WASH_MIN_CYCLES = 2             # min buy+sell round-trips to flag wash trader
    SYBIL_CLUSTER_SIZE = 3          # how many co-appearing wallets triggers sybil flag

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def analyze(self, transactions: list[dict], holders: list[dict]) -> dict:
        """
        Classify wallets and return aggregated analysis.

        Returns a dict with keys: total_wallets, real_traders, bots,
        wash_traders, sybil_wallets, trader_details, bot_percentage.
        """
        if not transactions:
            return self._empty_result()

        # Build per-wallet transaction lists
        wallet_txns: dict[str, list[dict]] = defaultdict(list)
        for txn in transactions:
            fee_payer = txn.get("feePayer") or txn.get("fee_payer")
            if fee_payer:
                wallet_txns[fee_payer].append(txn)

            # Also capture wallets mentioned in token transfers so we track
            # all participating addresses, even those that aren't the fee payer.
            for transfer in txn.get("tokenTransfers", []):
                for key in ("fromUserAccount", "toUserAccount"):
                    addr = transfer.get(key)
                    if addr and addr not in wallet_txns:
                        wallet_txns[addr]  # initialize empty list via defaultdict

        all_wallets = list(wallet_txns.keys())
        details: list[dict] = []
        counts = {"real": 0, "bot": 0, "wash_trader": 0, "sybil": 0}

        for wallet, txns in wallet_txns.items():
            is_bot = self._is_bot(txns)
            is_wash = self._is_wash_trader(txns, transactions)
            is_sybil = self._is_sybil(wallet, all_wallets, transactions)

            if is_bot:
                label = "bot"
            elif is_wash:
                label = "wash_trader"
            elif is_sybil:
                label = "sybil"
            else:
                label = "real"

            counts[label] += 1
            details.append(
                {
                    "wallet": wallet,
                    "label": label,
                    "txn_count": len(txns),
                    "is_bot": is_bot,
                    "is_wash_trader": is_wash,
                    "is_sybil": is_sybil,
                }
            )

        total = len(all_wallets) or 1  # avoid division by zero
        bot_pct = round((counts["bot"] / total) * 100, 2)

        return {
            "total_wallets": len(all_wallets),
            "real_traders": counts["real"],
            "bots": counts["bot"],
            "wash_traders": counts["wash_trader"],
            "sybil_wallets": counts["sybil"],
            "trader_details": details,
            "bot_percentage": bot_pct,
        }

    # ---------------------------------------------------------------------------
    # Classification helpers
    # ---------------------------------------------------------------------------

    def _is_bot(self, wallet_txns: list[dict]) -> bool:
        """
        Flag as bot if:
        - More than BOT_MIN_TXNS transactions, AND
        - Average interval between consecutive transactions < BOT_AVG_INTERVAL_SECS
        """
        if len(wallet_txns) <= self.BOT_MIN_TXNS:
            return False

        timestamps = sorted(
            t for t in (txn.get("timestamp") for txn in wallet_txns) if t is not None
        )
        if len(timestamps) < 2:
            return False

        intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        avg_interval = sum(intervals) / len(intervals)
        return avg_interval < self.BOT_AVG_INTERVAL_SECS

    def _is_wash_trader(self, wallet_txns: list[dict], all_txns: list[dict]) -> bool:  # noqa: ARG002
        """
        Flag as wash trader if a wallet both bought and sold the same token
        multiple times within a short window.
        """
        if len(wallet_txns) < self.WASH_MIN_CYCLES * 2:
            return False

        # Build timeline of buy/sell events per token
        events: dict[str, list[dict]] = defaultdict(list)
        for txn in wallet_txns:
            ts = txn.get("timestamp")
            if ts is None:
                continue
            for transfer in txn.get("tokenTransfers", []):
                mint = transfer.get("mint")
                if not mint:
                    continue
                direction = "buy" if transfer.get("toUserAccount") else "sell"
                events[mint].append({"ts": ts, "dir": direction})

        for mint_events in events.values():
            sorted_events = sorted(mint_events, key=lambda e: e["ts"])
            cycles = self._count_buy_sell_cycles(sorted_events)
            if cycles >= self.WASH_MIN_CYCLES:
                return True

        return False

    def _count_buy_sell_cycles(self, events: list[dict]) -> int:
        """Count completed buy→sell cycles within the wash trading window."""
        cycles = 0
        bought_at: float | None = None
        for ev in events:
            if ev["dir"] == "buy":
                bought_at = ev["ts"]
            elif ev["dir"] == "sell" and bought_at is not None:
                if ev["ts"] - bought_at <= self.WASH_WINDOW_SECS:
                    cycles += 1
                    bought_at = None  # reset after completing cycle
        return cycles

    def _is_sybil(self, wallet: str, all_wallets: list[str], transactions: list[dict]) -> bool:
        """
        Flag as sybil if this wallet co-appears (same block/slot) with
        SYBIL_CLUSTER_SIZE or more other wallets that also share identical transfer amounts.
        """
        # Group transactions by slot
        slot_wallets: dict[Any, set[str]] = defaultdict(set)
        slot_amounts: dict[Any, list[float]] = defaultdict(list)

        for txn in transactions:
            slot = txn.get("slot")
            fp = txn.get("feePayer") or txn.get("fee_payer")
            if slot is None or not fp:
                continue
            slot_wallets[slot].add(fp)
            for transfer in txn.get("tokenTransfers", []):
                amt = transfer.get("tokenAmount")
                if amt is not None:
                    try:
                        slot_amounts[slot].append(float(amt))
                    except (TypeError, ValueError):
                        pass

        # Check if this wallet appears in any slot with enough co-wallets + same amounts
        for slot, wallets_in_slot in slot_wallets.items():
            if wallet not in wallets_in_slot:
                continue
            others = wallets_in_slot - {wallet}
            if len(others) < self.SYBIL_CLUSTER_SIZE:
                continue
            # Check for identical amounts (sybil clusters tend to transact exact same amounts)
            amounts = slot_amounts.get(slot, [])
            if amounts and len(amounts) > 1:
                unique_amounts = set(amounts)
                # If 80%+ of amounts are the same value, suspicious
                if len(unique_amounts) <= max(1, len(amounts) // 5):
                    return True

        return False

    # ---------------------------------------------------------------------------
    # Utility
    # ---------------------------------------------------------------------------

    @staticmethod
    def _empty_result() -> dict:
        return {
            "total_wallets": 0,
            "real_traders": 0,
            "bots": 0,
            "wash_traders": 0,
            "sybil_wallets": 0,
            "trader_details": [],
            "bot_percentage": 0.0,
        }
