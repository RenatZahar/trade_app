import os
import time
import os
import pandas as pd
import modules.finding_price_peaks.price_peaks_func as pnt
from config import setup_logging, CLEARED_PRICES_DIR_FILE, BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE, LINE_TIME_DURATION_MIN
from .config import how_much_data_test_after_learning_mounth, cicle, price_diff_pct, plato


logger = setup_logging(__name__)
# BASE_DIR = Path(__file__).resolve().parent
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

def get_peaks():
    print('сделать раз в день перезапуск get_peaks')
    yesterday_midnight = pnt.get_yesterday_midnight()
    btc_price_data_with_peaks = pd.read_parquet(BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE)
    last_date_of_peaks = btc_price_data_with_peaks['Timestamp'].iloc[-1]
    
    if yesterday_midnight < int(last_date_of_peaks):
        logger.info('get_peaks обновлял данные сегодня, пропускаем расчеты')
        return
    
    else:
        btc_price_df = pnt.get_btc_prices(CLEARED_PRICES_DIR_FILE)
        btc_price_data_with_peaks = pnt.analyze_with_parameters(btc_price_df, cicle, price_diff_pct, plato, LINE_TIME_DURATION_MIN)

        # print('dollars, sum_avg, for 1000')
        # print(pnt.calculate_profit(btc_price_data)) 
        # print(btc_price_data.head())
        logger.info('Пики в get_peaks найдены, крайие строки:')
        logger.info(btc_price_data_with_peaks.head(3))
        logger.info(btc_price_data_with_peaks.tail(3))
        btc_price_data_with_peaks.to_parquet(BTC_PRICES_WITH_PEAKS_AND_INTERVALS_FILE)

    # sell_signals = btc_price_data[btc_price_data['Sell'] > 0] 
    # buy_signals = btc_price_data[btc_price_data['Buy'] > 0]
    # print('len(sell_signals)')
    # print(len(sell_signals))
    # print('len(buy_signals)')
    # print(len(buy_signals))





if __name__ == '__main__':
    get_peaks()

