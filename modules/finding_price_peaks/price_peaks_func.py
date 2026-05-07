import pprint
import sitecustomize  # noqa: F401
import pandas as pd
from scipy.signal import find_peaks  # type: ignore
import itertools
import numpy as np
import os
from datetime import datetime, timedelta

pd.set_option("display.expand_frame_repr", False)  # не переносить строки
pd.set_option("display.max_colwidth", None)
pd.set_option("display.float_format", lambda x: "%.3f" % x)
pd.set_option("display.max_rows", 30)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)
pd.set_option("display.max_colwidth", None)
pp = pprint.PrettyPrinter(indent=4)

def get_yesterday_midnight():
    now = datetime.now()
    today_midnight = datetime(now.year, now.month, now.day)
    yesterday_midnight = today_midnight - timedelta(days=1)
    yesterday_timestamp = int(yesterday_midnight.timestamp())
    return yesterday_timestamp


# def def_total_iterations(TRADE_CICLE_MIN_DAYS_MIN_MAX_STEP, MIN_BTC_PRICE_DIFF_PCT_MIN_MAX_STEP, MIN_BTC_PRICE_DIFF_PLATO_MIN_MAX_STEP):
#     num_cicle_points = np.arange(*TRADE_CICLE_MIN_DAYS_MIN_MAX_STEP).size
#     num_price_diff_points = np.arange(*MIN_BTC_PRICE_DIFF_PCT_MIN_MAX_STEP).size
#     num_plato_points = np.arange(*MIN_BTC_PRICE_DIFF_PLATO_MIN_MAX_STEP).size
#     total_iterations = num_cicle_points * num_price_diff_points * num_plato_points
#     return total_iterations

def get_btc_prices(CLEARED_PRICES_DIR_FILE):
    btc_price_df = pd.read_parquet(CLEARED_PRICES_DIR_FILE)
    return btc_price_df

def analyze_with_parameters(btc_price_df, cicle, price_diff_pct, plato, SMA_MIN):
    prices = btc_price_df["Price"].values  # type: ignore
    peaks, _ = find_peaks(prices, distance=cicle * 24 * 60 / SMA_MIN, width=1)

    for index, peak in enumerate(peaks): 
        btc_price_df.loc[peak, "Sell"] = 1

    for i in range(1, len(peaks)):
    # Получаем интервал между двумя пиками
        start_peak = peaks[i - 1]
        end_peak = peaks[i]
        interval = btc_price_df.iloc[start_peak+1:end_peak+10]
        # Находим минимальную цену в интервале
        min_price_row = interval.loc[interval['Price'].idxmin()]
        min_price = min_price_row['Price']

        # Проверяем разницу в цене только со вторым пиком
        if abs(btc_price_df.iloc[end_peak]['Price'] - min_price) / min_price * 100 >= price_diff_pct:
            potential_buy_points = interval[(interval['Price'] >= min_price) &
                                            (interval['Price'] <= min_price * (1 + plato / 100))]
            btc_price_df.loc[potential_buy_points.index, 'Buy'] = 1

    btc_price_df = identify_trade_intervals(btc_price_df)
    btc_price_df = identify_more_sells(btc_price_df, plato)
    return btc_price_df

def identify_more_sells(btc_price_df, plato):
    # print(btc_price_df.head())
    start_interval_index = 0
    end_interval_index = 0
    for index, row in  btc_price_df.iterrows():
        if row['Start_interval'] == 1:
            start_interval_index = index

        if row['End_interval'] == 1 and start_interval_index:
            end_interval_index = index + 1 #почему то иногда подбирается предыдущий по цене пик

        if start_interval_index and end_interval_index:
            temp_df = btc_price_df.iloc[start_interval_index:end_interval_index]
            max_sell_price = max(temp_df['Price'].tolist())
            diff = (max_sell_price/100)*plato
            min_diff_sell_price = max_sell_price - diff
            max_diff_sell_price = max_sell_price + diff
            for temp_index, temp_row in  temp_df.iterrows():
                if temp_row['Price'] >= min_diff_sell_price and temp_row['Price'] <= max_diff_sell_price:
                    btc_price_df.at[temp_index, 'Sell'] = 1

            end_interval_index = None
            start_interval_index = None
            max_sell_price = None
            diff = None
    # print(btc_price_df.loc[btc_price_df['Sell'] != 0])
    return btc_price_df

def identify_trade_intervals(btc_price_df):
    # Объединяем столбцы Buy и Sell
    btc_price_df['Trade'] = btc_price_df['Buy'] - btc_price_df['Sell']
    btc_price_df['Start_interval'] = 0
    btc_price_df['End_interval'] = 0
    trade_points = btc_price_df.copy()
    trade_points = trade_points.loc[btc_price_df['Trade'] != 0]

    # Находим индексы начала и конца торговых интервалов
    in_interval = False
    last_sell_index = None
    sell_indexes = {}

    for index, trade in trade_points['Trade'].items():
        if trade == 1:  # Если есть покупка
            if in_interval and last_sell_index:
                highest_index = max(sell_indexes, key=sell_indexes.get)
                btc_price_df.loc[highest_index+6, 'End_interval'] = 1
                in_interval = False
                last_sell_index = None
                sell_indexes = {}

            if not in_interval:  # Если ещё не в интервале
                btc_price_df.loc[index, 'Start_interval'] = 1  # Начало нового интервала
                in_interval = True
                last_sell_index = None  # Сброс последней продажи

        elif trade == -1 and in_interval:  # Если есть продажа и мы в интервале
            last_sell_index = index  # Обновляем индекс последней продажи
            sell_indexes[index] = btc_price_df.loc[index, 'Price']

    # Если остались незакрытые интервалы
    if in_interval and last_sell_index is not None:
        if sell_indexes:
            highest_index = max(sell_indexes, key=sell_indexes.get)
            # btc_price_df.loc[highest_index+1, 'End_interval'] = 1
            btc_price_df.loc[highest_index, 'End_interval'] = 1

        in_interval = False
        last_sell_index = None

    btc_price_df = btc_price_df.reset_index(drop=True)
    
    del trade_points
    return btc_price_df

# def calculate_profit(btc_price_df):
#     trade_points = btc_price_df.copy()
#     trade_points = trade_points.loc[(trade_points['End_interval']!=0) | (trade_points['Start_interval']!=0)]
#     index_pairs = [(trade_points.index[i], trade_points.index[i+1]) for i in range(0, len(trade_points.index) - 1, 2)]
#     dollars = 1000
#     btc = 0 
#     sum_avg = 0
#     commision_proc = 0.001
#     for i, k in index_pairs:
#         interval = btc_price_df.iloc[i:k+1]
#         buy_prices = pd.Series([interval['Price'].iloc[i] for i in range(len(interval)) if interval['Buy'].iloc[i] == 1])
#         avg_buy_price = buy_prices.mean()
#         sell_prices = pd.Series([interval['Price'].iloc[i] for i in range(len(interval)) if interval['Sell'].iloc[i] == 1])
#         avg_sell_price = sell_prices.mean()
#         sum_avg += avg_sell_price - avg_buy_price
        
#         btc = dollars/avg_buy_price
#         btc = btc-btc*commision_proc
#         dollars = 0
#         dollars = btc*avg_sell_price
#         dollars = dollars-dollars*commision_proc
#         btc = 0

#     if btc != 0:
#         dollars += btc*sell_prices
#         btc = 0
#     return dollars, sum_avg


