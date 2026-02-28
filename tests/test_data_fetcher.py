"""
Unit tests for DataFetcher.
"""

from __future__ import annotations

import pytest
import requests

from src.data_fetcher import DataFetcher


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TOKEN = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # example (USDC mint)
HELIUS_KEY = "test_api_key"


@pytest.fixture()
def fetcher() -> DataFetcher:
    return DataFetcher(helius_api_key=HELIUS_KEY, rugcheck_api_key="test_rugcheck_key")


# ---------------------------------------------------------------------------
# get_token_info
# ---------------------------------------------------------------------------

class TestGetTokenInfo:
    def test_returns_parsed_token_info(self, fetcher: DataFetcher, mocker):
        mock_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "result": {
                "content": {
                    "metadata": {"name": "USD Coin", "symbol": "USDC", "description": "A stablecoin"},
                    "links": {"image": "https://example.com/usdc.png"},
                },
                "token_info": {
                    "supply": 1_000_000_000,
                    "decimals": 6,
                    "freeze_authority": None,
                },
                "authorities": [],
            },
        }
        mocker.patch("src.data_fetcher.requests.post", return_value=_mock_resp(mock_response))
        result = fetcher.get_token_info(TOKEN)
        assert result["name"] == "USD Coin"
        assert result["symbol"] == "USDC"
        assert result["decimals"] == 6
        assert result["address"] == TOKEN

    def test_returns_empty_dict_on_404(self, fetcher: DataFetcher, mocker):
        mocker.patch(
            "src.data_fetcher.requests.post",
            side_effect=requests.exceptions.HTTPError(
                response=_mock_resp({}, status_code=404)
            ),
        )
        result = fetcher.get_token_info(TOKEN)
        assert result == {}

    def test_returns_empty_dict_on_network_error(self, fetcher: DataFetcher, mocker):
        mocker.patch(
            "src.data_fetcher.requests.post",
            side_effect=requests.exceptions.ConnectionError("Network unreachable"),
        )
        result = fetcher.get_token_info(TOKEN)
        assert result == {}

    def test_returns_empty_dict_when_result_missing(self, fetcher: DataFetcher, mocker):
        mocker.patch(
            "src.data_fetcher.requests.post",
            return_value=_mock_resp({"jsonrpc": "2.0", "id": "1", "result": None}),
        )
        result = fetcher.get_token_info(TOKEN)
        assert result == {}

    def test_mint_authority_revoked_when_no_mint_scope(self, fetcher: DataFetcher, mocker):
        mock_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "result": {
                "content": {"metadata": {"name": "T", "symbol": "T"}, "links": {}},
                "token_info": {"supply": 100, "decimals": 9, "freeze_authority": None},
                "authorities": [{"scopes": ["update"]}],  # no "mint" scope
            },
        }
        mocker.patch("src.data_fetcher.requests.post", return_value=_mock_resp(mock_response))
        result = fetcher.get_token_info(TOKEN)
        assert result["mint_authority_revoked"] is True

    def test_freeze_authority_not_revoked_when_present(self, fetcher: DataFetcher, mocker):
        mock_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "result": {
                "content": {"metadata": {"name": "T", "symbol": "T"}, "links": {}},
                "token_info": {"supply": 100, "decimals": 9, "freeze_authority": "some_authority"},
                "authorities": [],
            },
        }
        mocker.patch("src.data_fetcher.requests.post", return_value=_mock_resp(mock_response))
        result = fetcher.get_token_info(TOKEN)
        assert result["freeze_authority_revoked"] is False


# ---------------------------------------------------------------------------
# get_token_supply
# ---------------------------------------------------------------------------

class TestGetTokenSupply:
    def test_returns_supply_info(self, fetcher: DataFetcher, mocker):
        mock_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "result": {
                "value": {
                    "amount": "1000000000",
                    "decimals": 6,
                    "uiAmount": 1000.0,
                    "uiAmountString": "1000",
                }
            },
        }
        mocker.patch("src.data_fetcher.requests.post", return_value=_mock_resp(mock_response))
        result = fetcher.get_token_supply(TOKEN)
        assert result["uiAmount"] == 1000.0
        assert result["decimals"] == 6

    def test_returns_defaults_on_error(self, fetcher: DataFetcher, mocker):
        mocker.patch(
            "src.data_fetcher.requests.post",
            side_effect=requests.exceptions.ConnectionError(),
        )
        result = fetcher.get_token_supply(TOKEN)
        assert result["uiAmount"] == 0


# ---------------------------------------------------------------------------
# get_recent_transactions
# ---------------------------------------------------------------------------

