"""
Data fetcher module – retrieves token data from Helius and RugCheck APIs.
All methods return empty dicts/lists on failure; they never raise to the caller.
"""

from __future__ import annotations

import time
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_HELIUS_RPC = "https://mainnet.helius-rpc.com/"
_HELIUS_API = "https://api.helius.xyz"
_RUGCHECK_API = "https://api.rugcheck.xyz/v1"

_DEFAULT_TIMEOUT = 20  # seconds
_MAX_RETRIES = 2


def _try_import_rich():
    try:
        from rich import print as rprint  # noqa: F401
        return rprint
    except ImportError:
        return print


_print = _try_import_rich()


def _post_with_retry(url: str, payload: dict, timeout: int = _DEFAULT_TIMEOUT) -> dict:
    """POST JSON with retry logic. Returns parsed JSON or empty dict."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            _print(f"[yellow]⚠ Timeout on attempt {attempt + 1}/{_MAX_RETRIES + 1} for {url}[/yellow]")
        except requests.exceptions.HTTPError as exc:
            # Don't retry 4xx client errors
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                _print(f"[red]✗ HTTP {exc.response.status_code} for {url}[/red]")
                return {}
            last_exc = exc
            _print(f"[yellow]⚠ HTTP error on attempt {attempt + 1}: {exc}[/yellow]")
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            _print(f"[yellow]⚠ Request error on attempt {attempt + 1}: {exc}[/yellow]")

        if attempt < _MAX_RETRIES:
            time.sleep(1.5 ** attempt)

    _print(f"[red]✗ All retries exhausted for {url}: {last_exc}[/red]")
    return {}


def _get_with_retry(url: str, params: dict | None = None, timeout: int = _DEFAULT_TIMEOUT) -> dict | list:
    """GET with retry logic. Returns parsed JSON or empty dict."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            _print(f"[yellow]⚠ Timeout on attempt {attempt + 1}/{_MAX_RETRIES + 1} for {url}[/yellow]")
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                _print(f"[red]✗ HTTP {exc.response.status_code} for {url}[/red]")
                return {}
            last_exc = exc
            _print(f"[yellow]⚠ HTTP error on attempt {attempt + 1}: {exc}[/yellow]")
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            _print(f"[yellow]⚠ Request error on attempt {attempt + 1}: {exc}[/yellow]")

        if attempt < _MAX_RETRIES:
            time.sleep(1.5 ** attempt)

    _print(f"[red]✗ All retries exhausted for {url}: {last_exc}[/red]")
    return {}


# ---------------------------------------------------------------------------
# DataFetcher
# ---------------------------------------------------------------------------

