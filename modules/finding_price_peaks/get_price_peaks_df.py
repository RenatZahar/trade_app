# redis_init.py

import os
import time
import os
import modules.finding_price_peaks.price_peaks_func as pnt
from config import setup_logging, BLOCKS_SQL_DATA, CLEARED_PRICES_DIR_FILE, BTC_PRICES_WITH_INTERVALS_FILE
from .config import how_much_data_test_after_learning_mounth, cicle, price_diff_pct, plato
from dotenv import load_dotenv
load_dotenv()

logger = setup_logging(__name__)
# BASE_DIR = Path(__file__).resolve().parent
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

LINE_TIME_DURATION_MIN = int(os.getenv('LINE_TIME_DURATION_MIN'))
# LINE_TIME_DURATION_MIN = os.getenv('LINE_TIME_DURATION_MIN')
# LINE_TIME_DURATION_MIN = int(LINE_TIME_DURATION_MIN)



def get_peaks():
    btc_price_df = pnt.get_btc_prices(CLEARED_PRICES_DIR_FILE)

    # btc_price_df, btc_price_df_for_test = pnt.split_btc_prices(btc_price_df, how_much_data_test_after_learning_mounth)
    btc_price_data = pnt.analyze_with_parameters(btc_price_df, cicle, price_diff_pct, plato, LINE_TIME_DURATION_MIN)

    # print('dollars, sum_avg, for 1000')
    # print(pnt.calculate_profit(btc_price_data)) 
    # print(btc_price_data.head())

    btc_price_data.to_parquet(BTC_PRICES_WITH_INTERVALS_FILE)
    # btc_price_df_for_test.to_parquet(btc_price_test_data_dir)

    sell_signals = btc_price_data[btc_price_data['Sell'] > 0] 
    buy_signals = btc_price_data[btc_price_data['Buy'] > 0]

    print('len(sell_signals)')
    print(len(sell_signals))
    print('len(buy_signals)')
    print(len(buy_signals))


if __name__ == '__main__':
    get_peaks()

