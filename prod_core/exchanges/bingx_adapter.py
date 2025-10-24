import ccxt
import hmac
import hashlib
import urllib.parse
import requests
import time
from typing import Dict, Optional, List, Union, Tuple
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class BingXAdapter:
    """
    Адаптер для работы с BingX, поддерживающий стандартные и бессрочные фьючерсы
    """
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = 'https://open-api.bingx.com'
        
        # Базовый CCXT клиент
        self.exchange = ccxt.bingx({
            'apiKey': api_key,
            'secret': api_secret,
            'options': {
                'defaultType': 'swap',
            }
        })
        
        # Кэш для leverage и режимов
        self._leverage_cache = {}
        self._futures_type_cache = {}

    def _sign_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Tuple[str, Dict]:
        """Подписать запрос к BingX API"""
        timestamp = int(time.time() * 1000)
        params = params or {}
        params['timestamp'] = timestamp
        
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        params['signature'] = signature
        url = f"{self.base_url}{endpoint}?{urllib.parse.urlencode(params)}"
        
        headers = {
            'X-BX-APIKEY': self.api_key,
            'Content-Type': 'application/json'
        }
        
        return url, headers

    async def place_order(self, 
                         symbol: str,
                         side: str,
                         amount: float,
                         price: Optional[float] = None,
                         leverage: int = 1,
                         is_standard_futures: bool = True,
                         stop_loss: Optional[float] = None,
                         take_profit: Optional[float] = None) -> Dict:
        """
        Разместить ордер с учетом типа фьючерсов
        """
        try:
            # Установка плеча если оно изменилось
            cached_leverage = self._leverage_cache.get(symbol)
            if cached_leverage != leverage:
                await self.set_leverage(symbol, leverage, is_standard_futures)
                self._leverage_cache[symbol] = leverage

            endpoint = '/openApi/swap/v2/trade/order'
            
            params = {
                'symbol': symbol.replace('/', ''),
                'side': side.upper(),
                'type': 'LIMIT' if price else 'MARKET',
                'quantity': str(amount),
                'leverage': str(leverage),
                'standardFutures': str(is_standard_futures).lower()
            }
            
            if price:
                params['price'] = str(price)
                
            # Добавляем SL/TP если указаны
            if stop_loss:
                params['stopLoss'] = str(stop_loss)
            if take_profit:
                params['takeProfit'] = str(take_profit)

            url, headers = self._sign_request('POST', endpoint, params)
            response = await self._async_request('POST', url, headers)
            
            if response.get('code') == 0:
                logger.info(f"Order placed successfully: {response}")
                return response['data']
            else:
                logger.error(f"Failed to place order: {response}")
                raise Exception(f"BingX API error: {response}")

        except Exception as e:
            logger.error(f"Error placing order: {str(e)}")
            raise

    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict]:
        """Получить открытые позиции"""
        try:
            if symbol:
                positions = await self.exchange.fetch_positions([symbol])
            else:
                positions = await self.exchange.fetch_positions()
            return positions
        except Exception as e:
            logger.error(f"Error fetching positions: {str(e)}")
            raise

    async def get_balance(self) -> Dict:
        """Получить баланс аккаунта"""
        try:
            balance = await self.exchange.fetch_balance({'type': 'swap'})
            return balance
        except Exception as e:
            logger.error(f"Error fetching balance: {str(e)}")
            raise

    async def set_leverage(self, symbol: str, leverage: int, is_standard_futures: bool = True) -> Dict:
        """Установить кредитное плечо"""
        try:
            endpoint = '/openApi/swap/v2/trade/leverage'
            params = {
                'symbol': symbol.replace('/', ''),
                'leverage': str(leverage),
                'standardFutures': str(is_standard_futures).lower()
            }
            
            url, headers = self._sign_request('POST', endpoint, params)
            response = await self._async_request('POST', url, headers)
            
            if response.get('code') == 0:
                logger.info(f"Leverage set successfully for {symbol}: {leverage}x")
                return response['data']
            else:
                logger.error(f"Failed to set leverage: {response}")
                raise Exception(f"BingX API error: {response}")

        except Exception as e:
            logger.error(f"Error setting leverage: {str(e)}")
            raise

    async def close_position(self, symbol: str, is_standard_futures: bool = True) -> Dict:
        """Закрыть позицию"""
        try:
            positions = await self.get_positions(symbol)
            if not positions:
                logger.info(f"No position found for {symbol}")
                return None

            position = positions[0]
            side = 'SELL' if position['side'] == 'long' else 'BUY'
            
            return await self.place_order(
                symbol=symbol,
                side=side,
                amount=abs(float(position['contracts'])),
                is_standard_futures=is_standard_futures
            )
        except Exception as e:
            logger.error(f"Error closing position: {str(e)}")
            raise

    async def get_market_price(self, symbol: str) -> float:
        """Получить текущую рыночную цену"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker['last']
        except Exception as e:
            logger.error(f"Error fetching market price: {str(e)}")
            raise

    async def _async_request(self, method: str, url: str, headers: Dict) -> Dict:
        """Выполнить асинхронный запрос"""
        try:
            response = requests.request(method, url, headers=headers)
            return response.json()
        except Exception as e:
            logger.error(f"API request error: {str(e)}")
            raise