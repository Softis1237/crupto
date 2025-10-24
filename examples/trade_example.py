import asyncio
import os
from prod_core.trade_executor import TradeExecutor

async def main():
    # Получаем креды из окружения
    api_key = os.getenv('EXCHANGE_API_KEY')
    api_secret = os.getenv('EXCHANGE_API_SECRET')
    
    # Создаем исполнитель торговли
    executor = TradeExecutor(api_key, api_secret)
    
    # Пример торговли на стандартных фьючерсах
    try:
        order = await executor.execute_trade(
            symbol='BTC/USDT',
            side='buy',
            amount=0.01,
            price=35000,
            leverage=2,
            is_standard_futures=True,  # Стандартные фьючерсы
            stop_loss=34000,
            take_profit=36000
        )
        print("Ордер на стандартных фьючерсах:", order)
        
    except Exception as e:
        print(f"Ошибка при торговле стандартными фьючерсами: {str(e)}")

    # Пример торговли на бессрочных фьючерсах
    try:
        order = await executor.execute_trade(
            symbol='BTC/USDT',
            side='buy',
            amount=0.01,
            price=35000,
            leverage=2,
            is_standard_futures=False,  # Бессрочные фьючерсы
            stop_loss=34000,
            take_profit=36000
        )
        print("Ордер на бессрочных фьючерсах:", order)
        
    except Exception as e:
        print(f"Ошибка при торговле бессрочными фьючерсами: {str(e)}")

if __name__ == '__main__':
    asyncio.run(main())