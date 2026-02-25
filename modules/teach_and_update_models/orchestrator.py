import os
import json
import pandas as pd
import gc
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import random

from config import setup_logging, NEW_PARAM_GRID_DIR, PARAM_GRID_DIR, PARAM_GRID_RESULTS
import main_functions as mf
from . import service_funcs as sf
from . import data_operations as do
from . import model_classes as mc
 
logger = setup_logging(__name__)
script_dir = os.path.dirname(os.path.abspath(__file__))
module_name_for_temp_dir = __name__.replace('.', '_')

os.chdir(script_dir)

def main_processing_model_orchestra(model, TEST):
    # mf.clear_temp_directory_of_module(module_name_for_temp_dir)

    # ДОБАВИТЬ В ПАРАМЕТРЫ МОДЕЛИ ПАРАМЕТРЫ ЗАТУХАНИЯ ДЛЯ ТЕСТА В ПАРАМ ГРИД. ПЕРЕДЕЛАТЬ ФУНКЦИЮ ТЕСТИРОВАНИЯ ПАРАМ ГРИДА ПОД РАЗНЫЕ
        # data_for_teach_df
        # посмтроить иерархию - сначала разные параметры 
        # data_for_teach_df -> model_param ->.........додумать

    print('изучить возможноть использовать во временном ряду не только куммулятывных сумм но и скользящего среднего')
    if TEST:
        logger.info("Тестовый режим")
        logger.info(f"Кол-во кошельков в тесте: {round((TEST*100), 2)} %")

    chunk_size = 180
    time_params = model.time_params
    model.tmsps_data = sf.get_tmsps_data_of_model(time_params)
    # print(model.tmsps_data)
    filter_params = model.filter_params
    correlation_type = model.correlation_params.get('correlation_type', None).lower()
    for iteration, tmps in model.tmsps_data.items():
        logger.info(f'\033[34mStart main teaching iteration {iteration} of {len(model.tmsps_data)}\033[0m')
        logger.info(f'Models Time data: {tmps}')

        cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test  = do.get_corelation_by_tmsp_df(TEST, filter_params, correlation_type, tmps, chunk_size)
        cor_data_in_iteration_to_teach = do.clean_data(cor_data_in_iteration_to_teach)
    
        if cor_data_in_iteration_to_profit_test.empty:
            logger.info("Empty profit test data. Stop teaching.")
            continue
        cor_data_in_iteration_to_profit_test = do.clean_data(cor_data_in_iteration_to_profit_test)

        # cor_data_in_iteration_to_teach.to_parquet('cor_data_in_iteration_to_teach.parquet')
        # cor_data_in_iteration_to_profit_test.to_parquet('cor_data_in_iteration_to_profit_test.parquet')

        model.train_model_specific(cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test)
        profit = model.calculate_total_value(cor_data_in_iteration_to_profit_test)
        logger.info(f'\033[34mResult of profit test of {iteration} iteration: {profit}\033[0m')
        model.save_model(iteration)

        # mf.clear_temp_directory()
        gc.collect()
    
    # sf.move_init_data(model)

def teaching_with_param_grid_orchestrator(TEACHING_TEST):
    time_grid_params, grid_params = sf.check_for_new_param_grid()
    models_statistic_result_df = pd.DataFrame()

    chunk_size = 200

    tmsps_data = sf.get_tmsps_data_of_model(time_grid_params)
    tmps = tmsps_data[1]
    print(tmps)

    logger.info(f'\033[34mStart get data for testing grid (only 1 iter)\033[0m')
    # я просто хочу протестировать параметры моделей, проверить их на сходимость
    # итерации не нужны - должна быть 1 в гриде
    # в get_corelation_by_tmsp_df испльузется model.filter_params и model.correlation_params.get('correlation_type'
    print(grid_params[0])
    filter_params = grid_params[0]['model']['filters']
    grid_with_opimized_corr = []
    grid_with_basic_corr = []
    for param in grid_params:
        if param['model']['correlation_params']['correlation_type'] == 'optimized':
            grid_with_opimized_corr.append(param)
        elif param['model']['correlation_params']['correlation_type'] == 'basic':
            grid_with_basic_corr.append(param)

    grids_grouped_by_corr_type = [grid_with_opimized_corr, grid_with_basic_corr]

    if TEACHING_TEST:
        for i, group in enumerate(grids_grouped_by_corr_type):
                grids_grouped_by_corr_type[i] = random.sample(group, int(len(group)*TEACHING_TEST))

    for group_of_grid in grids_grouped_by_corr_type:
        
        correlation_type = group_of_grid[0]['model']['correlation_params'].get('correlation_type', None).lower()
        
        existing_data = load_existing_correlation_data(tmps, PARAM_GRID_RESULTS)
        if existing_data is not None:
            cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test = existing_data
            logger.info("Используем сохранённые корреляционные данные.")
        else:
            cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test  = do.get_corelation_by_tmsp_df(TEACHING_TEST, filter_params, correlation_type, tmps, chunk_size)
            cor_data_in_iteration_to_teach = do.clean_data(cor_data_in_iteration_to_teach)
            cor_data_in_iteration_to_profit_test = do.clean_data(cor_data_in_iteration_to_profit_test)
            os.makedirs(PARAM_GRID_RESULTS, exist_ok=True)
            cor_data_in_iteration_to_teach.to_parquet(os.path.join(PARAM_GRID_RESULTS, f'cor_data_in_1_iteration_to_teach.parquet'))
            cor_data_in_iteration_to_profit_test.to_parquet(os.path.join(PARAM_GRID_RESULTS, f'cor_data_in_1_iteration_to_profit_test.parquet'))
        
        print('ПЕРЕПИСАТЬ ПОД ДАСК')
        with ProcessPoolExecutor(max_workers=8) as executor:
            futures = []
            for index, param in enumerate(group_of_grid):
                print(f'\nОбучение модели {index+1} из {len(group_of_grid)}', end='')
                futures.append(executor.submit(
                    train_model_for_param, 
                    param, 
                    cor_data_in_iteration_to_teach, 
                    cor_data_in_iteration_to_profit_test
                ))
            for future in as_completed(futures):
                result = future.result()
                row_df = pd.DataFrame([result])
                models_statistic_result_df = pd.concat([models_statistic_result_df, row_df], ignore_index=True)

    now = datetime.now()
    now = now.strftime("%d-%m-%Y_%H-%M-%S")
    os.makedirs(PARAM_GRID_RESULTS, exist_ok=True)
    models_statistic_result_df.to_parquet(os.path.join(PARAM_GRID_RESULTS, f'models_statistic_result_df_{now}.parquet'))

