# model_classes.py

import pickle
import os
import re
import time
import sitecustomize  # noqa: F401
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
from sklearn.metrics import f1_score, precision_score, recall_score
import warnings

from settings.dask import configure_dask_dataframe_backend

configure_dask_dataframe_backend()

import dask.dataframe as dd
from dask.distributed import Client, LocalCluster, wait
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from dask.delayed import delayed
from datetime import datetime, timedelta
from dask.distributed import as_completed
from modules.dask_client_init.get_dask_client import get_dask_client
from settings.data_operations import MIN_TXS_PER_WALLET, TOTAL_AMOUNT_MORE_THAN_BTC
from settings.paths import BLOCK_HEIGHT_BLOCK_TIME_MAP_DIR_FILE, BLOCKS_SQL_DATA, TRAINED_MODELS_DIR

from . import service_funcs as sf
from . import data_operations as do
from .determinism import model_params_with_seed

import logging
logger = logging.getLogger("app")
script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

class GeneralModel(): 
    NON_FEATURE_COLUMNS = ('Action', 'Price', 'Predicted_Action', 'index')

    def __init__(self, model_info):
        self.model_info = model_info
        self.model_type = model_info['model']['type']
        self.model_parameters = self.normalize_model_parameters(model_info['model']['model_param'])
        self.time_params = model_info['model']['time_params']
        self.comment = model_info['model'].get('comment', None)
        self.filter_params = model_info['model'].get('filters', None)
        self.correlation_params = model_info['model'].get('correlation_params', None)
        self.model = None 
        self.init_dir_file = None  
        self.model_dir = None
        self.start_teaching_tmsp = None
        self.end_teaching_tmsp = None
        self.tmsps_data = None
        self.model_feature_columns = None

    @staticmethod
    def normalize_model_parameters(model_parameters):
        normalized_params = dict(model_parameters)
        legacy_threshold = normalized_params.pop('threshold', None)
        decision_threshold = normalized_params.get('decision_threshold')

        if legacy_threshold is not None:
            if decision_threshold is not None and decision_threshold != legacy_threshold:
                raise ValueError(
                    "Conflicting threshold and decision_threshold values in model parameters."
                )
            normalized_params['decision_threshold'] = legacy_threshold

        return normalized_params

    def train_model_specific(self, cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test, seed=None):
        """
        Абстрактный метод для специфической тренировки модели.
        Должен быть реализован в подклассе.
        """
        pass

    def prepare_feature_frame(self, data, feature_columns=None):
        feature_frame = data.drop(columns=list(self.NON_FEATURE_COLUMNS), errors='ignore')
        if feature_columns is None:
            return feature_frame

        missing_features = [column for column in feature_columns if column not in feature_frame.columns]
        if missing_features:
            raise ValueError(f"Missing features in prediction data: {missing_features}")

        return feature_frame.loc[:, list(feature_columns)]

    def log_model_contract(self, context, extra=None):
        model_object = self.model
        pipeline_steps = None
        if hasattr(model_object, "named_steps"):
            pipeline_steps = list(model_object.named_steps)

        details = {
            "context": context,
            "model_type": self.model_type,
            "decision_threshold": self.model_parameters.get("decision_threshold"),
            "feature_count": (
                len(self.model_feature_columns)
                if self.model_feature_columns is not None
                else None
            ),
            "feature_columns": self.model_feature_columns,
            "model_object_type": type(model_object).__name__ if model_object is not None else None,
            "pipeline_steps": pipeline_steps,
        }
        if extra:
            details.update(extra)

        logger.info("MODEL_CONTRACT %s", json.dumps(details, ensure_ascii=False, default=str))
        
    # def calculate_total_value(self, data):
    #     """
    #     Абстрактный метод для profit test.
    #     Сейчс реализован для еластикнет, проблема в threshold - нет уверенности, что этот показатель етсь в других моделях.
    #     Если есть или если получится тестировать без его определения - сделать метод универсальным.
    #     """
    #     pass
        
    def save_model(self, iteration):
        from joblib import dump
        model = self.model

        # Сформировать путь к директории модели
        if self.model_dir == None:
            self.model_dir = sf.get_group_of_model_save_dir(self)
        
        # Сначала создаём директорию, если она не существует
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Теперь можно безопасно сохранять DataFrame
        profit_dir = self.model_dir / 'profit_test_df'
        profit_dir.mkdir(parents=True, exist_ok=True)
        profit_path = profit_dir / f"profit_test_df_{iteration+1}.parquet"

        if not self.profit_test_df.empty:
            self.profit_test_df.to_parquet(profit_path)
            self.profit_test_df = None

        model_dir = self.model_dir / 'models'
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"model_{iteration+1}.joblib"
        dump(model, model_path)
        
        # model_X_dir = self.model_dir
        # переписать сохранение  - dir_of_group_of_model 
        # и далее все по итерациям.в итерациях сохранить tmsp ы обучения и профит теста 
        logger.info(f"Модель сохранена по пути: {model_path}")
        logger.info(f"Profit DataFrame сохранён по пути: {profit_path}")
    

    # начал писать пересохранение модели и ее файллв, дописать как структура будет перед глазами
    # def save_model(self, iteration):
    #     from joblib import dump

    #     if self.model_dir == None:
    #         self.model_dir = sf.get_group_of_model_save_dir(self)
    #     self.model_dir.mkdir(parents=True, exist_ok=True)
        
    #     # Теперь можно безопасно сохранять DataFrame
    #     profit_dir = self.model_dir / 'profit_test_df'
    #     name = f"profit_test_df_{iteration+1}.parquet"
    #     if not self.profit_test_df.empty:
    #         self.profit_test_df.to_parquet(profit_path)
    #         self.profit_test_df = None

    #     save_model_files(self, name, profit_dir, iteration)



    #     model_dir = self.model_dir / 'models'
    #     model_dir.mkdir(parents=True, exist_ok=True)
    #     model_path = model_dir / f"model_{iteration+1}.joblib"
    #     dump(self.model, model_path)
        
    #     # model_X_dir = self.model_dir
    #     # переписать сохранение  - dir_of_group_of_model 
    #     # и далее все по итерациям.в итерациях сохранить tmsp ы обучения и профит теста 
    #     print(f"Модель сохранена по пути: {model_path}")
    #     print(f"Profit DataFrame сохранён по пути: {profit_path}")

    # def save_model_files(self, name, dir, iteration = 0):
    #     dir.mkdir(parents=True, exist_ok=True)
    #     profit_path = profit_dir / f"profit_test_df_{iteration+1}.parquet"

    #     pass


    def calculate_total_value(self, data, dollar_qnt = 1000):
        if do.is_dask_dataframe_like(data):
            data = data.persist().compute()

        model = self.model
        threshold = self.model_parameters['decision_threshold']

        # Начальные значения
        btc_qnt = 0
        already_bought = 0
        data_copy = self.prepare_feature_frame(data, self.model_feature_columns)
        self.log_model_contract(
            "profit_predict",
            extra={
                "prediction_rows": int(len(data_copy)),
                "prediction_columns_count": int(len(data_copy.columns)),
            },
        )
        data_copy.to_parquet('data_copy_for_predictions.parquet')
        # print(data_copy.head())
        # Генерация предсказаний на основе модели
        predictions = model.predict(data_copy)  # Убедитесь, что здесь удалены все неиспользуемые колонки
        
        logger.warning('дописать проверку на соответствие фич, смотри под комментом')
        # Перед вызовом predict убедиться, что data_copy содержит те же самые фичи, что использовались при обучении.

        # Можно сохранить список фич модели 
        # при обучении и затем перед predict делать data_copy = data_copy[feature_names], где feature_names — список фич.
        # и проверка на упущенные фичи 
        # missing_features = set(self.model.feature_names_in_) - set(data_copy.columns)
        # if missing_features:
        #     raise ValueError(f"Missing features in prediction data: {missing_features}") 
        # Добавление предсказаний к данным
        data['Predicted_Action'] = np.zeros_like(predictions, dtype=predictions.dtype)
        data.loc[predictions > threshold, 'Predicted_Action'] = 1
        data.loc[predictions < -threshold, 'Predicted_Action'] = -1
        predicted_action_counts = data['Predicted_Action'].value_counts(dropna=False).to_dict()
        logger.info(
            "MODEL_PREDICTION_SUMMARY %s",
            json.dumps(
                {
                    "rows": int(len(data)),
                    "threshold": threshold,
                    "predicted_action_counts": {
                        str(key): int(value)
                        for key, value in predicted_action_counts.items()
                    },
                },
                ensure_ascii=False,
                default=str,
            ),
        )

        data.to_parquet('data_after_predictions.parquet')

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
        self.profit_of_model = total_final_value
        return total_final_value

