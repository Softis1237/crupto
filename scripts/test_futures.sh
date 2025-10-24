#!/bin/bash

# Активируем виртуальное окружение
source .venv/bin/activate

# Загружаем тестовое окружение
set -o allexport
source .env.test
set +o allexport

# Очищаем логи предыдущих тестов
echo "Cleaning old logs..."
mkdir -p logs
rm -f logs/futures_test_*.log

# Запускаем тест
echo "Starting futures trading test..."
python -m tests.test_futures_trading 2>&1 | tee logs/futures_test_$(date +%Y%m%d_%H%M%S).log

# Проверяем результат
if [ $? -eq 0 ]; then
    echo "Test completed successfully"
else
    echo "Test failed! Check the logs for details"
    exit 1
fi