def load_existing_correlation_data(tmps, results_dir):
    """
    Проверяет наличие parquet-файлов с корреляционными данными и сравнивает временные метки.
    
    Аргументы:
      tmps (dict): словарь с временными метками (например, 'teaching_start_tmsp', 'teaching_end_tmsp' и т.д.).
      results_dir (str): путь к директории, где должны находиться файлы.
      
    Возвращает:
      Кортеж (df_teach, df_profit), если файлы существуют и метки времени совпадают, иначе None.
    """
    
    teach_path = os.path.join(results_dir, 'cor_data_in_1_iteration_to_teach.parquet')
    profit_path = os.path.join(results_dir, 'cor_data_in_1_iteration_to_profit_test.parquet')
    
    if os.path.exists(teach_path) and os.path.exists(profit_path):
        try:
            df_teach = pd.read_parquet(teach_path)
            df_profit = pd.read_parquet(profit_path)
        except Exception as e:
            logger.error(f"Ошибка загрузки файлов: {e}")
            return None
        return df_teach, df_profit

    #     # Проверим, что во всех необходимых столбцах присутствует единственное значение,
    #     # и оно совпадает с ожидаемыми временными метками из tmps.
    #     cmlt_start_tmsp = tmps['cmlt_start_tmsp']
    #     profit_test_end_tmsp = tmps['profit_test_end_tmsp']
    #     teaching_start_tmsp = tmps['teaching_start_tmsp']
    #     teaching_end_tmsp = tmps['teaching_end_tmsp']

    #     if cmlt_start_tmsp == df_teach['Timestamp'].min() and df_profit['Timestamp'].max() == profit_test_end_tmsp:
    #         logger.info("Найденные корреляционные данные корректны по временным меткам.")
    #         return df_teach, df_profit
    #     else:
    #         print('cmlt_start_tmsp, profit_test_end_tmsp')
    #         print(cmlt_start_tmsp, profit_test_end_tmsp)
    #         print('df_teach[Timestamp].min(), df_profit[Timestamp].max()')
    #         print(df_teach['Timestamp'].min(), df_profit['Timestamp'].max())
    # else:
    #     logger.info("Файлы с корреляционными данными не найдены, сбор данных заново.")
    #     return None




def train_model_for_param(param, cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test):
    model_type = param['model']['type']
    if model_type == 'ElasticNet':
        model = mc.ElasticNetModel(param)
    else:
        raise ValueError(f"Модель типа {model_type} не поддерживается.")
    return model.train_model_specific(cor_data_in_iteration_to_teach, cor_data_in_iteration_to_profit_test, return_=True)

def teach_model(model_type_data, model_type, model_info, model_dir_file, TEACHING_TEST):
    if 'json' in model_type_data:
        logger.info("Найден новый json модели")
        teach_model_from_json(model_type, model_info, model_dir_file, TEACHING_TEST)
    elif 'pkl' in model_type_data:
        logger.info("Найден новый pkl модели") 
        print('Код для использования модели PKL еще не написан. Надо сохранять параметры в папку teached models если буду использовать pkl')

def teach_model_from_json(model_type, model_info, init_dir_file, TEACHING_TEST):
    if model_type == 'ElasticNet':
        model = mc.ElasticNetModel(model_info)
    else:
        raise ValueError(f"Модель типа {model_type} не поддерживается.")
    model.init_dir_file = init_dir_file
    main_processing_model_orchestra(model, TEACHING_TEST)