class ElasticNetModel(GeneralModel):
    @staticmethod
    def _elasticnet_pipeline_params(model_parameters):
        return {
            f"regressor__{key}": value
            for key, value in model_parameters.items()
        }

    def train_model_specific(self, cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test, n_splits=5, return_ = False, seed=None):
        from sklearn.linear_model import ElasticNet
        from sklearn.model_selection import StratifiedKFold
        # logger.info("Start train_model_specific")
        # logger.info(f'Параметры модели {self.model_parameters}')
        model = Pipeline([
            ('scaler', StandardScaler()),
            ('regressor', ElasticNet(max_iter=10000)),
        ])
        # print('удалить после теста передачу cor_data_in_iteration_to_profit_test. или оставить для сравнения моделей')
        # X = cor_data_in_iteration_to_teach.drop(columns=['Action', 'Price'])
        train_features = self.prepare_feature_frame(cor_data_in_iteration_to_teach)
        self.model_feature_columns = list(train_features.columns)

        X = train_features
        logger.info("X for training")
        self.log_model_contract(
            "train_features_prepared",
            extra={
                "train_rows": int(len(X)),
                "train_columns_count": int(len(X.columns)),
            },
        )

        # logger.info(X.head())
        self.model_X = X

        y = cor_data_in_iteration_to_teach['Action']
        kf = StratifiedKFold(n_splits=n_splits)
        cor_data_in_iteration_to_profit_test['Predicted_Action'] = 0
        warning_messages = []
        f1_weighted_fold_scores = []
        precision_fold_scores = []
        recall_fold_scores = []
        profit_fold_values = []

        # переписать под USE_KF - в одну функцию  
        # for i, (train_index, test_index) in enumerate(kf.split(X, y), start=1):
        # без kf.split - в одну итерацию

        USE_KF = False 
        if USE_KF:
            for i, (train_index, test_index) in enumerate(kf.split(X, y), start=1):
                # logger.info(f"\033[34mStart {i} iteration in kf.split(X, y)\033[0m")
                X_train, X_test = X.iloc[train_index], X.iloc[test_index]
                y_train, y_test = y.iloc[train_index], y.iloc[test_index]
                filtered_params = {key: value for key, value in self.model_parameters.items() if key != 'decision_threshold'}
                filtered_params = model_params_with_seed(filtered_params, seed=seed)
                filtered_params = self._elasticnet_pipeline_params(filtered_params)
                
                model.set_params(**filtered_params)
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always")
                    model.fit(X_train, y_train)
                    if w:
                        for warning in w:
                            warning_messages.append(str(warning.message))
                            # logger.warning(f"Warning in fold {i}: {warning.message}")

                self.model = model
                decision_threshold = self.model_parameters['decision_threshold']

                y_pred_continuous = model.predict(X_test)
                y_pred = np.zeros_like(y_pred_continuous)
                y_pred[y_pred_continuous > decision_threshold] = 1
                y_pred[y_pred_continuous < -decision_threshold] = -1
                
                profit = self.calculate_total_value(cor_data_in_iteration_to_profit_test)
                profit_fold_values.append(profit)
                f1_weighted_fold_scores.append(f1_score(y_test, y_pred, average='weighted'))
                precision_fold_scores.append(precision_score(y_test, y_pred, average='weighted'))
                recall_fold_scores.append(recall_score(y_test, y_pred, average='weighted'))

        else:
            X_train, X_test = X, X
            y_train, y_test = y, y
            # Выполняем одну итерацию обучения
            filtered_params = {key: value for key, value in self.model_parameters.items() if key != 'decision_threshold'}
            filtered_params = model_params_with_seed(filtered_params, seed=seed)
            filtered_params = self._elasticnet_pipeline_params(filtered_params)
            model.set_params(**filtered_params)
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                model.fit(X_train, y_train)
                if w:
                    for warning in w:
                        warning_messages.append(str(warning.message))
            self.model = model
            decision_threshold = self.model_parameters['decision_threshold']
            y_pred_continuous = model.predict(X_test)
            y_pred = np.zeros_like(y_pred_continuous)
            y_pred[y_pred_continuous > decision_threshold] = 1
            y_pred[y_pred_continuous < -decision_threshold] = -1

            profit = self.calculate_total_value(cor_data_in_iteration_to_profit_test)
            profit_fold_values.append(profit)
            f1_weighted_fold_scores.append(f1_score(y_test, y_pred, average='weighted'))
            precision_fold_scores.append(precision_score(y_test, y_pred, average='weighted'))
            recall_fold_scores.append(recall_score(y_test, y_pred, average='weighted'))
        
        if return_:
            result = {
                "profits": profit_fold_values,
                "mean_profit": np.mean(profit_fold_values),
                "model_parameters": self.model_parameters,
                'decision_threshold': decision_threshold,
                'f1_weighted': np.mean(f1_weighted_fold_scores),
                'precision': np.mean(precision_fold_scores),
                'recall': np.mean(recall_fold_scores),
                'total_final_value': np.mean(profit_fold_values),
                "warnings": warning_messages
            }
            return result
        
# fast-api,пример:
# @app.post("/items/")
# async def create_item(item: Item) -> Item:
#     return item
# пример вызова функции из браузера (и не только) по запросу

# библиотека Jinja2 - рендеринг html шаблонов


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

