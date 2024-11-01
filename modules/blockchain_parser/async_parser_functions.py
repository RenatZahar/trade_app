# async_parser_functions.py
import statistics
import pandas as pd
import os
from collections import OrderedDict
from bitcoinrpc.authproxy import AuthServiceProxy
import cProfile
import pstats
import json
import time
import pickle
import gc
import asyncio
import aiohttp
import aiofiles
from aiohttp import ClientTimeout
import traceback
import sqlite3
import aiosqlite
from functools import wraps
import aiosqlite
import asyncio
import time
import traceback
import numpy as np

from config import setup_logging, CLEARED_PRICES_DIR # type: ignore #переменные подгружаются корректно, проблема в папках
from .config import (
    REQUESTS_QUANTITY,
    MIN_VALUE_THRESHOLD,
    MAX_LINES_IN_TX_CACHE,
    MAX_LINES_IN_HASH_CACHE,
    MAX_SAVE_TASKS
    )

sqlite3.register_adapter(np.int32, int)
sqlite3.register_adapter(np.int64, int)

rpc_user=os.getenv('RPC_USER')
rpc_password=os.getenv('RPC_PASSWORD')
rpc_host=os.getenv('RPC_HOST')
rpc_port=os.getenv('RPC_PORT')

last_request_time = None

global_count = 0
avg_cache_vin = []
avg_hash_for_vin = []
avg_times = [] 

tx_cache = OrderedDict()
blocks_hash_cache = OrderedDict()

cache_lock = asyncio.Lock()
avg_lock = asyncio.Lock()
rpc_lock = asyncio.Lock()
print_lock = asyncio.Lock()

save_semaphore = asyncio.Semaphore(MAX_SAVE_TASKS) #пока дожидаемся сохранения перед след циклом загрузки
logger = setup_logging(__name__)
    
def retry(max_attempts=3, delay=1, exceptions=(Exception,)):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    logger.warning(f"Попытка {attempt} для функции {func.__name__} не удалась: {e}")
                    if attempt < max_attempts:
                        await asyncio.sleep(delay)
            logger.error(f"Все {max_attempts} попыток для функции {func.__name__} не удались.")
            raise Exception(f"Функция {func.__name__} не смогла завершиться успешно после {max_attempts} попыток.")
        return wrapper
    return decorator
    
async def set_wal_mode(db_path):
    # Устанавливает режим журналирования базы данных на WAL.
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.commit()
            logger.info("Режим журналирования установлен на WAL.")
    except Exception as e:
        logger.error(f"Ошибка при установке режима WAL: {e}")

async def async_vacuum_analyze(db_path):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("VACUUM;")
            await db.execute("ANALYZE;")
            await db.commit()
            logger.info("VACUUM и ANALYZE успешно выполнены.")
    except Exception as e:
        logger.error(f"Ошибка при выполнении VACUUM/ANALYZE: {e}")

async def async_set_foreign_keys(db_path, enable=False):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(f"PRAGMA foreign_keys={'ON' if enable else 'OFF'};")
            await db.commit()
            logger.info(f"PRAGMA foreign_keys установлен на {'ON' if enable else 'OFF'}.")
    except Exception as e:
        logger.error(f"Ошибка при установке PRAGMA foreign_keys: {e}")

async def async_set_cache_size(db_path, cache_size=-2000000):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(f"PRAGMA cache_size={cache_size};")
            await db.commit()
            logger.info(f"PRAGMA cache_size установлен на {cache_size}.")
    except Exception as e:
        logger.error(f"Ошибка при установке PRAGMA cache_size: {e}")

async def async_set_synchronous_normal(db_path):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.commit()
            logger.info("PRAGMA synchronous установлен на NORMAL.")
    except Exception as e:
        logger.error(f"Ошибка при установке PRAGMA synchronous: {e}")

async def async_create_indexes(db_path, table_name='data_table'):
    start_time = time.perf_counter()
    try:
        async with aiosqlite.connect(db_path) as db:
            # Создание индекса на Wallet_id
            await db.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_wallet_id 
                ON {table_name} (Wallet_id);
            """)
            
            # Создание индекса на Block_height
            await db.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_block_height 
                ON {table_name} (Block_height);
            """)
            
            await db.commit()
            logger.info(f"Индексы на Wallet_id и Block_height успешно созданы или уже существуют.")
    except Exception as e:
        logger.error(f"Ошибка при создании индексов: {e}")
    finally:
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f"Время выполнения async_create_indexes: {elapsed_time:.6f} секунд")

