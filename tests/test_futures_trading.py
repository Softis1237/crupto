import asyncio
import os
import logging
from datetime import datetime
from prod_core.trade_executor import TradeExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_futures_trading():
    # Получаем креды из окружения
    api_key = os.getenv('EXCHANGE_API_KEY')
    api_secret = os.getenv('EXCHANGE_API_SECRET')
    
    if not api_key or not api_secret:
        raise ValueError("API credentials not found in environment variables")
    
    executor = TradeExecutor(api_key, api_secret)
    symbol = 'BTC/USDT'

    try:
        # 1. Проверяем баланс перед торговлей
        balance = await executor.exchange.get_balance()
        logger.info(f"Initial balance: {balance}")

        # 2. Получаем текущую цену
        price = await executor.get_market_price(symbol)
        logger.info(f"Current {symbol} price: {price}")

        # 3. Тестируем стандартные фьючерсы
        logger.info("Testing standard futures...")
        standard_order = await executor.execute_trade(
            symbol=symbol,
            side='buy',
            amount=0.001,  # Маленький размер для теста
            price=price * 0.99,  # Лимитный ордер чуть ниже рынка
            leverage=2,
            is_standard_futures=True,
            stop_loss=price * 0.98,
            take_profit=price * 1.02
        )
        logger.info(f"Standard futures order placed: {standard_order}")

        # Ждем немного
        await asyncio.sleep(5)

        # 4. Проверяем позиции
        await executor.update_positions()
        logger.info(f"Current positions: {executor.current_positions}")

        # 5. Тестируем бессрочные фьючерсы
        logger.info("Testing perpetual futures...")
        perpetual_order = await executor.execute_trade(
            symbol=symbol,
            side='buy',
            amount=0.001,  # Маленький размер для теста
            price=price * 0.99,  # Лимитный ордер чуть ниже рынка
            leverage=2,
            is_standard_futures=False,
            stop_loss=price * 0.98,
            take_profit=price * 1.02
        )
        logger.info(f"Perpetual futures order placed: {perpetual_order}")

        # Ждем немного
        await asyncio.sleep(5)

        # 6. Проверяем все открытые позиции
        await executor.update_positions()
        logger.info(f"Updated positions: {executor.current_positions}")

        # 7. Закрываем позиции
        for pos_symbol in executor.current_positions:
            logger.info(f"Closing position for {pos_symbol}...")
            result = await executor.close_position(pos_symbol)
            logger.info(f"Position closed: {result}")

    except Exception as e:
        logger.error(f"Error during testing: {str(e)}")
        raise

async def main():
    try:
        logger.info("Starting futures trading test...")
        await test_futures_trading()
        logger.info("Test completed successfully")
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")

if __name__ == '__main__':
    asyncio.run(main())