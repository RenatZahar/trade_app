# model_classes.py

import pickle
import os
import re
import time
import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
import traceback
import bisect
import sys
import math
import gc
import json
import dask.dataframe as dd
from dask.distributed import Client, LocalCluster

from operator import itemgetter
from dask.delayed import delayed
from datetime import datetime, timedelta
from dask.distributed import as_completed
from config import setup_logging, BLOCKS_SQL_DATA, TRAINED_MODELS_DIR, TOTAL_AMOUNT_MORE_THAN_BTC, MIN_TXS_PER_WALLET, BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE
from .service_funcs import get_peaks_df, get_model_type
from modules.dask_client_init.get_dask_client import get_dask_client

logger = setup_logging(__name__)
# BASE_DIR = Path(__file__).resolve().parent
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

class GeneralModel(): 
    def __init__(self, model_info, init_dir_file=None):
        self.model_info = model_info
        self.model_type = model_info['model']['type']
        self.model_parameters = model_info['model']['model_param']
        self.time_parameters = model_info['model']['time_param']
        self.model = None  # Здесь будет храниться объект модели
        self.init_dir_file = init_dir_file  
        self.comment = model_info['model'].get('comment', None)
        self.model_dir = None
        self.profit_test_df = None

    def train_model_specific(self, cor_data_in_iteration_to_teach):
        """
        Абстрактный метод для специфической тренировки модели.
        Должен быть реализован в подклассе.
        """
        pass
        
    def calculate_total_value(self, data):
        model = self.model
        threshold = self.model_parameters['threshold']

        # Начальные значения
        dollar_qnt = 1000
        btc_qnt = 0
        already_bought = 0
        data_copy = data.drop(columns=['Predicted_Action', 'Action', 'Sell', 'Buy', 'Human_time', 'Timestamp', 'Price', 'Nearest_tmps_from_learning_data'], errors='ignore').copy()
        print(data_copy.head())
        # Генерация предсказаний на основе модели
        predictions = model.predict(data_copy)  # Убедитесь, что здесь удалены все неиспользуемые колонки
        
        # Добавление предсказаний к данным
        data['Predicted_Action'] = np.zeros_like(predictions)
        data.loc[predictions > threshold, 'Predicted_Action'] = 1
        data.loc[predictions < -threshold, 'Predicted_Action'] = -1
        # Расчет прибыли
        for i, row in data.iterrows():
            if row['Predicted_Action'] == 1 and not already_bought:
                btc_qnt = dollar_qnt / row['Price']
                dollar_qnt = 0  
                already_bought = 1

            elif row['Predicted_Action'] == -1 and already_bought:
                dollar_qnt = btc_qnt * row['Price']
                btc_qnt = 0  
                already_bought = 0

        # Финальная стоимость портфеля
        final_dollar_amount = dollar_qnt
        final_btc_amount = btc_qnt * row['Price']
        total_final_value = final_dollar_amount + final_btc_amount
        self.profit_test_df = data

        return total_final_value
        
    def get_start_teaching_tmsp(self):
        midnight_timestamp = get_yesterday_midnight()
        how_many_sec_in_month = 30*24*60*60
        tmsp = midnight_timestamp-(self.time_parameters['training_data_duration_months']+self.time_parameters['total_testing_period_months'])*how_many_sec_in_month
        return tmsp

    # def create_model_save_dir(self):
    #     midnight_timestamp = get_yesterday_midnight()
    #     date_time = datetime.fromtimestamp(midnight_timestamp)
    #     short_date = date_time.strftime('%Y-%m-%d %H:%M')
    #     self.model_dir = Path(TRAINED_MODELS_DIR,  f"{self.model_type}_alpha{self.model_parameters['alpha']:.5f}_{self.time_parameters['training_data_duration_months']}-{self.time_parameters['total_testing_period_months']}-{self.time_parameters['model_relevance_period_months']}-date_{short_date}".replace(':', '-').replace(' ', '_'))


    def train_with_iterations(self):
        how_many_sec_in_month = 30*24*60*60
        how_many_iterations = int(self.time_parameters['total_testing_period_months']/self.time_parameters['model_relevance_period_months'])
        how_many_iterations = max(1, how_many_iterations) 

        start_teaching_tmsp = self.get_start_teaching_tmsp()
        new_iteration_tmsp = start_teaching_tmsp
        for iteration in range(how_many_iterations):
            logger.info(f'Start main teaching iteration {iteration+1} of {how_many_iterations}')

            cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test  = self.get_corelation_df(new_iteration_tmsp, how_many_sec_in_month)
            self.train_model_specific(cor_data_in_iteration_to_teach)

            profit = self.calculate_total_value(cor_data_in_iteration_to_profit_test) #мб надо добавить как атрибут экземпляра класса 
            # profit_calcilation(prediction_df)
            logger.info(f'Result of profit test of {iteration+1} iteration: {profit}')
            print(profit)
            new_iteration_tmsp = new_iteration_tmsp + self.time_parameters['model_relevance_period_months']*how_many_sec_in_month
            self.save_model(iteration)
            gc.collect()

            # print('Расчеты временых промежутков для обучения и теста')
            # print(f'{i}')
            # print(f'peaks_data_in_iteration_to_teach  {peaks_data_in_iteration_to_teach.head(1)}')
            # print(f'{peaks_data_in_iteration_to_teach.tail(1)}')
            # print(f'peaks_data_in_iteration_to_profit_test  {peaks_data_in_iteration_to_profit_test.head(1)}')
            # print(f'{peaks_data_in_iteration_to_profit_test.tail(1)}')

    def save_model(self, iteration):
        from joblib import dump
        model = self.model

        # Сформировать путь к директории модели
        self.model_dir = self.get_model_save_dir(iteration)
        
        # Сначала создаём директорию, если она не существует
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Теперь можно безопасно сохранять DataFrame
        profit_path = self.model_dir / "profit_test_df.parquet"
        self.profit_test_df.to_parquet(profit_path)
        
        # Сохраняем модель
        model_path = self.model_dir / "model.joblib"
        dump(model, model_path)
        
        print(f"Модель сохранена по пути: {model_path}")
        print(f"DataFrame сохранён по пути: {profit_path}")
        self.move_init_data()



    def move_init_data(self):
        init_file_path = self.init_dir_file
        if init_file_path:
            try:
                # Проверяем, существует ли файл
                if init_file_path.exists():
                    with open(init_file_path, 'r', encoding='utf-8') as file:
                        init_json_data = json.load(file)
                    # Удаляем файл
                    init_file_path.unlink()
                    logger.info(f"Файл {init_file_path} успешно удалён.")
                else:
                    logger.warning(f"Файл {init_file_path} не существует и не может быть удалён.")

                trained_model_json_data = init_json_data.copy()
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                trained_model_json_data['model']['train_date'] = timestamp
                model_param_path = self.model_dir / "params_json.json"
                with open(model_param_path, 'w') as f:
                    json.dump(trained_model_json_data, f, indent=4)
            except Exception as e:
                logger.error(f"Произошла ошибка при удалении или создании файла: {e}")    
        else:
            logger.info('def move_init_data(self).json init file didn"t exist')

    def sanitize_filename(self, filename):
        # Заменяем недопустимые символы на дефис
        sanitized = re.sub(r'[<>:"/\\|?*]', '-', filename)
        # Заменяем пробелы на подчёркивания
        sanitized = sanitized.replace(' ', '_')
        return sanitized

    def get_model_save_dir(self, iteration):
        # Название папки для итерации
        raw_subdir_name = (
            f"iter_{iteration}"
            f"alpha{self.model_parameters['alpha']:.5f}_"
            f"{self.time_parameters['training_data_duration_months']}-"
            f"{self.time_parameters['total_testing_period_months']}-"
            f"{self.time_parameters['model_relevance_period_months']}"
        )
        # Санитизируем только поддиректорию
        sanitized_subdir_name = self.sanitize_filename(raw_subdir_name)
        midnight_timestamp = get_yesterday_midnight()

        # Строим путь:
        # TRAINED_MODELS_DIR / "ElasticNet172999999" / "iter_0alpha46.41589_12-6-1.5"
        return TRAINED_MODELS_DIR / (self.model_type+'_'+midnight_timestamp) / sanitized_subdir_name

    def get_corelation_df(self, new_iteration_tmsp, how_many_sec_in_month)  : # -> peaks_data_in_iteration_to_teach, peaks_data_in_iteration_to_profit_test
        # сначала получаем кошельки по точкам пиков
        # собираем их транзакции
        # фильтруем
        # считаем кореляцию
        # рассчитываем дф для обучения 
        print('________ПРОВЕРИТЬ КАКИЕ СТОЛБЦЫ В ОБУЧАЮЩЕЙ ВЫБОРКЕ')
        iterval_with_peaks_df = self.get_peaks_of_iteration(new_iteration_tmsp)
        wallets_of_peaks_list, min_block, max_block = self.get_wallets_of_peaks_list(iterval_with_peaks_df)
        chunk_size_of_wallets = 900
        TEST = 1
        if TEST:
            wallets_of_peaks_list = wallets_of_peaks_list[:chunk_size_of_wallets*50]
            
        chunks_list = get_chunks_of_wallets(wallets_of_peaks_list, chunk_size_of_wallets)

        dask_client = get_dask_client()
        all_wallets_corelation_ddf, all_txs_of_wallets_ddf = get_corelation_of_wallets_df_with_dask(chunks_list, min_block, max_block)
        cor_data_in_iteration_to_teach_df = get_data_for_teach_with_dask(iterval_with_peaks_df, all_txs_of_wallets_ddf, all_wallets_corelation_ddf)

        start_test_profit_tmsp = iterval_with_peaks_df['Timestamp'].iloc[-1]
        last_test_profit_tmsp = int(start_test_profit_tmsp+self.time_parameters['model_relevance_period_months']*how_many_sec_in_month)

        # print('start_test_profit_tmsp, last_test_profit_tmsp')
        # print(start_test_profit_tmsp, last_test_profit_tmsp)
        cor_data_in_iteration_to_profit_test_df = self.get_data_to_test(start_test_profit_tmsp, last_test_profit_tmsp, all_wallets_corelation_ddf) 
        print('cor_data_in_iteration_to_profit_test.head and tail')
        print(cor_data_in_iteration_to_profit_test_df.head(3))
        print(cor_data_in_iteration_to_profit_test_df.tail(3))

        return cor_data_in_iteration_to_teach_df, cor_data_in_iteration_to_profit_test_df

    def get_data_to_test(self, start_test_profit_tmsp, last_test_profit_tmsp, corelation_of_wallets_df):
        print('start_test_profit_tmsp, last_test_profit_tmsp')
        print(start_test_profit_tmsp, last_test_profit_tmsp)

        peaks_data = get_peaks_df()
        # print(peaks_data.head(3))
        peaks_data = peaks_data.loc[
            (peaks_data['Timestamp']>start_test_profit_tmsp) & 
            (peaks_data['Timestamp']<last_test_profit_tmsp)]
        
        # print('peaks_data')
        # print(peaks_data.head())
        # print(peaks_data.tail())
        wallets = corelation_of_wallets_df['Wallet_id'].compute().to_list()

        # wallets = corelation_of_wallets_df['Wallet_id'].to_list()
        chunk_size = 900
        wallets_list = [wallets[i:i + chunk_size] for i in range(0, len(wallets), chunk_size)]
        correletaion_df = []
