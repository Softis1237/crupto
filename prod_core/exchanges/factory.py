from typing import Optional
from .bingx_adapter import BingXAdapter

class ExchangeFactory:
    """
    Фабрика для создания экземпляров биржевых адаптеров
    """
    @staticmethod
    def create_exchange(exchange_name: str, api_key: str, api_secret: str, testnet: bool = False) -> Optional[BingXAdapter]:
        if exchange_name.lower() == 'bingx':
            return BingXAdapter(api_key, api_secret, testnet)
        else:
            raise ValueError(f"Unsupported exchange: {exchange_name}")