async def async_create_table(db_path, table_name='data_table'):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    Transaction_id TEXT PRIMARY KEY,
                    Wallet_id TEXT,
                    Amount REAL,
                    Btc_block_time_price REAL,
                    Block_time INTEGER,
                    Block_height INTEGER,
                    Block_hash TEXT,
                    n INTEGER
                );
            """)
            await db.commit()
            logger.info(f"Таблица '{table_name}' успешно создана или уже существует.")
    except Exception as e:
        logger.error(f"Ошибка при создании таблицы: {e}")

async def init_db_mod(db_path, table_name='data_table'):
    await async_set_foreign_keys(db_path, enable=True)
    await set_wal_mode(db_path)
    await async_set_synchronous_normal(db_path)
    await async_set_cache_size(db_path, cache_size=-2000000)  # Настройте значение по необходимости
    await async_create_table(db_path, table_name)
    await async_vacuum_analyze(db_path)
    await async_create_indexes(db_path, table_name)

async def async_print_db_schema(db_path, table_name='data_table'):
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(f"PRAGMA table_info('{table_name}');")
            columns_info = await cursor.fetchall()
            await cursor.close()
            if columns_info:
                print(f"Схема таблицы '{table_name}':")
                for column in columns_info:
                    cid, name, type_, notnull, dflt_value, pk = column
                    print(f" - Столбец: {name}, Тип данных: {type_}, NOT NULL: {notnull}, Значение по умолчанию: {dflt_value}, Первичный ключ: {pk}")
            else:
                print(f"Таблица '{table_name}' не найдена.")
    except Exception as e:
        print(f"Ошибка при получении схемы базы данных: {e}")

def init_cache():
    global tx_cache, blocks_hash_cache
    tx_cache_filename = 'tx_cache.pkl'
    blocks_hash_cache_filename = 'blocks_hash_cache.pkl'
    if not tx_cache:
        tx_cache = open_tx_cache(tx_cache_filename)
    if not blocks_hash_cache:
        blocks_hash_cache = open_blocks_hash_cache(blocks_hash_cache_filename)

def open_tx_cache(filename):
    global tx_cache
    current_dir = os.path.dirname(os.path.realpath(__file__))
    cache_file_path = os.path.join(current_dir, filename)
    
    if not os.path.exists(cache_file_path):
        cache = OrderedDict()
        print(f"Кэш {filename} не найден, создан новый словарь")
        return cache
    
    else:
        with open(cache_file_path, 'rb') as file:
            cache = pickle.load(file)
            print(f'Читаем {filename} из файла')
            return cache

def open_blocks_hash_cache(filename):
    global blocks_hash_cache
    current_dir = os.path.dirname(os.path.realpath(__file__))
    cache_file_path = os.path.join(current_dir, filename)
    
    if not os.path.exists(cache_file_path):
        cache = OrderedDict()
        print(f"Кэш {filename} не найден, создан новый словарь")
        return cache
    
    else:
        with open(cache_file_path, 'rb') as file:
            cache = pickle.load(file)
            print(f'Читаем {filename} из файла')
            return cache

async def async_save_cache_to_file(cache, filename):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, lambda: save_cache_to_file(cache, filename))

async def save_caches():
    await async_save_cache_to_file(blocks_hash_cache, 'blocks_hash_cache.pkl')
    await async_save_cache_to_file(tx_cache, 'tx_cache.pkl')

async def save_cache_to_file(cache, filename):
    print(f'Старт сохранения: {filename}')
    current_dir = os.path.dirname(os.path.realpath(__file__))
    cache_file_path = os.path.join(current_dir, filename)
    async with aiofiles.open(cache_file_path, 'wb') as file:
        await file.write(pickle.dumps(cache))
    print(f'Сохранение завершено: {filename}')

def general_cleaning_of_caches():
    global tx_cache, blocks_hash_cache
    if len(tx_cache) > MAX_LINES_IN_TX_CACHE:
                num_to_remove = int(len(tx_cache) - MAX_LINES_IN_TX_CACHE)
                for _ in range(num_to_remove):
                    tx_cache.popitem(last=False)
    
    if len(blocks_hash_cache) > MAX_LINES_IN_HASH_CACHE:
        num_to_remove = int(len(blocks_hash_cache) - MAX_LINES_IN_HASH_CACHE)
        for _ in range(num_to_remove):
            blocks_hash_cache.popitem(last=False)
    print(f'\nСтрок в tx_cache: {len(tx_cache)}')
    print(f'Строк в blocks_hash_cache: {len(blocks_hash_cache)}')

async def save_to_cache(tx_details_list, cache_type, old_txs = False):
    global tx_cache, blocks_hash_cache
    # добавление в кэш
    general_cleaning_of_caches()
    async with cache_lock:
        for i in tx_cache:
            if i in blocks_hash_cache:
                del blocks_hash_cache[i]
            
    tx_details_list = [
        tx_details for tx_details in tx_details_list 
        if tx_details is not None and 
        tx_details and  # Проверка на непустоту tx_details
        not any('coinbase' in vin_entry for vin_entry in tx_details.get('vin', []))
                            ]
    
    excluded_keys = ['in_active_chain', 'version', 'size', 'vsize', 'hex', 'confirmations', 'scriptSig', 'txinwitness', 'sequence', 'weight', 'locktime', 'vin']
    additional_excluded_keys = ['asm','desc', 'addr', 'hex', 'type', 'time', 'blocktime']

    for tx_detail in tx_details_list:
        txid = tx_detail['txid']
        # Фильтрация ключей транзакции
        filtered_tx_detail = {key: value for key, value in tx_detail.items() if key not in excluded_keys}

        if 'vout' in filtered_tx_detail:
            for vout_entry in filtered_tx_detail['vout']:
                if 'scriptPubKey' in vout_entry:
                    vout_entry['scriptPubKey'] = {key: value for key, value in vout_entry['scriptPubKey'].items() if key not in additional_excluded_keys}

        filtered_tx_detail = {key: value for key, value in filtered_tx_detail.items() if key not in ['time', 'blocktime']}
        async with cache_lock:
            if cache_type == 'tx_cache':
                if txid not in tx_cache:
                    tx_cache[txid] = filtered_tx_detail
            if cache_type == 'hash_cache':
                if txid not in blocks_hash_cache and txid not in tx_cache:
                    vout = tx_detail['vout']
                    if len(vout) > 5:
                        blocks_hash_cache[txid] = tx_detail.get('blockhash', None)

async def async_get_existing_last_block(db_path, start_block):
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT MAX(Block_height) FROM data_table;")
            result = await cursor.fetchone()
            await cursor.close()
            
            if result and result[0] is not None:
                last_block = result[0]
                logger.info(f"Последний загруженный блок: {last_block}")
            else:
                last_block = start_block
                logger.info(f"База данных пуста. Начинаем с блока: {start_block}")
            
            return last_block
    except Exception as e:
        logger.error(f"Ошибка при доступе к базе данных: {e}")
        return start_block
    # logger.info(f"Время выполнения async_get_existing_last_block: {elapsed_time:.6f} секунд")

def get_bicoin_prices(filepath):
    df = pd.read_parquet(CLEARED_PRICES_DIR)
    logger.info('CLEARED_PRICES_DIR')
    logger.info(f'\n{df.tail()}')
    return df
    
async def get_btc_price_of_timestamp(timestamp, btc_price):
    timestamp = int(timestamp)
    target_time = pd.to_datetime(timestamp, unit='s')
    index = btc_price['Human_time'].searchsorted(target_time)
    closest_index = max(min(index, len(btc_price) - 1), 0)
    closest_price = round((float(btc_price.iloc[closest_index]['Price'])), 2)
    return closest_price

def get_list_of_blocks_to_download(biggest_downloaded_block, rpc_connection):
    current_block = rpc_connection.getblockcount()
    if current_block > biggest_downloaded_block:
        list_of_blocks_to_download = list(range(biggest_downloaded_block+1,current_block))
        return(list_of_blocks_to_download)

def split_list_into_chunks(lst, QUANTITY_OF_BLOCKS_IN_ITERATION, MAX_ITERATIONS, blocks_to_remove):
    logger.info(f'Первый блок для загрузки: {lst[0]}')
    logger.info(f'Осталось загрузить блоков: {lst[-1]-lst[0]}')
    current_iteration = 0
    while MAX_ITERATIONS != current_iteration:
        current_iteration += 1
        current_blocks = lst[:QUANTITY_OF_BLOCKS_IN_ITERATION]
        if len(current_blocks) == 1:
            logger.info(f"\nИтерация - {current_iteration} из {MAX_ITERATIONS}, блок: {current_blocks[0]}.")
        else:
            logger.info(f"\nИтерация - {current_iteration} из {MAX_ITERATIONS}, блоков: {len(current_blocks)}.")

        if blocks_to_remove:
            logger.info(f'проверка на блоки {blocks_to_remove} в чанке')
            for i in blocks_to_remove:
                if i in current_blocks:
                    logger.info('Есть, удаляем')
                    current_blocks.remove(i) # type: ignore

        del lst[:QUANTITY_OF_BLOCKS_IN_ITERATION]
        yield current_blocks

async def amount_and_counbase_filter(tx_list):
    count = 0

    tx_list = [
        tx_details for tx_details in tx_list 
        if tx_details is not None and 
        tx_details and  # Проверка на непустоту tx_details
        not any('coinbase' in vin_entry for vin_entry in tx_details.get('vin', []))
                            ]
    
    filtered_tx_details_list = []
    for tx_details in tx_list:
        if tx_details is not None:
            if any(vout['value'] >= MIN_VALUE_THRESHOLD for vout in tx_details['vout']):
                filtered_tx_details_list.append(tx_details)
            else:
                count += 1  
    tx_list = []
    return filtered_tx_details_list

def check_time(stats):
    sync_rpc_stats = stats.stats[('парсинг транзакций\\parsing\\однопоточный скрипт с batch\\sync_fun.py', '148', 'sync_rpc_connection')]
    sync_rpc_time = sync_rpc_stats[3] 
    total_time = sum([info[3] for info in stats.stats.values()])
    percentage = (sync_rpc_time / total_time) * 100
    print(f"Функция sync_rpc_connection занимает {percentage:.2f}% общего времени выполнения.")

def get_rpc_connection():
    global rpc_user, rpc_password, rpc_host, rpc_port
    rpc_url = f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}"
    # print(rpc_url)
    rpc_connection = AuthServiceProxy(rpc_url, timeout=1200)
    return rpc_connection

def sync_rpc_connection(rpc_connection, rpc_method, *args):
    responses = []
    try:
        if rpc_method is None:
            if len(args) == 1 and isinstance(args[0], list):
                batch_list = args[0].copy()
                for i in range(0, len(batch_list), REQUESTS_QUANTITY):
                    time.sleep(0.2)  
                    attempt = 0
                    while attempt < 30:  
                        try:
                            batch = batch_list[i:i + REQUESTS_QUANTITY]
                            batch_responses = rpc_connection.batch_(batch)
                            responses.extend(batch_responses)
                            break  
                            
                        except Exception as e:
                            attempt += 1
                            time.sleep(5)
                            logger.error('sync_rpc_connection, запрос:')
                            logger.error(batch)
                            logger.error('sync_rpc_connection, ответ:')
                            logger.error(responses)
                            logger.error(f'Пакетная ошибка: {e}, попытка {attempt} для пакета')
                return responses
            else:
                raise ValueError("Некорректный формат аргументов для batch-запроса")
        else:
            method = getattr(rpc_connection, rpc_method)
            response = method(*args)
            return response
    except Exception as e:
        print(f'Размер запроса: {len(batch)}')
        print(f"Ошибка: {e}, ожидаем, попытка {attempt}")
        print(f'rpc_method: {rpc_method}, *args: {args}')
    print("Не удалось установить соединение после 150 попыток.")
    return None

async def async_rpc_connection(rpc_method, height, *args):
    global last_request_time, rpc_user, rpc_password, rpc_host, rpc_port
    url = f"http://{rpc_user}:{rpc_password}@{rpc_host}:{rpc_port}"
    headers = {'content-type': 'application/json', 'Connection': 'close'}
    timeout = ClientTimeout(total=360)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for i in range(150):  
            if last_request_time is not None:
                elapsed_time = time.time() - last_request_time
                if elapsed_time < 1:
                    await asyncio.sleep(1 - elapsed_time)
            if rpc_method is None:
                requests = [{"method": method, "params": params, "jsonrpc": "2.0", "id": i} for method, params in args[0]]
            else:
                requests = [{"method": rpc_method, "params": args, "jsonrpc": "2.0", "id": 0}]

            try:
                attempt = 0
                async with session.post(url, data=json.dumps(requests), headers=headers) as response:
                    if response.status == 200:
                        json_response = await response.json()
                        results = [item['result'] for item in json_response if 'result' in item]
                        return results

                    else:
                        attempt += 1
                        error_text = await response.text()
                        if 'Work queue depth exceeded' in error_text:
                            await asyncio.sleep(2)
                            continue
                        logger.error(f'Ошибка запроса: {response.status}, {error_text}')
                        await asi_sleep(attempt)

            except Exception as e:
                logger.error(f'Ошибка запроса: {e}, блок {height}')
                logger.error(f'Попытка {i+1}')
                logger.error(traceback.format_exc())
                await asyncio.sleep(10)  # Задержка перед повторной попыткой

        logger.error("Не удалось установить соединение после 150 попыток.")
        exit()

async def asi_sleep(attempt):
    if attempt > 50 and attempt < 100:
        await asyncio.sleep(10)
    elif attempt >= 100:
        logger.error('Большая задержка ответа')
        await asyncio.sleep(30)
    elif attempt == 150:
        logger.error('Exit из async def asi_sleep(attempt)')
        exit()
    else:
        logger.error('Ожидание ответа, asi_sleep(attempt), attempt<50')
        await asyncio.sleep(1)

async def parsing_data(block_list):
    init_cache()
    btc_price = get_bicoin_prices(CLEARED_PRICES_DIR)
    rpc_connection = get_rpc_connection()   
    height, blocks_hashes, block_times, transactions_of_group_of_block = get_transactions_of_blocks(block_list, rpc_connection) 
    all_records = await process_all_blocks(height, blocks_hashes, block_times, transactions_of_group_of_block, btc_price, rpc_connection)
    pd_data = records_to_df(all_records)
    gc.collect()
    return pd_data  

def get_transactions_of_blocks(block_list, rpc_connection):
    global tx_cache, blocks_hash_cache
    commands = [["getblockhash", block_number] for block_number in block_list]
    block_hashes = sync_rpc_connection(rpc_connection, None, commands)
    commands = [["getblock", block_hash] for block_hash in block_hashes] # type: ignore
    blocks = sync_rpc_connection(rpc_connection, None, commands)
    block_times, blocks_hashes, height, transactions_of_groups_of_block = [], [], [], []
    for block in blocks: # type: ignore
        if len(block['tx']) < 5:
            continue
        block_times.append(block['time'])
        blocks_hashes.append(block['hash'])
        height.append(block['height'])
        transactions_of_groups_of_block.append(block['tx'])

    return height, blocks_hashes, block_times, transactions_of_groups_of_block

async def process_all_blocks(heights, blocks_hashes, block_times, transactions_of_groups_of_block, btc_price, rpc_connection):
    tasks = []
    number = len(heights)
    # Перебираем все блоки и создаём задачу для каждого
    for index in range(len(heights)):
        task = asyncio.create_task(process_block(index, number, heights[index], blocks_hashes[index], block_times[index], transactions_of_groups_of_block[index], btc_price, rpc_connection))
        tasks.append(task)
    # Одновременное выполнение всех задач
    results = await asyncio.gather(*tasks)
    return [record for result in results if result is not None for record in result]

async def process_block(index, number, height, block_hash, block_time, transactions_of_block, btc_price, rpc_connection):
    global tx_cache, blocks_hash_cache
    records_of_block = []
    logger.info(f'Обработка блока {height}, {index+1}/{number}, транзакций: {len(transactions_of_block)}')

    btc_time_price = await get_btc_price_of_timestamp(block_time, btc_price)
    commands = [["getrawtransaction", [tx, 1, block_hash]] for tx in transactions_of_block]
    # logger.info(f'Отправка запроса для {height}')
    start_time = time.time()
    tx_details_list = await async_rpc_connection(None, height, commands)
    end_time = time.time()
    logger.info(f'Блок {height}, {index+1}/{number}, получение данных по \033[93mvout, сек: {round(end_time-start_time, 4)}\033[0m, транзакций: {len(tx_details_list)}')
    tx_details_list = await amount_and_counbase_filter(tx_details_list)
    await save_to_cache(tx_details_list, 'tx_cache')  
            
    prev_tx_vout_to_current_tx_map = {}
    for tx_details in tx_details_list:
        current_tx_id = tx_details['txid']
        for vin in tx_details['vin']:
            if 'txid' in vin and 'vout' in vin:
                prev_tx_id = vin['txid']
                vout = vin['vout']
                if prev_tx_id not in prev_tx_vout_to_current_tx_map:
                    prev_tx_vout_to_current_tx_map[prev_tx_id] = {}
                if vout not in prev_tx_vout_to_current_tx_map[prev_tx_id]:
                    prev_tx_vout_to_current_tx_map[prev_tx_id][vout] = {}
                prev_tx_vout_to_current_tx_map[prev_tx_id][vout] = (current_tx_id)
        tx_id = tx_details['txid']
        
        records = await cleaning_tx_vout_data(tx_id, tx_details, height, block_hash, block_time, btc_time_price)
        if records:
            # print(records)
            records_of_block.extend(records)
    records = await cleaning_tx_vin_data(index, number, prev_tx_vout_to_current_tx_map, height, block_hash, block_time, btc_time_price)
    if records:
        records_of_block.extend(records)
    return records_of_block
    


async def cleaning_tx_vout_data(tx_id, tx_details, height, block_hash, block_time, btc_time_price):
    records = []
    for vout in tx_details['vout']:
        wallet_id = vout['scriptPubKey'].get('address', None)
        n = vout['n']
        if wallet_id is None:
            continue
        amount = vout['value']
        if amount > 1000000 or amount < -1000000:
            print('satoshi')
            amount = amount/100000000
            print(tx_details)
        records.append([tx_id, wallet_id, amount, btc_time_price, block_time, height, block_hash, n]) 
    return records

async def cleaning_tx_vin_data(index, number, prev_tx_vout_to_current_tx_map, height, current_block_hash, block_time, btc_time_price):
    global tx_cache, blocks_hash_cache, avg_cache_vin, avg_hash_for_vin
    # счетчик tx к скачке и сколько записей надо
    prev_tx_id_count = 0
    vout_to_tx_map_count = 0
    for prev_tx_id, vout_to_tx_map in prev_tx_vout_to_current_tx_map.items():
        prev_tx_id_count += 1
        for i in vout_to_tx_map:
            vout_to_tx_map_count += 1

    async with print_lock:        
        print(f'Блок {height}, {index+1}/{number}. Всего tx для входов: {prev_tx_id_count}, выходов: {vout_to_tx_map_count}')
    
    commands = []
    prev_tx_details_list_cache= []
    commands_with_hash = 0
    commands_without_hash = 0 
    prev_tx_details_list_cache_count = 0
    for prev_tx_id, vout_to_tx_map in prev_tx_vout_to_current_tx_map.items():
        if prev_tx_id in tx_cache:
            prev_tx_details_list_cache_count += 1
            prev_tx_details_list_cache.append(tx_cache[prev_tx_id])
            continue
        block_hash = blocks_hash_cache.get(prev_tx_id)
        if block_hash:
            commands_with_hash += 1
            commands.append(["getrawtransaction", [prev_tx_id, 1, block_hash]]) 
        else:
            commands_without_hash += 1
            commands.append(["getrawtransaction", [prev_tx_id, 1]])
    try:
        cache_vin_percnt =  round((prev_tx_details_list_cache_count/(len(commands)+prev_tx_details_list_cache_count)*100), 2)
    except ZeroDivisionError:
        return 0
    try:
        hash_for_vin_percnt = round((commands_with_hash/(len(prev_tx_vout_to_current_tx_map)-prev_tx_details_list_cache_count+1)*100), 2)
    except ZeroDivisionError:
        return 0
    async with avg_lock:
        avg_cache_vin.append(cache_vin_percnt)
        avg_hash_for_vin.append(hash_for_vin_percnt)
    async with print_lock:
        print(f'Загружено tx \033[93mиз кэша\033[0m для \033[93mvin: {cache_vin_percnt}%\033[0m от всех vin, кол-во: {prev_tx_details_list_cache_count}')
        print(f'Команд \033[93mс хэшем\033[0m: {commands_with_hash}, \033[93m{hash_for_vin_percnt}%\033[0m, осталось команд без хэша: {commands_without_hash}')

    start_time = time.time()
    prev_tx_details_list = await async_rpc_connection(None, height, commands)
    end_time = time.time()
    
    await save_to_cache(prev_tx_details_list, 'tx_cache', old_txs = True )

    async with print_lock:
        print(f'Блок {height}, {index+1}/{number}. Получение данных по \033[93m vin, сек: {round(end_time-start_time, 4)}\033[0m, транзакций: {len(prev_tx_details_list)}')

    prev_tx_details_list = [
        tx_details for tx_details in prev_tx_details_list 
        if tx_details is not None and 
        tx_details and  # Проверка на непустоту tx_details
        not any('coinbase' in vin_entry for vin_entry in tx_details.get('vin', []))
                            ]
    
    prev_tx_details_list.extend(prev_tx_details_list_cache)
    prev_tx_details_list_cache = []

    start_time = time.time()
    records = []
    dwn_prev_tx_details_dict = {}
    for tx in prev_tx_details_list:
        dwn_prev_tx_details_dict[tx['txid']] = tx
        
    for prev_tx_id, links in prev_tx_vout_to_current_tx_map.items():
        if prev_tx_id in dwn_prev_tx_details_dict:
            tx_details = dwn_prev_tx_details_dict[prev_tx_id]
            for vout_detail in tx_details['vout']:
                for link in links:
                    if link == vout_detail['n']:
                        current_tx_id = prev_tx_vout_to_current_tx_map[prev_tx_id][link]
                        amount = -vout_detail['value']
                        wallet_id = vout_detail['scriptPubKey'].get('address', None)
                        current_record = [current_tx_id, wallet_id, amount, btc_time_price, block_time, height, current_block_hash, link]
                        records.append(current_record)

                        if prev_tx_id in tx_cache:  
                            tx_cache_details = tx_cache[prev_tx_id]
                            vout_list = tx_cache_details.get('vout', [])
                            vout_list = [vout for vout in vout_list if vout.get('n') != vout_detail['n']]
                            async with cache_lock:
                                tx_cache[prev_tx_id]['vout'] = vout_list
                                if not vout_list:
                                    del tx_cache[prev_tx_id]
                                    
    prev_tx_vout_to_current_tx_map = {}
    dwn_prev_tx_details_dict = {}    
    end_time = time.time()
    print(f'Блок {height}, {index+1}/{number}. Команд {len(commands)}, из кэша {prev_tx_details_list_cache_count}, сумма {len(commands)+prev_tx_details_list_cache_count}, сколько скачать надо {prev_tx_id_count}')
    print(f'Блок {height}, {index+1}/{number}. Всего скачанных записей с продажей {len(records)}, должно равняться {vout_to_tx_map_count}')
    if len(records) != vout_to_tx_map_count:
        print(f'Блок {height}, {index+1}/{number}. Разница между нужно было скачать и было скачано: {(vout_to_tx_map_count - len(records))}, {round(((vout_to_tx_map_count - len(records))/vout_to_tx_map_count*100), 4)} %')
        
    # допускаем 3 процентов расхождения
    upper_limit = vout_to_tx_map_count + (vout_to_tx_map_count * 0.03)
    lower_limit = vout_to_tx_map_count - (vout_to_tx_map_count * 0.03)
    if len(records) > upper_limit or len(records) < lower_limit:
        print(f"\033[31mБлок {height}, {index+1}/{number}\033[0m")
        print("\033[31mБОЛЬШАЯ РАЗНИЦА!\033[0m")
    if (vout_to_tx_map_count - len(records))/vout_to_tx_map_count*100 > 20:
        print('\033[31mРазница больше 20 процентов\033[0m')
    return records

def get_statistik_data(data):
    min_block_height = data['Block_height'].min()
    max_block_height = data['Block_height'].max()
    return min_block_height, max_block_height

async def async_check_block_height_data(db_path, table_name='data_table'):
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(f"SELECT Block_height FROM {table_name};")
            rows = await cursor.fetchall()
            await cursor.close()
            non_int_values = []
            for row in rows:
                value = row[0]
                if not isinstance(value, int):
                    non_int_values.append((value, type(value)))
            print(f"Количество строк: {len(rows)}")
            print(f"Количество значений Block_height, которые не являются int: {len(non_int_values)}")
            if non_int_values:
                print("Значения Block_height, не являющиеся int:")
                for value, value_type in non_int_values[:10]:  # Выводим первые 10
                    print(f" - Значение: {value}, Тип данных: {value_type}")
    except Exception as e:
        print(f"Ошибка при проверке данных столбца 'Block_height': {e}")

def records_to_df(all_records):
    # Подготовка данных к сохранению
    df = pd.DataFrame(all_records, columns=['Transaction_id', 'Wallet_id', 'Amount', 'Btc_block_time_price', 'Block_time', 'Block_height', 'Block_hash', 'n'])
    df['Amount'] = df['Amount'].astype('float64')
    df = df.groupby(['Transaction_id', 'Wallet_id', 'Btc_block_time_price', 'Block_time', 'Block_height', 'Block_hash', 'n']).agg(
        Amount=('Amount', 'sum'),
        Transactions_Count=('n', 'count')
                    ).reset_index()
    
    df = df.sort_values(by='Block_height')
    df = df.reset_index(drop=True)
    df['Transaction_id'] = df['Transaction_id'].astype(str)
    df['Wallet_id'] = df['Wallet_id'].astype(str)
    df['Amount'] = df['Amount'].astype(float)
    df['Btc_block_time_price'] = df['Btc_block_time_price'].astype(float)
    df['Block_hash'] = df['Block_hash'].astype(str)
    df['Block_time'] = df['Block_time'].astype(int)
    df['Block_height'] = df['Block_height'].astype(int)
    df['n'] = df['n'].astype(int)
    df['Transactions_Count'] = df['Transactions_Count'].astype(int)

    return df


async def save_data_to_db_with_semaphore(data, db_path):
    async with save_semaphore:
        await async_save_data_to_db(data, db_path)

async def async_save_data_to_db(data, db_path, table_name='data_table'):
    logger.info('Старт сохранения в бд')
    """
    Удаляет все строки, где Block_height хранится в байтовом виде, и сохраняет новые данные,
    гарантируя, что все значения Block_height сохраняются как целые числа.

    :param data: DataFrame с данными для сохранения.
    :param db_path: Путь к файлу базы данных SQLite.
    :param table_name: Название таблицы в базе данных.
    """
    start_time = time.perf_counter()
    try:
        logger.info(f"Подключение к базе данных по пути: {db_path}")
        # Установка асинхронного соединения с базой данных
        async with aiosqlite.connect(db_path) as db:
            await db.execute("BEGIN")  # Начало транзакции
            # logger.info("Начата транзакция для сохранения данных.")

            # Создание таблицы, если она не существует
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    Transaction_id TEXT PRIMARY KEY,
                    Wallet_id TEXT,
                    Amount REAL,
                    Btc_block_time_price REAL,
                    Block_time INTEGER,
                    Block_height INTEGER,
                    Block_hash TEXT,
                    n INTEGER
                );
            """)
            # logger.info(f"Таблица '{table_name}' проверена/создана.")
            # Преобразование DataFrame в список кортежей для вставки
            records = data.to_records(index=False)
            records = list(records)
            # for record in records[:10]:  # Просмотреть первые 10 записей
            #     logger.info(f"Типы данных записи: {[type(value) for value in record]}")
            # Формирование списка столбцов и плейсхолдеров
            columns = ', '.join(data.columns)
            placeholders = ', '.join(['?'] * len(data.columns))
            # Вставка данных
            insert_query = f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders});"
            await db.executemany(insert_query, records)
            # logger.info(f"Вставлено {len(records)} записей в таблицу '{table_name}'.")
            await db.commit()  # Фиксация транзакции
            # logger.info("Транзакция успешно зафиксирована.")
            # logger.info(f"Сохранено {len(records)} записей в таблицу '{table_name}'.")
            logger.info("\033[92mОбработка завершена, данные сохранены.\033[0m")

    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в базу данных: {e}")
        traceback.print_exc()
        # В случае ошибки транзакция будет автоматически откатана при выходе из блока `async with`
    finally:
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        logger.info(f"Время выполнения async_save_data_to_db: {elapsed_time:.6f} секунд")

