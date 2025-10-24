from typing import Dict, Optional
from decimal import Decimal
import logging
from .exchanges import ExchangeFactory

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self, api_key: str, api_secret: str, exchange_name: str = 'bingx'):
        self.exchange = ExchangeFactory.create_exchange(exchange_name, api_key, api_secret)
        self.current_positions = {}
        self.orders = {}

    async def execute_trade(self, 
                          symbol: str,
                          side: str,
                          amount: float,
                          price: Optional[float] = None,
                          leverage: int = 1,
                          is_standard_futures: bool = True,
                          stop_loss: Optional[float] = None,
                          take_profit: Optional[float] = None) -> Dict:
        """
        Выполнить торговую операцию
        """
        try:
            # Проверка баланса перед сделкой
            balance = await self.exchange.get_balance()
            
            # Размещение ордера
            order = await self.exchange.place_order(
                symbol=symbol,
                side=side,
                amount=amount,
                price=price,
                leverage=leverage,
                is_standard_futures=is_standard_futures,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            # Сохраняем информацию об ордере
            self.orders[order['orderId']] = order
            
            # Обновляем информацию о позициях
            await self.update_positions()
            
            return order
            
        except Exception as e:
            logger.error(f"Trade execution error: {str(e)}")
            raise

    async def update_positions(self):
        """Обновить информацию о текущих позициях"""
        try:
            positions = await self.exchange.get_positions()
            self.current_positions = {
                pos['symbol']: pos for pos in positions if float(pos['contracts']) != 0
            }
        except Exception as e:
            logger.error(f"Error updating positions: {str(e)}")
            raise

    async def close_position(self, symbol: str, is_standard_futures: bool = True) -> Optional[Dict]:
        """Закрыть позицию по символу"""
        try:
            result = await self.exchange.close_position(symbol, is_standard_futures)
            await self.update_positions()
            return result
        except Exception as e:
            logger.error(f"Error closing position: {str(e)}")
            raise

    async def get_market_price(self, symbol: str) -> float:
        """Получить текущую рыночную цену"""
        try:
            return await self.exchange.get_market_price(symbol)
        except Exception as e:
            logger.error(f"Error getting market price: {str(e)}")
            raise