class DataFetcher:
    """Fetches Solana token data from Helius and RugCheck APIs."""

    def __init__(self, helius_api_key: str, rugcheck_api_key: str | None = None):
        self.helius_api_key = helius_api_key
        self.rugcheck_api_key = rugcheck_api_key

    # ------------------------------------------------------------------
    # Helius helpers
    # ------------------------------------------------------------------

    def _helius_rpc_url(self) -> str:
        return f"{_HELIUS_RPC}?api-key={self.helius_api_key}"

    def _helius_rpc(self, method: str, params: Any) -> dict:
        payload = {"jsonrpc": "2.0", "id": "1", "method": method, "params": params}
        return _post_with_retry(self._helius_rpc_url(), payload)

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_token_info(self, token_address: str) -> dict:
        """Fetch token metadata via Helius getAsset."""
        data = _post_with_retry(
            self._helius_rpc_url(),
            {"jsonrpc": "2.0", "id": "1", "method": "getAsset", "params": {"id": token_address}},
        )
        result = data.get("result", {})
        if not result:
            return {}

        content = result.get("content", {})
        metadata = content.get("metadata", {})
        token_info = result.get("token_info", {})
        supply_info = token_info.get("supply", 0)
        decimals = token_info.get("decimals", 0)

        mint_authority = result.get("authorities", [])
        has_mint = any(a.get("scopes", []) and "mint" in a.get("scopes", []) for a in mint_authority)
        has_freeze = token_info.get("freeze_authority") is not None

        return {
            "address": token_address,
            "name": metadata.get("name", "Unknown"),
            "symbol": metadata.get("symbol", "???"),
            "decimals": decimals,
            "supply": supply_info,
            "mint_authority_revoked": not has_mint,
            "freeze_authority_revoked": not has_freeze,
            "description": metadata.get("description", ""),
            "image": content.get("links", {}).get("image", ""),
            "raw": result,
        }

    def get_token_largest_accounts(self, token_address: str) -> list[dict]:
        """Return top holders with address, amount, and percentage."""
        supply_data = self.get_token_supply(token_address)
        total_supply_ui = supply_data.get("uiAmount", 0) if supply_data else 0

        data = self._helius_rpc("getTokenLargestAccounts", [token_address])
        accounts = data.get("result", {}).get("value", [])

        holders: list[dict] = []
        for acct in accounts:
            ui_amount = float(acct.get("uiAmountString") or acct.get("uiAmount") or 0)
            pct = (ui_amount / total_supply_ui * 100) if total_supply_ui else 0
            holders.append(
                {
                    "address": acct.get("address", ""),
                    "amount": ui_amount,
                    "percentage": round(pct, 4),
                }
            )

        return sorted(holders, key=lambda h: h["amount"], reverse=True)

    def get_token_supply(self, token_address: str) -> dict:
        """Get token supply information."""
        data = self._helius_rpc("getTokenSupply", [token_address])
        value = data.get("result", {}).get("value", {})
        return {
            "amount": value.get("amount", "0"),
            "decimals": value.get("decimals", 0),
            "uiAmount": value.get("uiAmount", 0),
            "uiAmountString": value.get("uiAmountString", "0"),
        }

    def get_recent_transactions(self, token_address: str, limit: int = 100) -> list[dict]:
        """Get recent SWAP transactions via Helius Enhanced Transactions API."""
        url = f"{_HELIUS_API}/v0/addresses/{token_address}/transactions"
        params = {
            "api-key": self.helius_api_key,
            "limit": min(limit, 100),
            "type": "SWAP",
        }
        result = _get_with_retry(url, params=params)
        if isinstance(result, list):
            return result
        return []

    def get_rugcheck_report(self, token_address: str) -> dict:
        """Fetch rug pull analysis from RugCheck.xyz."""
        url = f"{_RUGCHECK_API}/tokens/{token_address}/report"
        headers: dict[str, str] = {}
        if self.rugcheck_api_key:
            headers["Authorization"] = f"Bearer {self.rugcheck_api_key}"

        try:
            resp = requests.get(url, headers=headers, timeout=_DEFAULT_TIMEOUT)
            if resp.status_code == 404:
                _print(f"[yellow]⚠ RugCheck: no report found for {token_address}[/yellow]")
                return {}
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as exc:
            _print(f"[yellow]⚠ RugCheck unavailable: {exc}[/yellow]")
            return {}

    def get_all_token_data(self, token_address: str) -> dict:
        """Fetch all available data for a token and combine into one dict."""
        _print(f"[cyan]→ Fetching token metadata...[/cyan]")
        token_info = self.get_token_info(token_address)

        _print(f"[cyan]→ Fetching top holders...[/cyan]")
        holders = self.get_token_largest_accounts(token_address)

        _print(f"[cyan]→ Fetching recent transactions...[/cyan]")
        transactions = self.get_recent_transactions(token_address)

        _print(f"[cyan]→ Fetching RugCheck report...[/cyan]")
        rugcheck = self.get_rugcheck_report(token_address)

        return {
            "token_address": token_address,
            "token_info": token_info,
            "holders": holders,
            "transactions": transactions,
            "rugcheck": rugcheck,
        }