def print_cicle_info(start_time, min_block_height, max_block_height, len_blocks_group, df, quantity_of_blocks_to_download):
    global avg_cache_vin, avg_hash_for_vin
    end_time = time.time()
    cicle_time =  end_time - start_time
    # print(f"\nРазмер tx_cache в памяти: {int((asizeof.asizeof(tx_cache))/1000000)} мегабайт")
    print(f"Строк в tx_cache: {len(tx_cache)}")
    # print(f"Размер blocks_hash_cache в памяти: {int((asizeof.asizeof(blocks_hash_cache))/1000000)} мегабайт")
    print(f"Строк в blocks_hash_cache : {len(blocks_hash_cache)}")
    print(f'Больше нуля в df: {len(df.loc[df.Amount > 0])}, меньше нуля в df: {len(df.loc[df.Amount < 0])}')
    print(f'Больше нуля минус меньше нуля в дф: {len(df.loc[df.Amount > 0])-len(df.loc[df.Amount < 0])}, всего срок: {len(df)}')
    print(f'\nСохранено {min_block_height} - {max_block_height}') 
    print(f"Обработка завершена, данные сохранены. Время выполнения: {cicle_time:.2f} секунд")
    print(f'Блоков в минуту в цикле: {len_blocks_group/(int(cicle_time)/60):.2f}')
    print(f'Средний процент загрузок tx из кэша: {statistics.mean(avg_cache_vin)}')
    print(f'Средний процент команд tx с хэшем: {statistics.mean(avg_hash_for_vin)}')
    print(f"Количество блоков для скачивания: {quantity_of_blocks_to_download}")
    time_of_circle = len_blocks_group/(int(cicle_time)/60)
    return time_of_circle

def get_avg_blocks_in_minut(time_of_circle):
    global avg_times
    avg_times.append(time_of_circle)
    if len(avg_times) > 50:
        avg_times = avg_times[-50:]
    times = 0
    for i in avg_times:
        times += i
    total_avg_time = times / len(avg_times)
    five_times = 0
    for i in avg_times[-5:]:
        five_times += i
    if len(avg_times) > 5:
        logger.info(f'За последние пять блоков: {round((five_times/5), 2)} блоков/мин')
    logger.info(f'\n\033[93mСредняя скорость за {len(avg_times)} итераций: {round(total_avg_time, 2)} блоков/мин\033[0m')
    
def start_anliz_processes():
    profiler = cProfile.Profile()
    profiler.enable()
    return profiler
        
def end_of_anliz_processes(profiler):
    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumtime').print_stats(30)