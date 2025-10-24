import asyncio
import hmac
import hashlib
import inspect
import logging
import os
import time
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import ccxt

try:  # pragma: no cover - optional dependency
    import ccxt.async_support as ccxt_async  # type: ignore
except ImportError:  # pragma: no cover - fallback when async support is unavailable
    ccxt_async = None

logger = logging.getLogger(__name__)


def _env_flag(name: str) -> bool:
    value = os.getenv(name, "")
    return value.lower() in {"1", "true", "yes", "on"}


class _SyncExchangeWrapper:
    """Expose synchronous ccxt client via async-friendly interface."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def set_sandbox_mode(self, enabled: bool) -> None:
        if hasattr(self._client, "set_sandbox_mode"):
            self._client.set_sandbox_mode(enabled)

    async def fetch_positions(self, symbols: Optional[List[str]] = None) -> List[Dict]:
        return await asyncio.to_thread(self._client.fetch_positions, symbols)

    async def fetch_balance(self, params: Optional[Dict] = None) -> Dict:
        return await asyncio.to_thread(self._client.fetch_balance, params or {})

    async def fetch_ticker(self, symbol: str) -> Dict:
        return await asyncio.to_thread(self._client.fetch_ticker, symbol)

    async def close(self) -> None:
        close_attr = getattr(self._client, "close", None)
        if callable(close_attr):
            await asyncio.to_thread(close_attr)


class BingXAdapter:
    """
    Адаптер для работы с BingX, поддерживающий стандартные и бессрочные фьючерсы.
    """

    def __init__(self, api_key: str, api_secret: str, testnet: bool = False) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://open-api.bingx.com"
        self._session: aiohttp.ClientSession | None = None
        self._use_virtual = _env_flag("USE_VIRTUAL_TRADING")
        self._virtual_asset = os.getenv("VIRTUAL_ASSET", "VST")

        # Базовый CCXT клиент
        self.exchange = self._build_exchange(api_key, api_secret, testnet)

        # Кэш для leverage и режимов
        self._leverage_cache: Dict[str, int] = {}
        self._futures_type_cache: Dict[str, bool] = {}

    def _build_exchange(self, api_key: str, api_secret: str, testnet: bool) -> Any:
        params = {
            "apiKey": api_key,
            "secret": api_secret,
            "options": {
                "defaultType": "swap",
            },
        }
        use_sandbox = testnet or self._use_virtual

        if ccxt_async:
            client = ccxt_async.bingx(params)
            if hasattr(client, "set_sandbox_mode"):
                client.set_sandbox_mode(use_sandbox)
            return client

        client = ccxt.bingx(params)
        wrapper = _SyncExchangeWrapper(client)
        wrapper.set_sandbox_mode(use_sandbox)
        return wrapper

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _sign_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Tuple[str, Dict]:
        """Подписать запрос к BingX API."""
        timestamp = int(time.time() * 1000)
        params = params or {}
        params["timestamp"] = timestamp

        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)

        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        params["signature"] = signature
        url = f"{self.base_url}{endpoint}?{urllib.parse.urlencode(params)}"

        headers = {
            "X-BX-APIKEY": self.api_key,
            "Content-Type": "application/json",
        }

        return url, headers

    async def place_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: Optional[float] = None,
        leverage: int = 1,
        is_standard_futures: bool = True,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Dict:
        """
        Разместить ордер с учетом типа фьючерсов.
        """
        try:
            cached_leverage = self._leverage_cache.get(symbol)
            if cached_leverage != leverage:
                await self.set_leverage(symbol, leverage, is_standard_futures)
                self._leverage_cache[symbol] = leverage

            endpoint = "/openApi/swap/v2/trade/order"

            params: Dict[str, str] = {
                "symbol": symbol.replace("/", ""),
                "side": side.upper(),
                "type": "LIMIT" if price else "MARKET",
                "quantity": str(amount),
                "leverage": str(leverage),
                "standardFutures": str(is_standard_futures).lower(),
            }

            if price is not None:
                params["price"] = str(price)

            if stop_loss is not None:
                params["stopLoss"] = str(stop_loss)
            if take_profit is not None:
                params["takeProfit"] = str(take_profit)

            if self._use_virtual:
                params["virtualAccountType"] = self._virtual_asset
                params["forceVirtual"] = "true"

            url, headers = self._sign_request("POST", endpoint, params)
            response = await self._async_request("POST", url, headers)

            if response.get("code") == 0:
                logger.info("Order placed successfully: %s", response)
                data = response["data"]
                if self._use_virtual:
                    data.setdefault("meta", {})["virtual_asset"] = self._virtual_asset
                return data

            logger.error("Failed to place order: %s", response)
            raise RuntimeError(f"BingX API error: {response}")

        except Exception as exc:
            logger.error("Error placing order: %s", exc)
            raise

    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Получить открытые позиции."""
        try:
            if symbol:
                positions = await self.exchange.fetch_positions([symbol])
            else:
                positions = await self.exchange.fetch_positions()
            if self._use_virtual:
                for position in positions or []:
                    position.setdefault("info", {})["virtual_asset"] = self._virtual_asset
            return positions
        except Exception as exc:
            logger.error("Error fetching positions: %s", exc)
            raise

    async def get_balance(self) -> Dict:
        """Получить баланс аккаунта."""
        try:
            balance = await self.exchange.fetch_balance({"type": "swap"})
            if self._use_virtual:
                balance.setdefault("info", {})["virtual_asset"] = self._virtual_asset
            return balance
        except Exception as exc:
            logger.error("Error fetching balance: %s", exc)
            raise

    async def set_leverage(self, symbol: str, leverage: int, is_standard_futures: bool = True) -> Dict:
        """Установить кредитное плечо."""
        try:
            endpoint = "/openApi/swap/v2/trade/leverage"
            params = {
                "symbol": symbol.replace("/", ""),
                "leverage": str(leverage),
                "standardFutures": str(is_standard_futures).lower(),
            }

            if self._use_virtual:
                params["virtualAccountType"] = self._virtual_asset
                params["forceVirtual"] = "true"

            url, headers = self._sign_request("POST", endpoint, params)
            response = await self._async_request("POST", url, headers)

            if response.get("code") == 0:
                logger.info("Leverage set successfully for %s: %sx", symbol, leverage)
                return response["data"]

            logger.error("Failed to set leverage: %s", response)
            raise RuntimeError(f"BingX API error: {response}")

        except Exception as exc:
            logger.error("Error setting leverage: %s", exc)
            raise

    async def close_position(self, symbol: str, is_standard_futures: bool = True) -> Optional[Dict]:
        """Закрыть позицию."""
        try:
            positions = await self.get_positions(symbol)
            if not positions:
                logger.info("No position found for %s", symbol)
                return None

            position = positions[0]
            side = "SELL" if position.get("side") == "long" else "BUY"

            return await self.place_order(
                symbol=symbol,
                side=side,
                amount=abs(float(position.get("contracts", 0.0))),
                is_standard_futures=is_standard_futures,
            )
        except Exception as exc:
            logger.error("Error closing position: %s", exc)
            raise

    async def get_market_price(self, symbol: str) -> float:
        """Получить текущую рыночную цену."""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return float(ticker["last"])
        except Exception as exc:
            logger.error("Error fetching market price: %s", exc)
            raise

    async def _async_request(self, method: str, url: str, headers: Dict) -> Dict:
        """Выполнить асинхронный HTTP-запрос."""
        session = await self._ensure_session()
        try:
            async with session.request(method, url, headers=headers, timeout=15) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as exc:
            logger.error("API request error: %s", exc)
            raise

    async def close(self) -> None:
        """Закрыть HTTP-сессию и клиент биржи."""
        close_attr = getattr(self.exchange, "close", None)
        if callable(close_attr):
            if inspect.iscoroutinefunction(close_attr):
                await close_attr()
            else:
                await asyncio.to_thread(close_attr)
        if self._session and not self._session.closed:
            await self._session.close()