#             txs_of_chunk = get_txs_of_wallets_by_tmsp(wallets_chunk, start_test_profit_tmsp, last_test_profit_tmsp)
        blocks_time = pd.read_parquet(BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE)
        blocks_time = blocks_time.loc[(blocks_time['block_times']>=start_test_profit_tmsp) & (blocks_time['block_times']<=last_test_profit_tmsp)]
        min_block, max_block  = blocks_time['block_heights'].min(), blocks_time['block_heights'].max()
        for wallets_chunk in wallets_list:
            txs_of_chunk = get_txs_of_wallets_list(wallets_chunk, min_block, max_block)
            correletaion_chunk_df = get_data_for_teach_with_dask(peaks_data, txs_of_chunk, corelation_of_wallets_df)
            correletaion_df.append(correletaion_chunk_df)

        correletaion_df = pd.concat(correletaion_df)
        correletaion_df = correletaion_df.sort_values('Timestamp')

        return correletaion_df
        # есть список корреляции кошельков
        # есть начальная и конечная точка
        # я получаю транзакции кошельков, которые есть в corelation_of_wallets_df дф в промежутке между точками
        # я разбиваю их на 10и минутные промежутки идентичные тем промежуткам которые есть в iterval_with_peaks_df
        # и считаю корреляцию в этих промежутка....(?)
        # на выходе мне нужно получить корреляционный дф по временным 10иминутным интервала для теста моделей
        


    def get_wallets_of_peaks_list(self, iterval_with_peaks_df):
        list_intervals = get_list_of_intervals(iterval_with_peaks_df)
        list_intervals = merge_intervals(list_intervals)
        blocks_of_intervals = get_blocks_of_intervals(list_intervals)
        min_block = min(blocks_of_intervals)
        max_block = max(blocks_of_intervals)
        uniq_wallets_of_blocks = get_uniq_wallets_of_blocks(blocks_of_intervals)
        return uniq_wallets_of_blocks, min_block, max_block

    def load(self, path):
    # def load_model(self, path):
    #     with open(path, 'rb') as f:
    #         self.model = pickle.load(f)
    #     print(f"Модель загружена из пути: {path}")        
        pass

    def get_peaks_of_iteration(self, new_iteration_tmsp):
        how_many_sec_in_month = 30*24*60*60
        peaks_data = get_peaks_df()
        peaks_data_in_iteration_to_teach = peaks_data.loc[
            (peaks_data['Timestamp']>new_iteration_tmsp) & 
            (peaks_data['Timestamp']<new_iteration_tmsp+self.time_parameters['training_data_duration_months']*how_many_sec_in_month)]
        # peaks_data_in_iteration_to_profit_test = peaks_data.loc[
        #     (peaks_data['Timestamp']>new_iteration_tmsp+self.time_parameters['training_data_duration_months']*how_many_sec_in_month) & 
        #     (peaks_data['Timestamp']<(new_iteration_tmsp+(self.time_parameters['training_data_duration_months']+self.time_parameters['model_relevance_period_months'])*how_many_sec_in_month))]
        # print('peaks_data_in_iteration_to_teach')
        # print(peaks_data_in_iteration_to_teach.head)
        peaks_data_in_iteration_to_teach = peaks_data_in_iteration_to_teach.sort_values('Timestamp')
        return peaks_data_in_iteration_to_teach

class ElasticNetModel(GeneralModel):
    def train_model_specific(self, cor_data_in_iteration_to_teach, n_splits=5):
        from sklearn.linear_model import ElasticNet
        from sklearn.model_selection import StratifiedKFold
        logger.info(f'Параметры модели {self.model_parameters}')
        logger.info(f'ДФ для обучения')
        logger.info(cor_data_in_iteration_to_teach.head())

        model = ElasticNet()

        print('train_model_specific cor_data_in_iteration_to_teach.head()')
        print(cor_data_in_iteration_to_teach.head())
        X = cor_data_in_iteration_to_teach.drop(columns=['Action', 'Sell', 'Buy', 'Human_time', 'Timestamp', 'Price', 'Nearest_tmps_from_learning_data'])
        y = cor_data_in_iteration_to_teach['Action']
        kf = StratifiedKFold(n_splits=n_splits)
        print('start обучение с kf.split')
        for train_index, test_index in kf.split(X, y):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            filtered_params = {key: value for key, value in self.model_parameters.items() if key != 'threshold'}

            model.set_params(**filtered_params)
            model.fit(X_train, y_train)
            threshold = self.model_parameters['threshold']
            y_pred_continuous = model.predict(X_test)
            y_pred = np.zeros_like(y_pred_continuous)  # Инициализируем массив предсказаний
            y_pred[y_pred_continuous > threshold] = 1  # возможно, можно сохранить не приведенный к 1 или -1 threshold?
            y_pred[y_pred_continuous < -threshold] = -1
            print(y_pred)
            print('ДОПИСАТЬ СРАВНЕНИЕ ВСЕХ МОДЕЛЕЙ И ПЕРЕОБУЧЕНИЯ ЛУЧШЕЙ')
            #сохранять копии модели в список, сохранять их результаты. потом брать лучшую
            self.model = model

