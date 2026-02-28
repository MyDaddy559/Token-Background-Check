"""
Visualizer – generates PNG charts for token analysis results.
Uses matplotlib for maximum compatibility.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _get_matplotlib():
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
    return plt


class Visualizer:
    """Generates PNG charts and saves them to output_dir."""

    _COLORS = {
        "real": "#4CAF50",
        "bot": "#F44336",
        "wash_trader": "#FF9800",
        "sybil": "#9C27B0",
        "bundle": "#2196F3",
        "risk_low": "#4CAF50",
        "risk_medium": "#FF9800",
        "risk_high": "#F44336",
        "risk_critical": "#B71C1C",
        "bg": "#1e1e2e",
        "fg": "#cdd6f4",
        "grid": "#313244",
    }

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Individual chart methods
    # ------------------------------------------------------------------

    def plot_trader_breakdown(self, trader_analysis: dict) -> str:
        """Pie chart: Real traders vs Bots vs Wash traders vs Sybil."""
        plt = _get_matplotlib()

        labels = []
        sizes = []
        colors = []

        categories = [
            ("Real Traders", "real_traders", self._COLORS["real"]),
            ("Bots", "bots", self._COLORS["bot"]),
            ("Wash Traders", "wash_traders", self._COLORS["wash_trader"]),
            ("Sybil Wallets", "sybil_wallets", self._COLORS["sybil"]),
        ]

        for label, key, color in categories:
            val = trader_analysis.get(key, 0)
            if val > 0:
                labels.append(f"{label}\n({val})")
                sizes.append(val)
                colors.append(color)

        if not sizes:
            sizes = [1]
            labels = ["No Data"]
            colors = ["#555555"]

        fig, ax = plt.subplots(figsize=(7, 5), facecolor=self._COLORS["bg"])
        ax.set_facecolor(self._COLORS["bg"])

        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=140,
            textprops={"color": self._COLORS["fg"], "fontsize": 10},
        )
        for at in autotexts:
            at.set_color(self._COLORS["bg"])
            at.set_fontweight("bold")

        ax.set_title(
            "Trader Classification Breakdown",
            color=self._COLORS["fg"],
            fontsize=13,
            pad=15,
        )

        out_path = str(self.output_dir / "trader_breakdown.png")
        fig.savefig(out_path, bbox_inches="tight", dpi=120, facecolor=self._COLORS["bg"])
        plt.close(fig)
        return out_path

    def plot_holder_distribution(self, holders: list[dict], top_n: int = 10) -> str:
        """Bar chart: Top N holder percentages."""
        plt = _get_matplotlib()

        top = sorted(holders, key=lambda h: h.get("percentage", 0), reverse=True)[:top_n]
        if not top:
            top = [{"address": "No Data", "percentage": 0}]

        addresses = [h["address"][:8] + "…" for h in top]
        percentages = [h.get("percentage", 0) for h in top]

        fig, ax = plt.subplots(figsize=(9, 5), facecolor=self._COLORS["bg"])
        ax.set_facecolor(self._COLORS["bg"])

        bar_colors = [self._COLORS["bundle"]] * len(percentages)
        # Highlight top holder specially
        if percentages:
            bar_colors[0] = self._COLORS["bot"]

        bars = ax.bar(addresses, percentages, color=bar_colors, edgecolor="none")
        ax.bar_label(bars, fmt="%.1f%%", color=self._COLORS["fg"], fontsize=8, padding=3)

        ax.set_xlabel("Wallet Address (truncated)", color=self._COLORS["fg"], fontsize=10)
        ax.set_ylabel("Supply %", color=self._COLORS["fg"], fontsize=10)
        ax.set_title(f"Top {top_n} Holder Distribution", color=self._COLORS["fg"], fontsize=13)
        ax.tick_params(colors=self._COLORS["fg"])
        ax.spines[:].set_color(self._COLORS["grid"])
        ax.yaxis.grid(True, color=self._COLORS["grid"], linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        plt.xticks(rotation=30, ha="right")

        out_path = str(self.output_dir / "holder_distribution.png")
        fig.savefig(out_path, bbox_inches="tight", dpi=120, facecolor=self._COLORS["bg"])
        plt.close(fig)
        return out_path

    def plot_risk_factors(self, risk_result: dict) -> str:
        """Horizontal bar chart: Risk factor point contributions."""
        plt = _get_matplotlib()

        factors = risk_result.get("factors", [])
        if not factors:
            factors = [{"name": "No risk factors triggered", "points": 0}]

        names = [f["name"].replace("_", " ").title() for f in factors]
        points = [f["points"] for f in factors]

        # Colour based on severity
        bar_colors = []
        for p in points:
            if p >= 20:
                bar_colors.append(self._COLORS["risk_critical"])
            elif p >= 15:
                bar_colors.append(self._COLORS["risk_high"])
            elif p >= 10:
                bar_colors.append(self._COLORS["risk_medium"])
            else:
                bar_colors.append(self._COLORS["risk_low"])

        fig, ax = plt.subplots(figsize=(9, max(4, len(names) * 0.6 + 1)), facecolor=self._COLORS["bg"])
        ax.set_facecolor(self._COLORS["bg"])

        bars = ax.barh(names, points, color=bar_colors, edgecolor="none")
        ax.bar_label(bars, fmt="+%d pts", color=self._COLORS["fg"], fontsize=9, padding=4)

        total = risk_result.get("total_score", 0)
        level = risk_result.get("risk_level", "UNKNOWN")
        ax.set_title(
            f"Risk Factors  │  Total: {total}/100  ({level})",
            color=self._COLORS["fg"],
            fontsize=12,
        )
        ax.set_xlabel("Points", color=self._COLORS["fg"], fontsize=10)
        ax.tick_params(colors=self._COLORS["fg"])
        ax.spines[:].set_color(self._COLORS["grid"])
        ax.xaxis.grid(True, color=self._COLORS["grid"], linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)

        out_path = str(self.output_dir / "risk_factors.png")
        fig.savefig(out_path, bbox_inches="tight", dpi=120, facecolor=self._COLORS["bg"])
        plt.close(fig)
        return out_path

    def plot_bundle_groups(self, bundle_analysis: dict) -> str:
        """Bar chart: Bundle group sizes."""
        plt = _get_matplotlib()

        groups = bundle_analysis.get("bundle_groups", [])[:15]  # show top 15

        if not groups:
            fig, ax = plt.subplots(figsize=(6, 3), facecolor=self._COLORS["bg"])
            ax.set_facecolor(self._COLORS["bg"])
            ax.text(
                0.5, 0.5, "No bundles detected", ha="center", va="center",
                transform=ax.transAxes, color=self._COLORS["fg"], fontsize=12,
            )
            ax.set_title("Bundle Groups", color=self._COLORS["fg"], fontsize=13)
            ax.axis("off")
            out_path = str(self.output_dir / "bundle_groups.png")
            fig.savefig(out_path, bbox_inches="tight", dpi=120, facecolor=self._COLORS["bg"])
            plt.close(fig)
            return out_path

        x_labels = [f"Slot {g['slot']}" for g in groups]
        sizes = [g["size"] for g in groups]
        bar_colors = [
            self._COLORS["risk_critical"] if g.get("suspicious") else self._COLORS["bundle"]
            for g in groups
        ]

        fig, ax = plt.subplots(figsize=(max(6, len(groups) * 0.8), 5), facecolor=self._COLORS["bg"])
        ax.set_facecolor(self._COLORS["bg"])

        bars = ax.bar(x_labels, sizes, color=bar_colors, edgecolor="none")
        ax.bar_label(bars, color=self._COLORS["fg"], fontsize=8, padding=3)

        ax.set_xlabel("Slot", color=self._COLORS["fg"], fontsize=10)
        ax.set_ylabel("Wallets in Bundle", color=self._COLORS["fg"], fontsize=10)
        ax.set_title("Bundle Groups (red = suspicious)", color=self._COLORS["fg"], fontsize=12)
        ax.tick_params(colors=self._COLORS["fg"])
        ax.spines[:].set_color(self._COLORS["grid"])
        ax.yaxis.grid(True, color=self._COLORS["grid"], linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)
        plt.xticks(rotation=30, ha="right")

        out_path = str(self.output_dir / "bundle_groups.png")
        fig.savefig(out_path, bbox_inches="tight", dpi=120, facecolor=self._COLORS["bg"])
        plt.close(fig)
        return out_path

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def generate_all(
        self,
        token_address: str,
        trader_analysis: dict,
        holders: list[dict],
        risk_result: dict,
        bundle_analysis: dict,
    ) -> list[str]:
        """Generate all charts and return list of file paths."""
        paths: list[str] = []
        try:
            paths.append(self.plot_trader_breakdown(trader_analysis))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] trader breakdown chart failed: {exc}")
        try:
            paths.append(self.plot_holder_distribution(holders))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] holder distribution chart failed: {exc}")
        try:
            paths.append(self.plot_risk_factors(risk_result))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] risk factors chart failed: {exc}")
        try:
            paths.append(self.plot_bundle_groups(bundle_analysis))
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] bundle groups chart failed: {exc}")
        return paths
