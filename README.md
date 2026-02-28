# 🛡 Solana Token Guardian Agent

A Python-based CLI tool that performs comprehensive background checks on Solana tokens, detecting rug-pull signals, bot activity, wallet bundling, and wash trading — then produces risk scores, charts, and detailed reports.

---

## Features

- **Token Metadata Analysis** – fetches name, symbol, supply, mint/freeze authority status via Helius
- **Holder Concentration** – identifies top-10 holder concentration risk
- **Trader Classification** – labels wallets as Real Traders, Bots, Wash Traders, or Sybil wallets
- **Bundler Detection** – finds coordinated wallet clusters transacting in the same block
- **Risk Scoring** – 0–100 composite score with individual factor breakdown (LOW / MEDIUM / HIGH / CRITICAL)
- **RugCheck Integration** – pulls reports from RugCheck.xyz for additional signal
- **Charts** – PNG bar/pie charts for trader breakdown, holder distribution, risk factors, and bundle groups
- **Reports** – JSON report and self-contained dark-theme HTML report with embedded charts
- **Rich Terminal Dashboard** – coloured tables and risk indicators in the terminal

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/your-org/Token-Background-Check.git
cd Token-Background-Check

# 2. (Recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## API Key Setup

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```dotenv
# Required – get a free key at https://helius.xyz
HELIUS_API_KEY=your_helius_api_key_here

# Optional – unauthenticated public endpoints are used if absent
RUGCHECK_API_KEY=your_rugcheck_api_key_here

# Output directory (default: ./output)
OUTPUT_DIR=./output
```

> Only `HELIUS_API_KEY` is strictly required. The tool will warn but continue without `RUGCHECK_API_KEY`.

---

## Usage

```bash
# Basic analysis
python token_check.py <TOKEN_MINT_ADDRESS>

# Save reports to a custom directory
python token_check.py <TOKEN_MINT_ADDRESS> --output-dir ./reports

# Skip chart generation (faster)
python token_check.py <TOKEN_MINT_ADDRESS> --no-charts

# JSON report only (no terminal dashboard, no HTML)
python token_check.py <TOKEN_MINT_ADDRESS> --json-only

# Generate HTML report explicitly
python token_check.py <TOKEN_MINT_ADDRESS> --html
```

### Example

```bash
python token_check.py EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v
```

**Sample terminal output:**

```
🔍 Analysing token: EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v

→ Fetching token metadata...
→ Fetching top holders...
→ Fetching recent transactions...
→ Fetching RugCheck report...
→ Analysing trader behaviour...
→ Detecting wallet bundles...
→ Computing risk score...
→ Generating charts...

✓ JSON report: ./output/report_EPjFWdd5_20241120_143022.json
✓ HTML report: ./output/report_EPjFWdd5_20241120_143022.html

┌─ Token Analysis Report ─────────────────────────────────┐
│ 🛡 Solana Token Guardian                                 │
│ USD Coin (USDC)                                          │
│ EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v            │
└──────────────────────────────────────────────────────────┘
  Risk Score: 10/100  ──  LOW
  Mint Authority Revoked: YES ✓  │  Freeze Authority Revoked: NO ✗
  Top-10 Concentration: 42.3%  │  Bot Activity: 5.0%
```

---

## Output Files

All output is saved to `./output/` (or `--output-dir`):

| File | Description |
|------|-------------|
| `report_<addr>_<ts>.json` | Full machine-readable JSON report |
| `report_<addr>_<ts>.html` | Self-contained dark-theme HTML report with embedded charts |
| `trader_breakdown.png` | Pie chart of trader classification |
| `holder_distribution.png` | Bar chart of top-10 holder percentages |
| `risk_factors.png` | Horizontal bar chart of risk factor scores |
| `bundle_groups.png` | Bar chart of detected wallet bundle sizes |

---

## Risk Score Explanation

The risk score is a composite 0–100 value. Higher = riskier.

| Factor | Max Points | Trigger |
|--------|-----------|---------|
| Mint authority not revoked | +25 | Developer can print unlimited tokens |
| Freeze authority not revoked | +20 | Developer can freeze holder wallets |
| Top-10 holder concentration > 80% | +20 | Extreme supply concentration |
| Top-10 holder concentration 50–80% | +10 | Elevated supply concentration |
| Bundled wallet percentage > 30% | +15 | Coordinated launch detected |
| Bot activity > 50% | +10 | Majority of volume is automated |
| No liquidity info | +10 | Token may be illiquid / unverified |
| RugCheck score > 500 | +20 | RugCheck.xyz flagged as high risk |

**Risk levels:**

| Score | Level |
|-------|-------|
| 0–24 | 🟢 LOW |
| 25–49 | 🟡 MEDIUM |
| 50–74 | 🔴 HIGH |
| 75–100 | ⛔ CRITICAL |

The CLI exits with code `1` when the risk level is CRITICAL.

---

## Project Structure

```
Token-Background-Check/
├── token_check.py          # CLI entry point
├── requirements.txt
├── .env.example
├── .gitignore
├── src/
│   ├── config.py           # Environment / API key loading
│   ├── data_fetcher.py     # Helius + RugCheck API client
│   ├── trader_analyzer.py  # Bot / wash-trader / sybil classification
│   ├── bundler_detector.py # Wallet bundle detection
│   ├── risk_scorer.py      # Composite risk scoring
│   ├── visualizer.py       # Matplotlib chart generation
│   └── report_generator.py # JSON, HTML, terminal reports
└── tests/
    ├── test_trader_analyzer.py
    ├── test_bundler_detector.py
    ├── test_risk_scorer.py
    └── test_data_fetcher.py
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## APIs Used

- **[Helius](https://helius.xyz)** – Solana RPC + Enhanced Transaction API (token metadata, holders, swaps)
- **[RugCheck.xyz](https://rugcheck.xyz)** – Token risk reports and market data

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m "Add my feature"`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

Please ensure all tests pass (`pytest tests/ -v`) before submitting.

---

## License

MIT