def get_txs_of_wallets_by_tmsp(wallets_chunk, start_test_profit_tmsp, last_test_profit_tmsp, table_name='data_table'):
    placeholders = ', '.join('?' for _ in wallets_chunk)
    query = f"""
        SELECT *
        FROM {table_name}
        WHERE Wallet_id IN ({placeholders})
          AND Timestamp BETWEEN ? AND ?;
    """
    params = wallets_chunk + [start_test_profit_tmsp, last_test_profit_tmsp]
    with sqlite3.connect(BLOCKS_SQL_DATA) as conn:
        txs = pd.read_sql_query(query, conn, params=params)
    return txs


def get_data_for_teach_with_dask(iterval_with_peaks_df, all_txs_of_wallets_ddf, correlation_wallets_ddf):
    logger.info("Start get_data_for_teach_with_dask")
    logger.info("Calculating weighted_sell_correlation and other metrics")
    logger.info("Preparing data_for_teach by dropping unnecessary columns and sorting by 'Timestamp'")
    
    # Шаг 1: Подготовка data_for_teach
    data_for_teach = iterval_with_peaks_df.drop(labels=['Trade', 'Start_interval', 'End_interval'], axis=1)
    
    # Преобразование в Dask DataFrame
    data_for_teach_ddf = dd.from_pandas(data_for_teach, npartitions=1)
    data_for_teach_ddf = data_for_teach_ddf.sort_values('Timestamp').persist()
    # data_for_teach_ddf['Timestamp'] = data_for_teach_ddf['Timestamp'].astype(int)

    if isinstance(all_txs_of_wallets_ddf, pd.DataFrame):
        all_txs_of_wallets_ddf = dd.from_pandas(all_txs_of_wallets_ddf, npartitions=800)
    print('all_txs_of_wallets_ddf') 
    print(type(all_txs_of_wallets_ddf))
    # print(all_txs_of_wallets_ddf.head())

    print('correlation_wallets_ddf') 
    print(type(all_txs_of_wallets_ddf))
    print(correlation_wallets_ddf.head())
    if isinstance(all_txs_of_wallets_ddf, pd.DataFrame):
        all_txs_of_wallets_ddf = dd.from_pandas(all_txs_of_wallets_ddf, npartitions=800)
    txs_ddf = all_txs_of_wallets_ddf.merge(
        correlation_wallets_ddf,
        on='Wallet_id',
        how='left'
    )
    del correlation_wallets_ddf
    txs_ddf = txs_ddf.sort_values('Block_time')
    # txs_ddf['Block_time'] = txs_ddf['Block_time'].astype(int)

    merged_ddf = dd.merge_asof(
        txs_ddf,
        data_for_teach_ddf[['Timestamp']],
        left_on='Block_time',
        right_on='Timestamp',
        direction='nearest'
        )
    # merged_ddf = merged_ddf
    # Шаг 6: Добавление нового столбца 'Nearest_tmps_from_learning_data'
    merged_ddf['Nearest_tmps_from_learning_data'] = merged_ddf['Timestamp']

    # Шаг 7: Добавление столбца 'in_10_min_period'
    # Предполагается, что 'Block_time' и 'Nearest_tmps_from_learning_data' являются datetime
    # Используем map_partitions для корректного выполнения операций
    def calculate_in_10_min_period(df):
        df['in_10_min_period'] = (
            (df['Block_time'] >= (df['Nearest_tmps_from_learning_data'] - 300)) &
            (df['Block_time'] <= (df['Nearest_tmps_from_learning_data'] + 300))
        )
        return df

    merged_ddf = merged_ddf.map_partitions(calculate_in_10_min_period)
    
    # # # Вывод первых строк для отладки
    # print('merged_ddf.head()')
    # print(merged_ddf.head())
    
    # Шаг 8: Группировка и агрегация
    grouped_ddf = merged_ddf.groupby('Nearest_tmps_from_learning_data').agg({
        'Weighted_sell_correlation': 'sum',
        'Weighted_buy_correlation': 'sum',
        'Weighted_sell_anti_correlation': 'sum',
        'Weighted_buy_anti_correlation': 'sum',
        'WSASI-WSABI': 'sum',
        'WBABI-WBASI': 'sum',
        'Normalized_sell_amount_in_sell_interval': 'sum',
        'Normalized_sell_amount_in_buy_interval': 'sum',
        'Normalized_buy_amount_in_buy_interval': 'sum',
        'Normalized_buy_amount_in_sell_interval': 'sum',
        'SASI-SABI': 'sum',
        'BABI-BASI': 'sum'
    }).reset_index()
    
    # Вывод первых и последних строк для отладки
    # print('grouped_df.head()')
    # print(grouped_ddf.head())
    # print('grouped_df.tail()')
    # print(grouped_ddf.tail())

    # Шаг 9: Объединение сгруппированных данных обратно с data_for_teach_ddf
    print(data_for_teach_ddf.head())
    data_for_teach_ddf = data_for_teach_ddf.merge(
        grouped_ddf,
        left_on='Timestamp',
        right_on='Nearest_tmps_from_learning_data',
        how='left'
    )

    data_for_teach_ddf['CMLTV_WSC'] = 0
    data_for_teach_ddf['CMLTV_WBC'] = 0
    data_for_teach_ddf['CMLTV_WSAC'] = 0
    data_for_teach_ddf['CMLTV_WBAC'] = 0

    data_for_teach_ddf['CMLTV_N_Sell_amount_in_sell_interval'] = 0
    data_for_teach_ddf['CMLTV_N_Buy_amount_in_buy_interval'] = 0
    data_for_teach_ddf['CMLTV_SASI-SABI'] = 0
    data_for_teach_ddf['CMLTV_BABI-BASI'] = 0
    data_for_teach_ddf['CMLTV_WSASI-WSABI'] = 0
    data_for_teach_ddf['CMLTV_WBABI-WBASI'] = 0
    data_for_teach_ddf = data_for_teach_ddf.compute()
    data_for_teach_ddf = data_for_teach_ddf.sort_values('Timestamp')
    # период затухания куммулятивных сумм
    time_frame_hours = 3
    tau = time_frame_hours*6  # количество строк за 3 часа (3 часа = 18 строк по 10 минут)
    alpha = 1 - math.exp(-1 / tau) # коэффициент затухания



    data_for_teach_ddf['CMLTV_WSC'] = data_for_teach_ddf['Weighted_sell_correlation'].ewm(alpha=alpha).mean()
    data_for_teach_ddf['CMLTV_WBC'] = data_for_teach_ddf['Weighted_buy_correlation'].ewm(alpha=alpha).mean()
    data_for_teach_ddf['CMLTV_WSAC'] = data_for_teach_ddf['Weighted_sell_anti_correlation'].ewm(alpha=alpha).mean()
    data_for_teach_ddf['CMLTV_WBAC'] = data_for_teach_ddf['Weighted_buy_anti_correlation'].ewm(alpha=alpha).mean()


    data_for_teach_ddf['CMLTV_N_Sell_amount_in_sell_interval'] = data_for_teach_ddf['Normalized_sell_amount_in_sell_interval'].ewm(alpha=alpha).mean()
    data_for_teach_ddf['CMLTV_N_Buy_amount_in_buy_interval'] = data_for_teach_ddf['Normalized_buy_amount_in_buy_interval'].ewm(alpha=alpha).mean()
    data_for_teach_ddf['CMLTV_SASI-SABI'] = data_for_teach_ddf['SASI-SABI'].ewm(alpha=alpha).mean()
    data_for_teach_ddf['CMLTV_BABI-BASI'] = data_for_teach_ddf['BABI-BASI'].ewm(alpha=alpha).mean()
    data_for_teach_ddf['CMLTV_WSASI-WSABI'] = data_for_teach_ddf['WSASI-WSABI'].ewm(alpha=alpha).mean()
    data_for_teach_ddf['CMLTV_WBABI-WBASI'] = data_for_teach_ddf['WBABI-WBASI'].ewm(alpha=alpha).mean()
    data_for_teach_ddf['Action'] = data_for_teach_ddf['Buy'] - data_for_teach_ddf['Sell']
    # data_for_teach = data_for_teach.merge(grouped_df, left_on='Timestamp', right_on='Nearest_tmps_from_learning_data' ,how='left')
    data_for_teach_ddf = data_for_teach_ddf.fillna(0)
    gc.collect
    return data_for_teach_ddf


