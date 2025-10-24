import ccxt
import json
from datetime import datetime
import hmac
import hashlib
import urllib.parse
import requests
import time

class BingXFutures:
    def __init__(self, api_key, api_secret, testnet=False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = 'https://open-api.bingx.com'
        
        # Инициализация CCXT для общих операций
        self.exchange = ccxt.bingx({
            'apiKey': api_key,
            'secret': api_secret,
            'options': {
                'defaultType': 'swap',
            }
        })

    def _sign_request(self, method, endpoint, params=None):
        timestamp = int(time.time() * 1000)
        params = params or {}
        params['timestamp'] = timestamp
        
        # Сортировка параметров
        sorted_params = sorted(params.items())
        query_string = urllib.parse.urlencode(sorted_params)
        
        # Создание подписи
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        params['signature'] = signature
        
        # Формирование URL
        url = f"{self.base_url}{endpoint}?{urllib.parse.urlencode(params)}"
        
        headers = {
            'X-BX-APIKEY': self.api_key,
            'Content-Type': 'application/json'
        }
        
        return url, headers

    def get_balance(self):
        """Получить баланс фьючерсного аккаунта"""
        return self.exchange.fetch_balance({'type': 'swap'})

    def place_standard_futures_order(self, symbol, side, amount, price=None, leverage=1):
        """
        Разместить ордер на стандартных фьючерсах
        
        :param symbol: Торговая пара (например 'BTC/USDT')
        :param side: 'buy' или 'sell'
        :param amount: Объем в базовой валюте
        :param price: Цена (None для рыночного ордера)
        :param leverage: Кредитное плечо
        """
        endpoint = '/openApi/swap/v2/trade/order'
        
        params = {
            'symbol': symbol.replace('/', ''),
            'side': side.upper(),
            'type': 'LIMIT' if price else 'MARKET',
            'quantity': str(amount),
            'leverage': str(leverage),
            'standardFutures': 'true'  # Важный параметр для стандартных фьючерсов
        }
        
        if price:
            params['price'] = str(price)

        url, headers = self._sign_request('POST', endpoint, params)
        response = requests.post(url, headers=headers)
        return response.json()

    def place_perpetual_futures_order(self, symbol, side, amount, price=None, leverage=1):
        """
        Разместить ордер на бессрочных фьючерсах
        
        :param symbol: Торговая пара (например 'BTC/USDT')
        :param side: 'buy' или 'sell'
        :param amount: Объем в базовой валюте
        :param price: Цена (None для рыночного ордера)
        :param leverage: Кредитное плечо
        """
        endpoint = '/openApi/swap/v2/trade/order'
        
        params = {
            'symbol': symbol.replace('/', ''),
            'side': side.upper(),
            'type': 'LIMIT' if price else 'MARKET',
            'quantity': str(amount),
            'leverage': str(leverage),
            'standardFutures': 'false'  # Важный параметр для бессрочных фьючерсов
        }
        
        if price:
            params['price'] = str(price)

        url, headers = self._sign_request('POST', endpoint, params)
        response = requests.post(url, headers=headers)
        return response.json()

    def get_positions(self):
        """Получить открытые позиции"""
        return self.exchange.fetch_positions()

    def set_leverage(self, symbol, leverage, is_standard_futures=True):
        """Установить кредитное плечо"""
        endpoint = '/openApi/swap/v2/trade/leverage'
        
        params = {
            'symbol': symbol.replace('/', ''),
            'leverage': str(leverage),
            'standardFutures': str(is_standard_futures).lower()
        }
        
        url, headers = self._sign_request('POST', endpoint, params)
        response = requests.post(url, headers=headers)
        return response.json()

    def get_market_price(self, symbol):
        """Получить текущую рыночную цену"""
        ticker = self.exchange.fetch_ticker(symbol)
        return ticker['last']

def main():
    # Пример использования
    api_key = 'YOUR_API_KEY'
    api_secret = 'YOUR_API_SECRET'
    
    bingx = BingXFutures(api_key, api_secret)
    
    # Пример работы со стандартными фьючерсами
    try:
        # Установка плеча для стандартных фьючерсов
        leverage_response = bingx.set_leverage('BTC/USDT', 2, is_standard_futures=True)
        print("Установка плеча (стандартные):", leverage_response)
        
        # Размещение ордера на стандартных фьючерсах
        standard_order = bingx.place_standard_futures_order(
            symbol='BTC/USDT',
            side='buy',
            amount=0.01,
            price=35000,
            leverage=2
        )
        print("Ордер на стандартных фьючерсах:", standard_order)
        
    except Exception as e:
        print(f"Ошибка при работе со стандартными фьючерсами: {str(e)}")

    # Пример работы с бессрочными фьючерсами
    try:
        # Установка плеча для бессрочных фьючерсов
        leverage_response = bingx.set_leverage('BTC/USDT', 2, is_standard_futures=False)
        print("Установка плеча (бессрочные):", leverage_response)
        
        # Размещение ордера на бессрочных фьючерсах
        perpetual_order = bingx.place_perpetual_futures_order(
            symbol='BTC/USDT',
            side='buy',
            amount=0.01,
            price=35000,
            leverage=2
        )
        print("Ордер на бессрочных фьючерсах:", perpetual_order)
        
    except Exception as e:
        print(f"Ошибка при работе с бессрочными фьючерсами: {str(e)}")

if __name__ == '__main__':
    main()