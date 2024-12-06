# model_classes.py

import pickle
import os
import time
import numpy as np
from abc import ABC, abstractmethod

from datetime import datetime, timedelta
from config import setup_logging, BLOCKS_SQL_DATA, TRAINED_MODELS_DIR
from service_funcs import get_peaks_df, get_model_type

logger = setup_logging(__name__)
# BASE_DIR = Path(__file__).resolve().parent
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

class GeneralModel(ABC): 
    def __init__(self, model_info, init_dir_file=None):
        self.model_info = model_info
        self.model_type = model_info['model']['type']
        self.model_parameters = model_info['model']['model_param']
        self.time_parameters = model_info['model']['time_param']
        self.model = None  # Здесь будет храниться объект модели
        self.init_dir_file = init_dir_file  
        self.comment = model_info['model'].get('comment', None)
        self.model_dir = None

    @abstractmethod
    def train_model_specific(self, cor_data_in_iteration_to_teach):
        """
        Абстрактный метод для специфической тренировки модели.
        Должен быть реализован в подклассе.
        """
        pass
        

    def save(self, iteration):
        path = f'{self.model_dir}/model_{iteration}.pkl'
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)
        with open(path, 'wb') as f:
            pickle.dump(self.model, f)
        print(f"Модель {self.model_type} iter-{iteration} сохранена по пути: {path}")
        
    def get_start_teaching_tmsp(self):
        midnight_timestamp = get_yesterday_midnight()
        how_many_sec_in_month = 30*24*60*60
        tmsp = midnight_timestamp-(self.time_parameters['training_data_duration_months']+self.time_parameters['total_testing_period_months'])*how_many_sec_in_month
        return tmsp

    def train_with_iterations(self):
        # print(self.time_parameters)
        midnight_timestamp = get_yesterday_midnight()
        date_time = datetime.fromtimestamp(midnight_timestamp)
        short_date = date_time.strftime('%Y-%m-%d %H:%M')
        # print(midnight_timestamp, ' (', short_date, ')')
        self.model_dir = f"{TRAINED_MODELS_DIR}/{self.model_type}_alpha{self.model_parameters['alpha']:.5f}_{self.time_parameters['training_data_duration_months']}-{self.time_parameters['total_testing_period_months']}-{self.time_parameters['model_relevance_period_months']}-date_{short_date}"
        how_many_sec_in_month = 30*24*60*60

        how_many_iterations = int(self.time_parameters['total_testing_period_months']/self.time_parameters['model_relevance_period_months'])
        how_many_iterations = max(1, how_many_iterations) 

        start_teaching_tmsp = self.get_start_teaching_tmsp()
        new_iteration_tmsp = start_teaching_tmsp
        for iteration in range(how_many_iterations):
            cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test = self.get_corelation_df(new_iteration_tmsp, how_many_sec_in_month)
            if self.model_type == 'ElasticNet':
                self.train_model_specific(cor_data_in_iteration_to_teach)

            # prediction_df = get_model_prediction(cor_data_in_iteration_to_profit_test) #мб надо добавить как атрибут экземпляра класса 
            # profit_calcilation(prediction_df)

            new_iteration_tmsp = new_iteration_tmsp + self.time_parameters['model_relevance_period_months']*how_many_sec_in_month

            self.save(iteration)

            # print('Расчеты временых промежутков для обучения и теста')
            # print(f'{i}')
            # print(f'peaks_data_in_iteration_to_teach  {peaks_data_in_iteration_to_teach.head(1)}')
            # print(f'{peaks_data_in_iteration_to_teach.tail(1)}')
            # print(f'peaks_data_in_iteration_to_profit_test  {peaks_data_in_iteration_to_profit_test.head(1)}')
            # print(f'{peaks_data_in_iteration_to_profit_test.tail(1)}')

    def get_corelation_df(self, new_iteration_tmsp, how_many_sec_in_month)  : # -> peaks_data_in_iteration_to_teach, peaks_data_in_iteration_to_profit_test
        # сначала получаем кошельки по точкам пиков
        # собираем их транзакции
        # фильтруем
        # считаем кореляцию
        # рассчитываем дф для обучения 
        iterval_with_peaks_df, iterval_with_peaks_df_for_test = self.get_peaks_of_iteration(new_iteration_tmsp)

        wallets_of_peaks_list = self.get_wallets_of_peaks_list(iterval_with_peaks_df)

        cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test = 0, 0
        return cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test

    def get_peaks_of_iteration(self, new_iteration_tmsp):
        how_many_sec_in_month = 30*24*60*60
        peaks_data = get_peaks_df()
        peaks_data_in_iteration_to_teach = peaks_data.loc[
            (peaks_data['Timestamp']>new_iteration_tmsp) & 
            (peaks_data['Timestamp']<new_iteration_tmsp+self.time_parameters['training_data_duration_months']*how_many_sec_in_month)]
        peaks_data_in_iteration_to_profit_test = peaks_data.loc[
            (peaks_data['Timestamp']>new_iteration_tmsp+self.time_parameters['training_data_duration_months']*how_many_sec_in_month) & 
            (peaks_data['Timestamp']<(new_iteration_tmsp+(self.time_parameters['training_data_duration_months']+self.time_parameters['model_relevance_period_months'])*how_many_sec_in_month))]
        print('peaks_data_in_iteration_to_teach')
        print(peaks_data_in_iteration_to_teach.head)
        return peaks_data_in_iteration_to_teach, peaks_data_in_iteration_to_profit_test
    
    def get_wallets_of_peaks_list(self, iterval_with_peaks_df):
        
        pass

    def load(self, path):
    # def load_model(self, path):
    #     with open(path, 'rb') as f:
    #         self.model = pickle.load(f)
    #     print(f"Модель загружена из пути: {path}")        
        pass



class ElasticNetModel(GeneralModel):
    def train_model_specific(self, cor_data_in_iteration_to_teach, n_splits=5):
        from sklearn.linear_model import ElasticNet
        from sklearn.model_selection import StratifiedKFold
        print(self.model_parameters)

        model = ElasticNet()

        X = cor_data_in_iteration_to_teach.drop(columns=['Action', 'Sell', 'Buy', 'Human_time', 'Timestamp', 'Price'])
        y = cor_data_in_iteration_to_teach['Action']
        kf = StratifiedKFold(n_splits=5)

        for train_index, test_index in kf.split(X, y):
            X_train, X_test = X.iloc[train_index], X.iloc[test_index]
            y_train, y_test = y.iloc[train_index], y.iloc[test_index]
            model.set_params(**self.model_parameters)
            model.fit(X_train, y_train)
            threshold = self.model_parameters['threshold']
            y_pred_continuous = model.predict(X_test)
            y_pred = np.zeros_like(y_pred_continuous)  # Инициализируем массив предсказаний
            y_pred[y_pred_continuous > threshold] = 1  # возможно, можно сохранить не приведенный к 1 или -1 threshold?
            y_pred[y_pred_continuous < -threshold] = -1
            
            # f1_weighted_fold_scores.append(f1_score(y_test, y_pred, average='weighted'))
            # precision_fold_scores.append(precision_score(y_test, y_pred, average='weighted'))
            # recall_fold_scores.append(recall_score(y_test, y_pred, average='weighted'))
            self.model = model
            



def get_yesterday_midnight():
    # Определяем полночь сегодня 
    now = datetime.now()
    today_midnight = datetime(now.year, now.month, now.day)
    today_midnight = int(today_midnight.timestamp())
    return today_midnight

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