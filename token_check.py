#!/usr/bin/env python3
"""
Solana Token Guardian Agent – CLI Entry Point

Usage:
    python token_check.py <token_address>
    python token_check.py <token_address> --output-dir ./my_reports
    python token_check.py <token_address> --no-charts
    python token_check.py <token_address> --json-only
    python token_check.py <token_address> --html
"""

from __future__ import annotations

import argparse
import sys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="token_check",
        description="Solana Token Guardian – analyse a token for rug-pull and manipulation risks.",
    )
    parser.add_argument("token_address", help="Solana token mint address to analyse")
    parser.add_argument(
        "--output-dir",
        default=None,
        metavar="DIR",
        help="Override the output directory for reports and charts (default: from .env or ./output)",
    )
    parser.add_argument(
        "--no-charts",
        action="store_true",
        help="Skip chart generation (faster, no matplotlib dependency at runtime)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only write JSON report; skip HTML report and terminal dashboard",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report (in addition to or instead of other outputs)",
    )
    return parser


def _console_print(msg: str, style: str = "") -> None:
    """Print using rich if available, otherwise plain print."""
    try:
        from rich import print as rprint
        rprint(msg)
    except ImportError:
        # Strip basic rich markup for plain output
        import re
        plain = re.sub(r"\[/?[^\]]*\]", "", msg)
        print(plain)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    token_address = args.token_address.strip()

    # ── Load configuration ───────────────────────────────────────────────
    try:
        from src.config import Config
        cfg = Config()
    except EnvironmentError as exc:
        _console_print(f"[bold red]Configuration error:[/bold red] {exc}")
        return 1

    output_dir = args.output_dir or cfg.output_dir

    # ── Fetch data ───────────────────────────────────────────────────────
    _console_print(f"\n[bold cyan]🔍 Analysing token:[/bold cyan] [yellow]{token_address}[/yellow]\n")

    from src.data_fetcher import DataFetcher
    fetcher = DataFetcher(cfg.helius_api_key, cfg.rugcheck_api_key)
    all_data = fetcher.get_all_token_data(token_address)

    token_info: dict = all_data.get("token_info", {})
    holders: list = all_data.get("holders", [])
    transactions: list = all_data.get("transactions", [])
    rugcheck: dict = all_data.get("rugcheck", {})

    # ── Trader analysis ──────────────────────────────────────────────────
    _console_print("[cyan]→ Analysing trader behaviour...[/cyan]")
    from src.trader_analyzer import TraderAnalyzer
    trader_analysis = TraderAnalyzer().analyze(transactions, holders)

    # ── Bundle detection ─────────────────────────────────────────────────
    _console_print("[cyan]→ Detecting wallet bundles...[/cyan]")
    from src.bundler_detector import BundlerDetector
    bundle_analysis = BundlerDetector().detect(transactions)

    # ── Risk scoring ─────────────────────────────────────────────────────
    _console_print("[cyan]→ Computing risk score...[/cyan]")
    from src.risk_scorer import RiskScorer
    # Merge bot_percentage from trader analysis into the token data dict for the scorer
    token_data_with_bot_pct = {**token_info, "bot_percentage": trader_analysis.get("bot_percentage", 0)}
    risk_result = RiskScorer().score(token_data_with_bot_pct, holders, bundle_analysis, rugcheck)

    # ── Visualisations ───────────────────────────────────────────────────
    chart_paths: list[str] = []
    if not args.no_charts:
        _console_print("[cyan]→ Generating charts...[/cyan]")
        from src.visualizer import Visualizer
        viz = Visualizer(output_dir)
        chart_paths = viz.generate_all(
            token_address, trader_analysis, holders, risk_result, bundle_analysis
        )
        for p in chart_paths:
            _console_print(f"  [dim]Chart saved:[/dim] {p}")

    # ── Reports ──────────────────────────────────────────────────────────
    from src.report_generator import ReportGenerator
    reporter = ReportGenerator(output_dir)

    json_path = reporter.generate_json_report(
        token_address, token_info, trader_analysis, bundle_analysis, risk_result, chart_paths
    )
    _console_print(f"\n[green]✓ JSON report:[/green] {json_path}")

    if not args.json_only:
        html_path = reporter.generate_html_report(
            token_address, token_info, trader_analysis, bundle_analysis,
            risk_result, chart_paths
        )
        _console_print(f"[green]✓ HTML report:[/green] {html_path}")

    # ── Terminal dashboard ───────────────────────────────────────────────
    if not args.json_only:
        _console_print("")
        reporter.print_terminal_dashboard(
            token_address, token_info, trader_analysis, bundle_analysis, risk_result
        )

    # ── Exit code ────────────────────────────────────────────────────────
    risk_level = risk_result.get("risk_level", "LOW")
    if risk_level == "CRITICAL":
        _console_print(
            "\n[bold white on red] ⛔  CRITICAL RISK – exercise extreme caution [/bold white on red]\n"
        )
        return 1

    _console_print(f"\n[bold green]✓ Analysis complete.[/bold green]\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