class TestGetRecentTransactions:
    def test_returns_transaction_list(self, fetcher: DataFetcher, mocker):
        mock_txns = [
            {"signature": "sig1", "feePayer": "wallet1", "timestamp": 1700000000, "tokenTransfers": []},
            {"signature": "sig2", "feePayer": "wallet2", "timestamp": 1700000001, "tokenTransfers": []},
        ]
        mocker.patch("src.data_fetcher.requests.get", return_value=_mock_resp(mock_txns))
        result = fetcher.get_recent_transactions(TOKEN)
        assert len(result) == 2
        assert result[0]["signature"] == "sig1"

    def test_returns_empty_list_on_error(self, fetcher: DataFetcher, mocker):
        mocker.patch(
            "src.data_fetcher.requests.get",
            side_effect=requests.exceptions.Timeout(),
        )
        result = fetcher.get_recent_transactions(TOKEN)
        assert result == []

    def test_returns_empty_list_when_response_is_dict(self, fetcher: DataFetcher, mocker):
        """If the API returns a dict (error) instead of a list, return empty list."""
        mocker.patch(
            "src.data_fetcher.requests.get",
            return_value=_mock_resp({"error": "something went wrong"}),
        )
        result = fetcher.get_recent_transactions(TOKEN)
        assert result == []


# ---------------------------------------------------------------------------
# get_rugcheck_report
# ---------------------------------------------------------------------------

class TestGetRugcheckReport:
    def test_returns_rugcheck_data(self, fetcher: DataFetcher, mocker):
        mock_data = {
            "score": 300,
            "markets": [{"id": "raydium_pool_1"}],
            "risks": [],
            "tokenMeta": {"name": "Test Token"},
        }
        mocker.patch("src.data_fetcher.requests.get", return_value=_mock_resp(mock_data))
        result = fetcher.get_rugcheck_report(TOKEN)
        assert result["score"] == 300
        assert len(result["markets"]) == 1

    def test_returns_empty_on_404(self, fetcher: DataFetcher, mocker):
        mocker.patch(
            "src.data_fetcher.requests.get",
            return_value=_mock_resp({}, status_code=404),
        )
        result = fetcher.get_rugcheck_report(TOKEN)
        assert result == {}

    def test_returns_empty_on_connection_error(self, fetcher: DataFetcher, mocker):
        mocker.patch(
            "src.data_fetcher.requests.get",
            side_effect=requests.exceptions.ConnectionError("unreachable"),
        )
        result = fetcher.get_rugcheck_report(TOKEN)
        assert result == {}

    def test_uses_auth_header_when_key_present(self, fetcher: DataFetcher, mocker):
        """When rugcheck_api_key is set, Authorization header should be included."""
        mock_get = mocker.patch(
            "src.data_fetcher.requests.get",
            return_value=_mock_resp({"score": 100}),
        )
        fetcher.get_rugcheck_report(TOKEN)
        call_kwargs = mock_get.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
        # Fallback: check the keyword arg 'headers'
        if not headers and call_kwargs.kwargs:
            headers = call_kwargs.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer test_rugcheck_key"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------

class TestRetryLogic:
    def test_retries_on_server_error(self, fetcher: DataFetcher, mocker):
        """POST should retry on 5xx error and succeed on second attempt."""
        success_response = {
            "jsonrpc": "2.0",
            "id": "1",
            "result": {
                "content": {"metadata": {"name": "Retry Token", "symbol": "RT"}, "links": {}},
                "token_info": {"supply": 100, "decimals": 9, "freeze_authority": None},
                "authorities": [],
            },
        }
        server_error = requests.exceptions.HTTPError(
            response=_mock_resp({}, status_code=503)
        )
        # First call fails, second succeeds
        mock_post = mocker.patch(
            "src.data_fetcher.requests.post",
            side_effect=[server_error, _mock_resp(success_response)],
        )
        mocker.patch("src.data_fetcher.time.sleep")  # don't actually sleep
        result = fetcher.get_token_info(TOKEN)
        assert result.get("name") == "Retry Token"
        assert mock_post.call_count == 2

    def test_stops_after_max_retries(self, fetcher: DataFetcher, mocker):
        """After MAX_RETRIES failures, should return empty dict."""
        mocker.patch(
            "src.data_fetcher.requests.post",
            side_effect=requests.exceptions.Timeout("always times out"),
        )
        mocker.patch("src.data_fetcher.time.sleep")
        result = fetcher.get_token_info(TOKEN)
        assert result == {}


# ---------------------------------------------------------------------------
# get_all_token_data
# ---------------------------------------------------------------------------

class TestGetAllTokenData:
    def test_returns_combined_dict(self, fetcher: DataFetcher, mocker):
        mocker.patch.object(fetcher, "get_token_info", return_value={"name": "Test", "symbol": "TST"})
        mocker.patch.object(fetcher, "get_token_largest_accounts", return_value=[{"address": "w1", "percentage": 10}])
        mocker.patch.object(fetcher, "get_recent_transactions", return_value=[])
        mocker.patch.object(fetcher, "get_rugcheck_report", return_value={"score": 100})

        result = fetcher.get_all_token_data(TOKEN)
        assert result["token_info"]["name"] == "Test"
        assert result["holders"] == [{"address": "w1", "percentage": 10}]
        assert result["transactions"] == []
        assert result["rugcheck"]["score"] == 100
        assert result["token_address"] == TOKEN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockResponse:
    def __init__(self, data, status_code: int = 200):
        self._data = data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            err = requests.exceptions.HTTPError(f"HTTP {self.status_code}")
            err.response = self
            raise err

    def json(self):
        return self._data


def _mock_resp(data, status_code: int = 200) -> _MockResponse:
    return _MockResponse(data, status_code)
