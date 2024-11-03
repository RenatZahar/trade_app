import time
import requests
import os
from config import setup_logging, LINE_TIME_DURATION_MIN

logger = setup_logging(__name__)

def get_price_data(start_time_ms, end_time_ms):
    logger.info(f"Старт price_updater")
    symbol = 'BTCUSDT'
    interval = '1m'  # Интервал свечи 1 минута
    limit = 1000     # Максимальное количество записей за один запрос

    url = 'https://api.binance.com/api/v3/klines'
    all_data = []

    while start_time_ms < end_time_ms:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': start_time_ms,
            'endTime': end_time_ms,
            'limit': limit
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при запросе данных: {e}")
            break

        if not data:
            break

        all_data.extend(data)

        # Обновляем start_time_ms для следующего запроса
        last_open_time = data[-1][0]
        start_time_ms = last_open_time + 60 * 1000  # Переходим к следующей минуте
        # Добавим небольшую задержку, чтобы не превышать лимиты API
        time.sleep(0.1)
    if all_data:
        return all_data
    else:
        logger.error('Не получилось обновить данные btc с api binance')
        return None 