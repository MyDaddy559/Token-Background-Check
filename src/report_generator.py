"""
Report generator – produces JSON, HTML, and rich terminal dashboard outputs.
"""

from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path


class ReportGenerator:
    """Generates analysis reports in multiple formats."""

    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # JSON report
    # ------------------------------------------------------------------

    def generate_json_report(
        self,
        token_address: str,
        token_info: dict,
        trader_analysis: dict,
        bundle_analysis: dict,
        risk_result: dict,
        chart_paths: list[str],
    ) -> str:
        """Write a JSON report and return the file path."""
        report = {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "token_address": token_address,
            "token_info": token_info,
            "risk": risk_result,
            "trader_analysis": {
                k: v for k, v in trader_analysis.items() if k != "trader_details"
            },
            "bundle_analysis": {
                k: v for k, v in bundle_analysis.items() if k != "bundle_groups"
            },
            "bundle_groups_preview": bundle_analysis.get("bundle_groups", [])[:5],
            "chart_files": chart_paths,
        }

        filename = f"report_{token_address[:8]}_{self._ts()}.json"
        out_path = self.output_dir / filename
        out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return str(out_path)

    # ------------------------------------------------------------------
    # HTML report
    # ------------------------------------------------------------------

    def generate_html_report(
        self,
        token_address: str,
        token_info: dict,
        trader_analysis: dict,
        bundle_analysis: dict,
        risk_result: dict,
        chart_paths: list[str],
    ) -> str:
        """Generate a self-contained dark-theme HTML report and return the file path."""
        charts_html = ""
        for path in chart_paths:
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    b64 = base64.b64encode(fh.read()).decode()
                label = Path(path).stem.replace("_", " ").title()
                charts_html += (
                    f'<div class="chart-card">'
                    f'<h3>{label}</h3>'
                    f'<img src="data:image/png;base64,{b64}" alt="{label}">'
                    f"</div>\n"
                )

        risk_level = risk_result.get("risk_level", "UNKNOWN")
        risk_color = {
            "LOW": "#4CAF50",
            "MEDIUM": "#FF9800",
            "HIGH": "#F44336",
            "CRITICAL": "#B71C1C",
        }.get(risk_level, "#888")

        factors_rows = ""
        for f in risk_result.get("factors", []):
            factors_rows += (
                f"<tr><td>{f['name']}</td>"
                f"<td style='color:#ff6b6b'>+{f['points']}</td>"
                f"<td>{f['description']}</td></tr>\n"
            )

        token_name = token_info.get("name", "Unknown")
        token_symbol = token_info.get("symbol", "???")
        total_score = risk_result.get("total_score", 0)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Token Guardian – {token_symbol} ({token_address[:8]}…)</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', system-ui, sans-serif;
      background: #1e1e2e; color: #cdd6f4; min-height: 100vh; padding: 24px;
    }}
    header {{ border-bottom: 2px solid #313244; padding-bottom: 16px; margin-bottom: 24px; }}
    header h1 {{ font-size: 1.8rem; }}
    header p {{ color: #a6adc8; font-size: 0.9rem; margin-top: 4px; }}
    .badge {{
      display: inline-block; padding: 4px 12px; border-radius: 20px;
      font-weight: 700; font-size: 1rem; color: #1e1e2e;
      background: {risk_color};
    }}
    .score-card {{
      background: #313244; border-radius: 10px; padding: 20px; margin-bottom: 24px;
      display: flex; align-items: center; gap: 20px;
    }}
    .score-number {{ font-size: 3rem; font-weight: 900; color: {risk_color}; }}
    .info-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 12px; margin-bottom: 24px;
    }}
    .info-card {{
      background: #313244; border-radius: 8px; padding: 14px;
    }}
    .info-card .label {{ color: #a6adc8; font-size: 0.75rem; text-transform: uppercase; }}
    .info-card .value {{ font-size: 1.1rem; font-weight: 600; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #313244; }}
    th {{ color: #89b4fa; font-size: 0.8rem; text-transform: uppercase; }}
    tr:hover td {{ background: #2a2a3d; }}
    h2 {{ color: #89b4fa; margin: 24px 0 12px; font-size: 1.1rem; text-transform: uppercase; letter-spacing: 1px; }}
    .charts {{ display: flex; flex-wrap: wrap; gap: 16px; }}
    .chart-card {{
      background: #313244; border-radius: 10px; padding: 14px; flex: 1 1 420px;
    }}
    .chart-card h3 {{ color: #a6adc8; font-size: 0.85rem; margin-bottom: 8px; }}
    .chart-card img {{ width: 100%; border-radius: 6px; }}
    footer {{ color: #585b70; font-size: 0.8rem; margin-top: 32px; text-align: center; }}
  </style>
</head>
<body>
  <header>
    <h1>🛡 Token Guardian Report &nbsp;<span class="badge">{risk_level}</span></h1>
    <p>Token: <strong>{token_name}</strong> ({token_symbol}) · Address: {token_address}</p>
    <p>Generated: {datetime.now(tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
  </header>

  <div class="score-card">
    <div class="score-number">{total_score}</div>
    <div>
      <div style="font-size:1.4rem;font-weight:700">Risk Score <span class="badge">{risk_level}</span></div>
      <div style="color:#a6adc8;margin-top:4px">0 = safe · 100 = critical</div>
    </div>
  </div>

  <div class="info-grid">
    <div class="info-card">
      <div class="label">Mint Authority</div>
      <div class="value" style="color:{'#4CAF50' if risk_result.get('mint_authority_revoked') else '#F44336'}">
        {'✓ Revoked' if risk_result.get('mint_authority_revoked') else '✗ NOT Revoked'}
      </div>
    </div>
    <div class="info-card">
      <div class="label">Freeze Authority</div>
      <div class="value" style="color:{'#4CAF50' if risk_result.get('freeze_authority_revoked') else '#F44336'}">
        {'✓ Revoked' if risk_result.get('freeze_authority_revoked') else '✗ NOT Revoked'}
      </div>
    </div>
    <div class="info-card">
      <div class="label">Top-10 Concentration</div>
      <div class="value">{risk_result.get('top10_concentration', 0):.1f}%</div>
    </div>
    <div class="info-card">
      <div class="label">Bot Activity</div>
      <div class="value">{risk_result.get('bot_percentage', 0):.1f}%</div>
    </div>
    <div class="info-card">
      <div class="label">Bundled Wallets</div>
      <div class="value">{risk_result.get('bundled_wallet_percentage', 0):.1f}%</div>
    </div>
    <div class="info-card">
      <div class="label">Liquidity Info</div>
      <div class="value" style="color:{'#4CAF50' if risk_result.get('liquidity_locked') else '#F44336'}">
        {'✓ Found' if risk_result.get('liquidity_locked') else '✗ Not Found'}
      </div>
    </div>
    <div class="info-card">
      <div class="label">Total Wallets Analysed</div>
      <div class="value">{trader_analysis.get('total_wallets', 0)}</div>
    </div>
    <div class="info-card">
      <div class="label">Bundles Detected</div>
      <div class="value">{bundle_analysis.get('total_bundles', 0)} ({bundle_analysis.get('suspicious_bundles', 0)} suspicious)</div>
    </div>
  </div>

  <h2>⚠ Triggered Risk Factors</h2>
  {'<p style="color:#a6adc8">No risk factors triggered.</p>' if not risk_result.get('factors') else ''}
  {'<table><thead><tr><th>Factor</th><th>Points</th><th>Description</th></tr></thead><tbody>' + factors_rows + '</tbody></table>' if risk_result.get('factors') else ''}

  <h2>📊 Charts</h2>
  <div class="charts">
    {charts_html if charts_html else '<p style="color:#a6adc8">No charts generated.</p>'}
  </div>

  <footer>Solana Token Guardian Agent · Report generated at {datetime.now(tz=timezone.utc).isoformat()}</footer>
</body>
</html>"""

        filename = f"report_{token_address[:8]}_{self._ts()}.html"
        out_path = self.output_dir / filename
        out_path.write_text(html, encoding="utf-8")
        return str(out_path)

    # ------------------------------------------------------------------
    # Terminal dashboard (rich)
    # ------------------------------------------------------------------

    def print_terminal_dashboard(
        self,
        token_address: str,
        token_info: dict,
        trader_analysis: dict,
        bundle_analysis: dict,
        risk_result: dict,
    ) -> None:
        """Print a rich formatted terminal dashboard."""
        try:
            self._print_rich_dashboard(
                token_address, token_info, trader_analysis, bundle_analysis, risk_result
            )
        except ImportError:
            self._print_plain_dashboard(
                token_address, token_info, trader_analysis, bundle_analysis, risk_result
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _print_rich_dashboard(
        self,
        token_address: str,
        token_info: dict,
        trader_analysis: dict,
        bundle_analysis: dict,
        risk_result: dict,
    ) -> None:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.columns import Columns
        from rich import box

        console = Console()

        risk_level = risk_result.get("risk_level", "UNKNOWN")
        total_score = risk_result.get("total_score", 0)
        risk_style = {
            "LOW": "bold green",
            "MEDIUM": "bold yellow",
            "HIGH": "bold red",
            "CRITICAL": "bold white on red",
        }.get(risk_level, "white")

        # Header panel
        token_name = token_info.get("name", "Unknown")
        token_symbol = token_info.get("symbol", "???")
        console.print(
            Panel(
                f"[bold cyan]🛡 Solana Token Guardian[/bold cyan]\n"
                f"[white]{token_name}[/white] ([yellow]{token_symbol}[/yellow])\n"
                f"[dim]{token_address}[/dim]",
                title="Token Analysis Report",
                border_style="cyan",
            )
        )

        # Risk score summary
        console.print(
            Panel(
                f"[{risk_style}]Risk Score: {total_score}/100  ──  {risk_level}[/{risk_style}]\n"
                f"Mint Authority Revoked: {'[green]YES ✓[/green]' if risk_result.get('mint_authority_revoked') else '[red]NO ✗[/red]'}  │  "
                f"Freeze Authority Revoked: {'[green]YES ✓[/green]' if risk_result.get('freeze_authority_revoked') else '[red]NO ✗[/red]'}  │  "
                f"Liquidity Found: {'[green]YES ✓[/green]' if risk_result.get('liquidity_locked') else '[red]NO ✗[/red]'}\n"
                f"Top-10 Concentration: [yellow]{risk_result.get('top10_concentration', 0):.1f}%[/yellow]  │  "
                f"Bot Activity: [yellow]{risk_result.get('bot_percentage', 0):.1f}%[/yellow]  │  "
                f"Bundled Wallets: [yellow]{risk_result.get('bundled_wallet_percentage', 0):.1f}%[/yellow]",
                title=f"[{risk_style}] ⚠  Risk Assessment [{risk_style}]",
                border_style="red" if risk_level in ("HIGH", "CRITICAL") else "yellow",
            )
        )

        # Risk factors table
        if risk_result.get("factors"):
            table = Table(title="Triggered Risk Factors", box=box.ROUNDED, border_style="dim")
            table.add_column("Factor", style="white")
            table.add_column("Points", style="bold red", justify="right")
            table.add_column("Description", style="dim")
            for f in risk_result["factors"]:
                table.add_row(f["name"], f"+{f['points']}", f["description"])
            console.print(table)

        # Trader analysis table
        trader_table = Table(title="Trader Classification", box=box.ROUNDED, border_style="dim")
        trader_table.add_column("Category", style="white")
        trader_table.add_column("Count", justify="right")
        trader_table.add_column("Percentage", justify="right")
        total_w = trader_analysis.get("total_wallets", 1) or 1
        for label, key, style in [
            ("Real Traders", "real_traders", "green"),
            ("Bots", "bots", "red"),
            ("Wash Traders", "wash_traders", "yellow"),
            ("Sybil Wallets", "sybil_wallets", "magenta"),
        ]:
            count = trader_analysis.get(key, 0)
            pct = count / total_w * 100
            trader_table.add_row(
                f"[{style}]{label}[/{style}]",
                str(count),
                f"{pct:.1f}%",
            )
        trader_table.add_row("[bold]Total[/bold]", str(total_w), "100%")
        console.print(trader_table)

        # Bundle summary
        bundle_table = Table(title="Bundle Detection", box=box.ROUNDED, border_style="dim")
        bundle_table.add_column("Metric", style="white")
        bundle_table.add_column("Value", justify="right")
        bundle_table.add_row("Total Bundles", str(bundle_analysis.get("total_bundles", 0)))
        bundle_table.add_row(
            "Suspicious Bundles",
            f"[red]{bundle_analysis.get('suspicious_bundles', 0)}[/red]",
        )
        bundle_table.add_row(
            "Bundled Wallet %",
            f"{bundle_analysis.get('bundled_wallet_percentage', 0):.1f}%",
        )
        console.print(bundle_table)

    def _print_plain_dashboard(
        self,
        token_address: str,
        token_info: dict,
        trader_analysis: dict,
        bundle_analysis: dict,
        risk_result: dict,
    ) -> None:
        """Fallback plain-text dashboard when rich is not available."""
        sep = "=" * 60
        print(sep)
        print(f"  SOLANA TOKEN GUARDIAN REPORT")
        print(f"  {token_info.get('name', 'Unknown')} ({token_info.get('symbol', '???')})")
        print(f"  {token_address}")
        print(sep)
        print(f"  Risk Score : {risk_result.get('total_score', 0)}/100  ({risk_result.get('risk_level', 'UNKNOWN')})")
        print(f"  Top-10 Concentration : {risk_result.get('top10_concentration', 0):.1f}%")
        print(f"  Bot Activity         : {risk_result.get('bot_percentage', 0):.1f}%")
        print(f"  Bundled Wallets      : {risk_result.get('bundled_wallet_percentage', 0):.1f}%")
        print(sep)
        for f in risk_result.get("factors", []):
            print(f"  [+{f['points']:2d}] {f['name']}: {f['description']}")
        print(sep)

    @staticmethod
    def _ts() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")