def get_data_for_old_teach_with_dask2(iterval_with_peaks_df, correlation_wallets_df, all_txs_of_wallets):
    data_for_teach = iterval_with_peaks_df.drop(labels=['Trade', 'Start_interval', 'End_interval'], axis=1) #'Number of trades',
    data_for_teach = data_for_teach.sort_values('Timestamp')
    all_txs_of_wallets = all_txs_of_wallets.set_index('Block_time').persist()
    all_txs_of_wallets = all_txs_of_wallets.map_partitions(lambda df: df.sort_index())
    print('data_for_teach.head()')
    print(data_for_teach.head())
    txs_df = all_txs_of_wallets.merge(correlation_wallets_df, on='Wallet_id', how='left')
    txs_df = txs_df.sort_values('Block_time')
    print('txs_df.head()')
    print(txs_df.head()) 
    txs_df['Nearest_tmps_from_learning_data'] = pd.merge_asof(txs_df, data_for_teach[['Timestamp']], left_on='Block_time', right_on='Timestamp', direction='nearest')['Timestamp']
    txs_df['in_10_min_period'] = 0
    txs_df['in_10_min_period'] = (txs_df['Block_time'] >= txs_df['Nearest_tmps_from_learning_data'] - 300) & (txs_df['Block_time'] <= txs_df['Nearest_tmps_from_learning_data'] + 300)
    txs_df = txs_df.reset_index(drop =True)
    print('txs_df2.head()')
    print(txs_df.head()) 
    grouped_df = txs_df.groupby('Nearest_tmps_from_learning_data').agg({
        'Weighted_sell_correlation': 'sum',
        'Weighted_buy_correlation': 'sum',
        'Weighted_sell_anti_correlation': 'sum',
        'Weighted_buy_anti_correlation': 'sum',
        'WSASI-WSABI': 'sum',
        'WBABI-WBASI': 'sum',
        'Normalized_sell_amount_in_sell_interval': 'sum',
        'Normalized_sell_amount_in_buy_interval': 'sum',
        'Normalized_buy_amount_in_buy_interval': 'sum',
        'Normalized_buy_amount_in_sell_interval': 'sum',
        'SASI-SABI': 'sum',
        'BABI-BASI': 'sum'
        })
    print('grouped_df.()')
    print(grouped_df.head()) 
    print(grouped_df.tail()) 
    data_for_teach = data_for_teach.merge(grouped_df, left_on='Timestamp', right_on='Nearest_tmps_from_learning_data' ,how='left')

    data_for_teach['CMLTV_WSC'] = 0
    data_for_teach['CMLTV_WBC'] = 0
    data_for_teach['CMLTV_WSAC'] = 0
    data_for_teach['CMLTV_WBAC'] = 0

    data_for_teach['CMLTV_N_Sell_amount_in_sell_interval'] = 0
    data_for_teach['CMLTV_N_Buy_amount_in_buy_interval'] = 0
    data_for_teach['CMLTV_SASI-SABI'] = 0
    data_for_teach['CMLTV_BABI-BASI'] = 0
    data_for_teach['CMLTV_WSASI-WSABI'] = 0
    data_for_teach['CMLTV_WBABI-WBASI'] = 0

    # период затухания куммулятивных сумм
    time_frame_hours = 3
    tau = time_frame_hours*6  # количество строк за 3 часа (3 часа = 18 строк по 10 минут)
    alpha = 1 - math.exp(-1 / tau) # коэффициент затухания

    data_for_teach['CMLTV_WSC'] = data_for_teach['Weighted_sell_correlation'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WBC'] = data_for_teach['Weighted_buy_correlation'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WSAC'] = data_for_teach['Weighted_sell_anti_correlation'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WBAC'] = data_for_teach['Weighted_buy_anti_correlation'].ewm(alpha=alpha).mean()


    data_for_teach['CMLTV_N_Sell_amount_in_sell_interval'] = data_for_teach['Normalized_sell_amount_in_sell_interval'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_N_Buy_amount_in_buy_interval'] = data_for_teach['Normalized_buy_amount_in_buy_interval'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_SASI-SABI'] = data_for_teach['SASI-SABI'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_BABI-BASI'] = data_for_teach['BABI-BASI'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WSASI-WSABI'] = data_for_teach['WSASI-WSABI'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WBABI-WBASI'] = data_for_teach['WBABI-WBASI'].ewm(alpha=alpha).mean()
    data_for_teach['Action'] = data_for_teach['Buy'] - data_for_teach['Sell']
    # data_for_teach = data_for_teach.merge(grouped_df, left_on='Timestamp', right_on='Nearest_tmps_from_learning_data' ,how='left')
    data_for_teach = data_for_teach.fillna(0)
    print('data_for_teach.head()')
    print(data_for_teach.head()) 
    return data_for_teach

def get_data_for_teach(iterval_with_peaks_df, correlation_wallets_df, all_txs_of_wallets):
    data_for_teach = iterval_with_peaks_df.drop(labels=['Trade', 'Start_interval', 'End_interval'], axis=1) #'Number of trades',
    data_for_teach = data_for_teach.sort_values('Timestamp')
    print('data_for_teach.head()')
    print(data_for_teach.head())
    txs_df = all_txs_of_wallets.merge(correlation_wallets_df, on='Wallet_id', how='left')
    txs_df = txs_df.sort_values('Block_time')
    print('txs_df.head()')
    print(txs_df.head()) 
    txs_df['Nearest_tmps_from_learning_data'] = pd.merge_asof(txs_df, data_for_teach[['Timestamp']], left_on='Block_time', right_on='Timestamp', direction='nearest')['Timestamp']
    txs_df['in_10_min_period'] = 0
    txs_df['in_10_min_period'] = (txs_df['Block_time'] >= txs_df['Nearest_tmps_from_learning_data'] - 300) & (txs_df['Block_time'] <= txs_df['Nearest_tmps_from_learning_data'] + 300)
    txs_df = txs_df.reset_index(drop =True)
    print('txs_df2.head()')
    print(txs_df.head()) 
    grouped_df = txs_df.groupby('Nearest_tmps_from_learning_data').agg({
        'Weighted_sell_correlation': 'sum',
        'Weighted_buy_correlation': 'sum',
        'Weighted_sell_anti_correlation': 'sum',
        'Weighted_buy_anti_correlation': 'sum',
        'WSASI-WSABI': 'sum',
        'WBABI-WBASI': 'sum',
        'Normalized_sell_amount_in_sell_interval': 'sum',
        'Normalized_sell_amount_in_buy_interval': 'sum',
        'Normalized_buy_amount_in_buy_interval': 'sum',
        'Normalized_buy_amount_in_sell_interval': 'sum',
        'SASI-SABI': 'sum',
        'BABI-BASI': 'sum'
        })
    print('grouped_df.()')
    print(grouped_df.head()) 
    print(grouped_df.tail()) 
    data_for_teach = data_for_teach.merge(grouped_df, left_on='Timestamp', right_on='Nearest_tmps_from_learning_data' ,how='left')

    data_for_teach['CMLTV_WSC'] = 0
    data_for_teach['CMLTV_WBC'] = 0
    data_for_teach['CMLTV_WSAC'] = 0
    data_for_teach['CMLTV_WBAC'] = 0

    data_for_teach['CMLTV_N_Sell_amount_in_sell_interval'] = 0
    data_for_teach['CMLTV_N_Buy_amount_in_buy_interval'] = 0
    data_for_teach['CMLTV_SASI-SABI'] = 0
    data_for_teach['CMLTV_BABI-BASI'] = 0
    data_for_teach['CMLTV_WSASI-WSABI'] = 0
    data_for_teach['CMLTV_WBABI-WBASI'] = 0

    # период затухания куммулятивных сумм
    time_frame_hours = 3
    tau = time_frame_hours*6  # количество строк за 3 часа (3 часа = 18 строк по 10 минут)
    alpha = 1 - math.exp(-1 / tau) # коэффициент затухания

    data_for_teach['CMLTV_WSC'] = data_for_teach['Weighted_sell_correlation'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WBC'] = data_for_teach['Weighted_buy_correlation'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WSAC'] = data_for_teach['Weighted_sell_anti_correlation'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WBAC'] = data_for_teach['Weighted_buy_anti_correlation'].ewm(alpha=alpha).mean()


    data_for_teach['CMLTV_N_Sell_amount_in_sell_interval'] = data_for_teach['Normalized_sell_amount_in_sell_interval'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_N_Buy_amount_in_buy_interval'] = data_for_teach['Normalized_buy_amount_in_buy_interval'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_SASI-SABI'] = data_for_teach['SASI-SABI'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_BABI-BASI'] = data_for_teach['BABI-BASI'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WSASI-WSABI'] = data_for_teach['WSASI-WSABI'].ewm(alpha=alpha).mean()
    data_for_teach['CMLTV_WBABI-WBASI'] = data_for_teach['WBABI-WBASI'].ewm(alpha=alpha).mean()
    data_for_teach['Action'] = data_for_teach['Buy'] - data_for_teach['Sell']
    # data_for_teach = data_for_teach.merge(grouped_df, left_on='Timestamp', right_on='Nearest_tmps_from_learning_data' ,how='left')
    data_for_teach = data_for_teach.fillna(0)
    print('data_for_teach.head()')
    print(data_for_teach.head()) 
    return data_for_teach

def merge_intervals(intervals):
    logger.info(" Start merge_intervals")

    # Сортируем интервалы по их началу
    intervals.sort(key=lambda x: x[0])

    merged = []
    for interval in intervals:
        if not merged or merged[-1][1] < interval[0]:
            # Если список пуст или предыдущий интервал не пересекается с текущим,
            # добавляем текущий интервал в результат
            merged.append(interval)
        else:
            # Есть пересечение, объединяем интервалы
            merged[-1][1] = max(merged[-1][1], interval[1])

    return merged


def get_yesterday_midnight():
    # Определяем полночь сегодня 
    now = datetime.now()
    today_midnight = datetime(now.year, now.month, now.day)
    today_midnight = int(today_midnight.timestamp())
    return today_midnight


def get_list_of_intervals(btc_price_df_with_intervals):
    logger.info(" Start get_list_of_intervals")
    intervals = transform_btc_to_intervals(btc_price_df_with_intervals)
    list_intervals = []
    # print(intervals) 
    for index, row in intervals.iterrows():
        list_intervals.append([int(row['Start']), int(row['End'])])
    return list_intervals

def transform_btc_to_intervals(btc_price_df_with_intervals):
    logger.info(" Start transform_btc_to_intervals")

    btc_price_df_with_intervals = btc_price_df_with_intervals.loc[(btc_price_df_with_intervals['Buy'] == 1) | (btc_price_df_with_intervals['Sell'] == 1)]
    timestapms = pd.DataFrame()
    timestapms['Timestamp'] = btc_price_df_with_intervals['Timestamp']
    timestapms['Start'] = timestapms['Timestamp'] - 600
    timestapms['End'] = timestapms['Timestamp'] + 600
    return timestapms


# def find_block_height_range(times_sorted, heights_sorted, start_time, end_time):
#     logger.info(" Start find_block_height_range")

#     """
#     С помощью бинарного поиска находим диапазон индексов для интервала времени,
#     затем возвращаем соответствующие минимальный и максимальный Block_height.
#     """
#     left_index = bisect.bisect_left(times_sorted, start_time)
#     right_index = bisect.bisect_right(times_sorted, end_time)
#     if left_index == right_index:
#         return None, None
#     min_height = heights_sorted[left_index]
#     max_height = heights_sorted[right_index - 1]
#     return min_height, max_height


def get_blocks_of_intervals(intervals, table_name='data_table'):
    logger.info(" Start get_blocks_of_intervals")

    # Предполагается, что intervals уже объединены функцией merge_intervals.
    # intervals - список вида [[start_time, end_time], ...]
    # Но в данном подходе мы просто формируем полный диапазон блоков от минимального до максимального.

    db_path = BLOCKS_SQL_DATA
    if isinstance(db_path, Path):
        db_path = str(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Сначала найдём минимальный и максимальный Block_height
    cursor.execute(f"SELECT MIN(Block_height), MAX(Block_height) FROM {table_name};")
    result = cursor.fetchone()
    if not result or result[0] is None or result[1] is None:
        # Нет данных
        cursor.close()
        conn.close()
        return []

    min_block_height, max_block_height = result[0], result[1]
    is_height_time = os.path.isfile(BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE)
    if is_height_time:
        df = pd.read_parquet(BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE)
        block_heights = df['block_heights']
        min_df_block = block_heights.min()
        max_df_block = block_heights.max()
        check_for_min_block = min_block_height == min_df_block
        check_for_max_block = max_block_height == max_df_block
    # Теперь у нас есть диапазон [min_block_height, max_block_height]
    # Предполагается, что блоки идут подряд от min до max без пропусков.
    # Для каждого блока получим Block_time.
    if is_height_time:
        if check_for_min_block and check_for_max_block:
            block_times = df['block_times']
            print('block_times читаем из файла')


    else:
        block_heights = []
        block_times = []

        total_blocks = max_block_height - min_block_height + 1
        count = 0

        for bh in range(min_block_height, max_block_height + 1):
            cursor.execute(f"""
                SELECT Block_time 
                FROM {table_name}
                WHERE Block_height = ?;
            """, (bh,))
            row = cursor.fetchone()
            if row:
                block_time = row[0]
                block_heights.append(bh)
                block_times.append(block_time)

            # count += 1
            # if count % 10000 == 0:
            #     sys.stdout.write(f"\rОбработано {count} блоков из {total_blocks}")
            #     sys.stdout.flush()

        cursor.close()
        conn.close()
        df = pd.DataFrame({
            'block_heights': block_heights,
            'block_times': block_times
        })
        df.to_parquet(BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE)
        logger.info('Новый BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE сохранен')
    # Теперь, имея полную карту (Block_height -> Block_time),
    # определим, какие блоки попадают в заданные интервалы времени.
    all_blocks = []
    # block_times отсортированы по возрастанию Block_height, следовательно, по времени.
    # Можно использовать бинарный поиск.
    for (start_time, end_time) in intervals:
        left_index = bisect.bisect_left(block_times, start_time)
        right_index = bisect.bisect_right(block_times, end_time)
        if left_index < right_index:
            all_blocks.extend(block_heights[left_index:right_index])

    return all_blocks


def get_uniq_wallets_of_blocks(block_list, table_name='data_table'):
    logger.info(" Start get_uniq_wallets_of_blocks")

    db_path = BLOCKS_SQL_DATA
    if isinstance(db_path, Path):
        db_path = str(db_path)

    unique_wallets = set()
    chunk_size = 900  # Уменьшенный размер чанка для безопасности

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        for i in range(0, len(block_list), chunk_size):
            chunk = block_list[i:i+chunk_size]
            if not chunk:
                continue
            placeholders = ",".join("?" * len(chunk))
            query = f"""
                SELECT DISTINCT Wallet_id
                FROM {table_name}
                WHERE Block_height IN ({placeholders});
            """
            try:
                cursor.execute(query, chunk)
                rows = cursor.fetchall()
                unique_wallets.update(r[0] for r in rows)
            except sqlite3.OperationalError as e:
                logger.error(f"Ошибка выполнения SQL запроса: {e}")
                continue  # Можно решить, как обрабатывать такие случаи

    return list(unique_wallets)

def get_corelation_of_wallets_df_with_dask(chunks_list, min_block, max_block):
    logger.info(" Start get_corelation_of_wallets_df with Dask")
    logger.info("correlation_df['Weighted_sell_correlation'] = correlation_df['Normalized_sell_amount_in_sell_interval'] * correlation_df['sell_txs_qnty']")
    logger.info('ПОЗДНЕЕ ПРОВЕРИТЬ КАК ПОКАЗЫВАЕ СЕБЯ ДЕЛЕНИЕ В ЭТОЙ ХАРАКТЕРИСТИКЕ. ПРИ УМНОЖЕНИИ - УСИЛИВАЕМ ВНИМАНИЕ ОТ КОЛ-ВА ТРАНЗАКЦИЙ. МБ НАДО ДЕЛАТЬ ТАК')
    logger.info("weighted_sell_correlation = (correlation_df['Normalized_sell_amount_in_sell_interval'] * correlation_df['sell_txs_qnty']).sum() / correlation_df['sell_txs_qnty'].sum()")
    logger.info('ПРОВЕРИТЬ ПОТОМ ПРИВЕДЕНИЕ ЗНАЧЕНИЙ К ДИАПАЗОНУ ОТ -1 ДО 1')
    print('забить npartitions от размера а не от кол-ва')
    # Функция обработки одного чанка
    peaks_data = get_peaks_df()
    npartitions = 500
    @delayed
    def process_chunk(chunk_wallets):
        # Получение транзакций
        txs_of_chunk = get_txs_of_wallets_list(chunk_wallets, min_block, max_block)
        if txs_of_chunk.empty:
            return pd.DataFrame(), pd.DataFrame()
        
        # Фильтрация транзакций
        txs_of_chunk = filter_txs_of_chunk(txs_of_chunk)
        
        # Нормализация сумм
        txs_of_chunk = normalize_amount(txs_of_chunk)
        
        # Импорт интервалов пиков
        txs_of_chunk_with_intervals = import_peak_intervals(txs_of_chunk, peaks_data)
        
        # Расчет корреляций
        correlation_wallets_df = calculate_correlations_of_wallets(txs_of_chunk_with_intervals)
        txs_of_chunk_with_intervals = txs_of_chunk_with_intervals.fillna(0)  
        correlation_wallets_df = correlation_wallets_df.fillna(0)

        del txs_of_chunk, chunk_wallets
        gc.collect()
        return correlation_wallets_df, txs_of_chunk_with_intervals

    #   НАВЕРНО ТУТ ЗАПИСЫВАТЬ TXS DF В БЖ
    # И ТОГДА МОЖНО СДЕЛАТЬ МНОГО ВОРКЕРОВ ПО ДВА ПОТОКА
    # сохранять транзакции кошельков из даска в бд иначе никак В process_chunk
    # ИЛИ В ДАСКЕ ФОРМИРОВАТЬ СРАЗУ ДФ ДЛЯ ОБУЧЕНИЯ
    # ФОРМИРОВАТЬ КОРРЕЛЯЦИОННЫЙ ВАЛЛЕТ ДФ 
    # А ПОТОМ СОБИРАТЬ ТРАНЗАКЦИИ КОШЕЛЬКОВ ПО ВРЕМЕННЫМ МЕТКАМ
    # calculate_correlations_of_wallets_optimized

    # Создаём список delayed вызовов для всех чанков
    delayed_results = [process_chunk(chunk) for chunk in chunks_list]
    
    # Разделяем результаты на два отдельных списка delayed DataFrame с использованием itemgetter
    delayed_correlation = [delayed(itemgetter(0))(result) for result in delayed_results]
    delayed_txs = [delayed(itemgetter(1))(result) for result in delayed_results]
    
    # Создание Dask DataFrame из delayed объектов
    if delayed_correlation:
        all_wallets_corelation_ddf = dd.from_delayed(delayed_correlation)
        all_wallets_corelation_ddf = all_wallets_corelation_ddf.repartition(npartitions=10)
        all_wallets_corelation_ddf = all_wallets_corelation_ddf.persist()
    else:
        all_wallets_corelation_ddf = dd.from_pandas(pd.DataFrame(), npartitions=1)
    
    if delayed_txs:
        all_txs_of_wallets_ddf = dd.from_delayed(delayed_txs)
        all_txs_of_wallets_ddf = all_txs_of_wallets_ddf.repartition(npartitions=npartitions)
    else:
        all_txs_of_wallets_ddf = dd.from_pandas(pd.DataFrame(), npartitions=1)

    return all_wallets_corelation_ddf, all_txs_of_wallets_ddf


def get_corelation_of_wallets_df(wallets_list, min_block, max_block):
    logger.info(" Start get_corelation_of_wallets_df")

    # разбиваем кошельки на чанки
    # итерация по чанкам
    #     собираем транзакции кошельков
    #     фильтруем кошельки в чанке (оборот и кол-во txs)
    #     рассчитываем и записываем кореляцию
    # ретерн кореляция КОШЕЛЬКОВ дф

    chunk_size_of_wallets = 900
    chunks_list = get_chunks_of_wallets(wallets_list, chunk_size_of_wallets)


    correlation_dfs = []
    txs_list = []
    peaks_data = get_peaks_df()

    for number, i in enumerate(chunks_list):
        txs_of_chunk = get_txs_of_wallets_list(i, min_block, max_block)
        if not txs_of_chunk:
            continue
        # sys.stdout.write(f"\rОбработано {number} чанков из {len(chunks_list)}")
        # sys.stdout.flush()
        # print(txs_of_chunk.head())
        txs_of_chunk = filter_txs_of_chunk(txs_of_chunk)

        txs_of_chunk = normalize_amount(txs_of_chunk)
        txs_of_chunk_with_intervals = import_peak_intervals(txs_of_chunk, peaks_data)
        txs_list.append(txs_of_chunk_with_intervals)
        correlation_wallets_df = calculate_correlations_of_wallets_optimized(txs_of_chunk_with_intervals)
        correlation_dfs.append(correlation_wallets_df)
        print(f"\rОбработано {number+1} чанков из {len(chunks_list)}")
        print(f'Размер чанка кошельков: {len(i)}')
        # Подсчет памяти всех DataFrame в txs_list
        mem_bytes = sum(df.memory_usage(deep=True).sum() for df in txs_list)
        mem_mb = mem_bytes / (1024 * 1024)
        print(f"Размер txs_list примерно: {mem_mb:.2f} MB")

        del txs_of_chunk, txs_of_chunk_with_intervals

    all_wallets_corelation_df = pd.concat(correlation_dfs, ignore_index=True).reset_index(drop=True)
    all_txs_of_wallets = pd.concat(txs_list, ignore_index=True).reset_index(drop=True)
    all_txs_of_wallets = all_txs_of_wallets.sort_values('Timestamp')

    del txs_list
    return all_wallets_corelation_df, all_txs_of_wallets

def calculate_correlations_of_wallets_optimized(ddf):
    logger.info('Start calculate_correlations_of_wallets_optimized')
    """
    Вычисляет корреляционные коэффициенты для каждого кошелька.
    """
    # Создаем новые столбцы для произведений, необходимых для корреляций
    ddf = ddf.assign(
        NSA_ISI = ddf['Normalized_sell_amount'] * ddf['in_sell_interval'],
        NSA_IBI = ddf['Normalized_sell_amount'] * ddf['in_buy_interval'],
        NBA_IBI = ddf['Normalized_buy_amount'] * ddf['in_buy_interval'],
        NBA_ISI = ddf['Normalized_buy_amount'] * ddf['in_sell_interval']
    )

    # Определяем необходимые агрегаты
    grouped = ddf.groupby('Wallet_id').agg({
        'Normalized_sell_amount': ['mean', 'std'],
        'Normalized_buy_amount': ['mean', 'std'],
        'in_sell_interval': ['mean', 'std'],
        'in_buy_interval': ['mean', 'std'],
        'Amount': ['count', lambda x: (x < 0).sum(), lambda x: (x > 0).sum()],
        'NSA_ISI': 'mean',
        'NSA_IBI': 'mean',
        'NBA_IBI': 'mean',
        'NBA_ISI': 'mean',
    })

    # Переименовываем столбцы для удобства
    grouped.columns = ['_'.join(col).strip() for col in grouped.columns.values]

    # Вычисляем корреляционные коэффициенты
    grouped = grouped.assign(
        cor_NSA_ISI = (
            (grouped['NSA_ISI'] - grouped['Normalized_sell_amount_mean'] * grouped['in_sell_interval_mean']) /
            (grouped['Normalized_sell_amount_std'] * grouped['in_sell_interval_std'])
        ),
        cor_NSA_IBI = (
            (grouped['NSA_IBI'] - grouped['Normalized_sell_amount_mean'] * grouped['in_buy_interval_mean']) /
            (grouped['Normalized_sell_amount_std'] * grouped['in_buy_interval_std'])
        ),
        cor_NBA_IBI = (
            (grouped['NBA_IBI'] - grouped['Normalized_buy_amount_mean'] * grouped['in_buy_interval_mean']) /
            (grouped['Normalized_buy_amount_std'] * grouped['in_buy_interval_std'])
        ),
        cor_NBA_ISI = (
            (grouped['NBA_ISI'] - grouped['Normalized_buy_amount_mean'] * grouped['in_sell_interval_mean']) /
            (grouped['Normalized_buy_amount_std'] * grouped['in_sell_interval_std'])
        )
    )

    # Заменяем NaN на 0.0
    grouped = grouped.fillna(0.0)

    # Добавляем дополнительные взвешенные корреляции
    grouped = grouped.assign(
        Weighted_sell_correlation = grouped['cor_NSA_ISI'] * grouped['Amount_<lambda_0>'],
        Weighted_buy_correlation = grouped['cor_NBA_IBI'] * grouped['Amount_<lambda_1>'],
        Weighted_sell_anti_correlation = grouped['cor_NSA_IBI'] * grouped['Amount_<lambda_0>'],
        Weighted_buy_anti_correlation = grouped['cor_NBA_ISI'] * grouped['Amount_<lambda_1>'],
        SASI_SABI = grouped['cor_NSA_ISI'] - grouped['cor_NSA_IBI'],
        BABI_BASI = grouped['cor_NBA_IBI'] - grouped['cor_NBA_ISI'],
        WSASI_WSABI = grouped['Weighted_sell_correlation'] - grouped['Weighted_sell_anti_correlation'],
        WBABI_WBASI = grouped['Weighted_buy_correlation'] - grouped['Weighted_buy_anti_correlation']
    )

    # Создаём итоговый DataFrame
    correlation_df = grouped.reset_index()[[
        'Wallet_id',
        'Normalized_sell_amount_mean',
        'Normalized_sell_amount_std',
        'Normalized_buy_amount_mean',
        'Normalized_buy_amount_std',
        'in_sell_interval_mean',
        'in_sell_interval_std',
        'in_buy_interval_mean',
        'in_buy_interval_std',
        'Amount_count',
        'Amount_<lambda_0>',
        'Amount_<lambda_1>',
        'NSA_ISI',
        'NSA_IBI',
        'NBA_IBI',
        'NBA_ISI',
        'cor_NSA_ISI',
        'cor_NSA_IBI',
        'cor_NBA_IBI',
        'cor_NBA_ISI',
        'Weighted_sell_correlation',
        'Weighted_buy_correlation',
        'Weighted_sell_anti_correlation',
        'Weighted_buy_anti_correlation',
        'SASI_SABI',
        'BABI_BASI',
        'WSASI_WSABI',
        'WBABI_WBASI'
    ]]

    # Переименование столбцов для соответствия исходной функции
    correlation_df = correlation_df.rename(columns={
        'Normalized_sell_amount_mean': 'mean_Normalized_sell_amount',
        'Normalized_sell_amount_std': 'std_Normalized_sell_amount',
        'Normalized_buy_amount_mean': 'mean_Normalized_buy_amount',
        'Normalized_buy_amount_std': 'std_Normalized_buy_amount',
        'in_sell_interval_mean': 'mean_in_sell_interval',
        'in_sell_interval_std': 'std_in_sell_interval',
        'in_buy_interval_mean': 'mean_in_buy_interval',
        'in_buy_interval_std': 'std_in_buy_interval',
        'Amount_count': 'count_txs_qnty',
        'Amount_<lambda_0>': 'sell_txs_qnty',
        'Amount_<lambda_1>': 'buy_txs_qnty',
        'NSA_ISI': 'mean_NSA_ISI',
        'NSA_IBI': 'mean_NSA_IBI',
        'NBA_IBI': 'mean_NBA_IBI',
        'NBA_ISI': 'mean_NBA_ISI',
        'SASI_SABI': 'SASI-SABI',
        'BABI_BASI': 'BABI-BASI',
        'WSASI_WSABI': 'WSASI-WSABI',
        'WBABI_WBASI': 'WBABI-WBASI'
    })

    gc.collect()

    return correlation_df

def calculate_correlations_of_wallets(txs_of_chunk_with_intervals):
    # Сгруппируем транзакции по кошельку и применим функцию calculate_correlations
    # print(txs_of_chunk_with_intervals.info())
    txs_of_chunk_with_intervals = txs_of_chunk_with_intervals.reset_index(drop=True)
    grouped = txs_of_chunk_with_intervals.groupby('Wallet_id')
    correlation_data = grouped.apply(calculate_correlations)

    correlation_df = pd.DataFrame(correlation_data).reset_index(drop=True)
    correlation_df = correlation_df.fillna(0.0)

    # Добавляем дополнительные взвешенные корреляции
    correlation_df['Weighted_sell_correlation'] = correlation_df['Normalized_sell_amount_in_sell_interval'] * correlation_df['sell_txs_qnty']
    correlation_df['Weighted_buy_correlation'] = correlation_df['Normalized_buy_amount_in_buy_interval'] * correlation_df['buy_txs_qnty']
    correlation_df['Weighted_sell_anti_correlation'] = correlation_df['Normalized_sell_amount_in_buy_interval'] * correlation_df['sell_txs_qnty']
    correlation_df['Weighted_buy_anti_correlation'] = correlation_df['Normalized_buy_amount_in_sell_interval'] * correlation_df['buy_txs_qnty']
    correlation_df['SASI-SABI'] = correlation_df['Normalized_sell_amount_in_sell_interval']-correlation_df['Normalized_sell_amount_in_buy_interval']
    correlation_df['BABI-BASI'] = correlation_df['Normalized_buy_amount_in_buy_interval']-correlation_df['Normalized_buy_amount_in_sell_interval']
    correlation_df['WSASI-WSABI'] = correlation_df['Weighted_sell_correlation']-correlation_df['Weighted_sell_anti_correlation']
    correlation_df['WBABI-WBASI'] = correlation_df['Weighted_buy_correlation']-correlation_df['Weighted_buy_anti_correlation']
    gc.collect()

    # print(correlation_df.head())
    return correlation_df

def calculate_correlations(group):
    correlation_matrix = group[
        ['Normalized_sell_amount', 'Normalized_buy_amount', 'in_sell_interval', 'in_buy_interval']
    ].corr(method='pearson')
    wallet_id = group['Wallet_id'].iloc[0]
    sell_txs = len(group.loc[group['Amount'] < 0])
    buy_txs = len(group.loc[group['Amount'] > 0])
    result = pd.Series([
        wallet_id,
        correlation_matrix.loc['Normalized_sell_amount', 'in_sell_interval'],
        correlation_matrix.loc['Normalized_sell_amount', 'in_buy_interval'],
        correlation_matrix.loc['Normalized_buy_amount', 'in_buy_interval'],
        correlation_matrix.loc['Normalized_buy_amount', 'in_sell_interval'],
        sell_txs,
        buy_txs
    ], index=[
        'Wallet_id',
        'Normalized_sell_amount_in_sell_interval',
        'Normalized_sell_amount_in_buy_interval',
        'Normalized_buy_amount_in_buy_interval',
        'Normalized_buy_amount_in_sell_interval',
        'sell_txs_qnty', 
        'buy_txs_qnty'
    ])
    gc.collect()
    return result

def import_peak_intervals(txs_of_chunk, peaks_data):
    # Предполагается, что txs_of_chunk отсортирован по 'Block_time', иначе:
    txs_of_chunk = txs_of_chunk.sort_values('Block_time')
    
    temp_buy = peaks_data[peaks_data['Buy'] > 0]['Timestamp'].values
    temp_sell = peaks_data[peaks_data['Sell'] > 0]['Timestamp'].values

    txs_of_chunk['in_sell_interval'] = 0
    txs_of_chunk['in_buy_interval'] = 0
    
    block_time = txs_of_chunk['Block_time'].values

    in_sell = txs_of_chunk['in_sell_interval'].values
    in_buy = txs_of_chunk['in_buy_interval'].values

    for tmsp in temp_sell:
        start = tmsp - 300
        end = tmsp + 300
        left = np.searchsorted(block_time, start, side='left')
        right = np.searchsorted(block_time, end, side='right')
        in_sell[left:right] = -1

    for tmsp in temp_buy:
        start = tmsp - 300
        end = tmsp + 300
        left = np.searchsorted(block_time, start, side='left')
        right = np.searchsorted(block_time, end, side='right')
        in_buy[left:right] = 1

    txs_of_chunk['in_sell_interval'] = in_sell
    txs_of_chunk['in_buy_interval'] = in_buy
    # print('_______txs_of_chunk')
    # print(txs_of_chunk.head())
    return txs_of_chunk

def import_peak_intervals_old(txs_of_chunk, peaks_data):
    # Загрузка данных без Dask, просто pandas
    temp_buy = peaks_data[peaks_data['Buy'] > 0]['Timestamp'].values
    temp_sell = peaks_data[peaks_data['Sell'] > 0]['Timestamp'].values

    # Добавление столбцов для отметок
    txs_of_chunk['in_sell_interval'] = 0
    txs_of_chunk['in_buy_interval'] = 0

    def mark_intervals(df, timestamps, column):
        for tmsp in timestamps:
            start = tmsp - 300
            end = tmsp + 300
            mask = (df['Block_time'] >= start) & (df['Block_time'] <= end)
            if column == 'in_sell_interval':
                df.loc[mask, column] = -1
            else:
                df.loc[mask, column] = 1
        return df

    # Применяем функцию к df для sell и buy интервалов
    txs_of_chunk = mark_intervals(txs_of_chunk, temp_sell, 'in_sell_interval')
    txs_of_chunk = mark_intervals(txs_of_chunk, temp_buy, 'in_buy_interval')
    return txs_of_chunk

def normalize_amount(txs_of_chunk):
    normalized_chunk = txs_of_chunk.groupby('Wallet_id').apply(normalize).reset_index(drop=True)
    # normalized_chunk['Normalized_sell_amount'] = normalized_chunk['Normalized_sell_amount'].fillna(0.0)
    # normalized_chunk['Normalized_buy_amount'] = normalized_chunk['Normalized_buy_amount'].fillna(0.0)
    return normalized_chunk

def min_max_normalize_shift(series):
    min_val = series.min()
    max_val = series.max()
    if min_val == max_val:
        return pd.Series([float(0)] * len(series), index=series.index)
    normalized = (series - min_val) / (max_val - min_val)
    return normalized

def normalize(group):
    group = group.copy()  # чтобы избежать SettingWithCopy
    positive = group[group['Amount'] > 0]
    negative = group[group['Amount'] < 0]
    
    # Инициализируем столбцы, если их ещё нет
    if 'Normalized_buy_amount' not in group.columns:
        group['Normalized_buy_amount'] = 0.0
    if 'Normalized_sell_amount' not in group.columns:
        group['Normalized_sell_amount'] = 0.0

    if len(positive) > 0:
        # Применяем нормализацию к подмножеству positive и записываем результаты обратно
        norm_buy = min_max_normalize_shift(positive['Amount'])
        group.loc[positive.index, 'Normalized_buy_amount'] = norm_buy
        
    if len(negative) > 0:
        norm_sell = min_max_normalize_shift(negative['Amount'])
        # Знак минус, как задумано
        group.loc[negative.index, 'Normalized_sell_amount'] = -norm_sell
    
    return group

def filter_txs_of_chunk(txs_of_chunk):
    aggregated_ddf = txs_of_chunk.groupby('Wallet_id').agg({
        'Amount': 'sum',  # Пример агрегации (сумма транзакций)
        'Block_time': 'max',  # Максимальное значение времени блока
        'Transaction_id': 'count'  # Количество транзакций в группе
    })

    filtered_aggregated_ddf = aggregated_ddf[
        (aggregated_ddf['Amount'] >= TOTAL_AMOUNT_MORE_THAN_BTC) & 
        (aggregated_ddf['Transaction_id'] >= MIN_TXS_PER_WALLET) 
        ]
    txs_of_chunk = txs_of_chunk[txs_of_chunk['Wallet_id'].isin(filtered_aggregated_ddf.index)]
    return txs_of_chunk

def get_chunks_of_wallets(wallets_list, chunk_size):
    logger.info(" Start get_chunks_of_wallets")

    chunk_list = []
    for i in range(0, len(wallets_list), chunk_size):
        chunk = wallets_list[i:i+chunk_size]
        chunk_list.append(chunk)
    return chunk_list

def get_txs_of_wallets_list(wallet_list, min_block, max_block, table_name='data_table'):
    # print('верояно, надо создавать отдельную бд под txs целевых кошельков')
    """
    Получает транзакции для списка кошельков, фильтруя их по диапазону высот блоков.
    
    Параметры:
    - wallet_list (list): Список Wallet_id для выборки.
    - min_block (int): Минимальная высота блока.
    - max_block (int): Максимальная высота блока.
    - table_name (str): Имя таблицы в базе данных.
    
    Возвращает:
    - pd.DataFrame: DataFrame с транзакциями, удовлетворяющими критериям.
    """
    # logger.info("Start get_txs_of_wallets_list")

    db_path = BLOCKS_SQL_DATA
    if isinstance(db_path, Path):
        db_path = str(db_path)

    if not wallet_list:
        logger.warning("Empty wallet_list provided.")
        return pd.DataFrame()

    chunk_size = 900  # Уменьшенный размер чанка для безопасности (SQLite имеет ограничение на количество параметров, обычно 999)
    frames = []

    with sqlite3.connect(db_path) as conn:
        set_sqlite_pragma(conn)
        cursor = conn.cursor()
        for i in range(0, len(wallet_list), chunk_size):
            chunk = wallet_list[i:i + chunk_size]
            if not chunk:
                continue
            placeholders_wallet = ",".join("?" * len(chunk))
            query = f"""
                SELECT *
                FROM {table_name}
                WHERE Wallet_id IN ({placeholders_wallet})
                AND Block_height BETWEEN ? AND ?;
            """
            # Добавляем min_block и max_block к параметрам запроса
            params = chunk + [min_block, max_block]
            try:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]
                df_chunk = pd.DataFrame(rows, columns=column_names)
                frames.append(df_chunk)
                # logger.info(f"Processed chunk {i//chunk_size + 1} / ~{(len(wallet_list)//len(chunk))+1} with {len(chunk)} Wallet_id.")
            except sqlite3.OperationalError as e:
                logger.error(f"SQL query failed for chunk {i//chunk_size + 1}: {e}")
                continue

    if frames:
        df = pd.concat(frames, ignore_index=True)
    else:
        df = pd.DataFrame()

    # logger.info(f"Total transactions retrieved: {len(df)}")
    return df

def set_sqlite_pragma(conn):
    """
    Устанавливает оптимальные параметры PRAGMA для улучшения производительности.
    """
    cursor = conn.cursor()
    cursor.execute("PRAGMA synchronous = OFF;")  # Повышает скорость записи, но снижает безопасность
    cursor.execute("PRAGMA journal_mode = WAL;")  # Устанавливает режим WAL для улучшения параллельности чтения/записи
    cursor.execute("PRAGMA cache_size = 100000;")  # Увеличивает размер кэша
    cursor.execute("PRAGMA temp_store = MEMORY;")  # Хранит временные таблицы в памяти
    cursor.close()

# Пример использования:
# list_intervals = [[1686775320, 1686776520], [1686775920, 1686777120], [1686776520, 1686777720]]
# blocks_list_in_interval = get_blocks_list_in_interval(list_intervals)
# print(blocks_list_in_interval)


# fast-api,пример:
# @app.post("/items/")
# async def create_item(item: Item) -> Item:
#     return item
# пример вызова функции из браузера (и не только) по запросу

# библиотека Jinja2 - рендеринг html шаблонов

# Аннотация типов
# def greet(name: str) -> str:
#     return f"Привет, {name}!"
# В данном примере:

# name: str указывает, что параметр name должен быть строкой.
# -> str указывает, что функция возвращает строку.



# ** - распаковка словаря в виде именованных аргументов
# def greet(name, greeting):
#     print(f"{greeting}, {name}!")

# params = {
#     "name": "Алиса",
#     "greeting": "Привет"
# }

# greet(**params)  # Эквивалентно greet(name="Алиса", greeting="Привет")





# Динамическое создание классов моделей
# Если у вас много различных моделей, можно динамически создавать экземпляры классов на основе типа модели, указанного в конфигурации.

# MODEL_CLASSES = {
#     "ElasticNet": ElasticNetModel,
#     "RandomForest": RandomForestModel,
#     # Добавьте другие модели здесь
# }

# def teach_models(model_info):
#     model_type = list(model_info.keys())[0]
#     model_class = MODEL_CLASSES.get(model_type)
#     if not model_class:
#         print(f"Неизвестный тип модели: {model_type}")
#         return
#     model = model_class(model_info)
#     # Предположим, что у вас есть данные X и y
#     X, y = get_training_data()
#     model.train(X, y)