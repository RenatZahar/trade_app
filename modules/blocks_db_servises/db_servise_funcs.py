# db_servise_funcs.py
import pandas as pd
from datetime import datetime
from collections import OrderedDict
import time
import asyncio
# from config import CLEARED_PRICES_DIR # type: ignore #переменные подгружаются корректно, проблема в папках
import sqlite3
import aiosqlite
from functools import wraps
import aiosqlite
import asyncio
import time
from functools import wraps

import logging
logger = logging.getLogger("app")

def retry(max_attempts=3, delay=1, exceptions=(Exception,)):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            last_exception = None
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    attempt += 1
                    logger.warning(f"Попытка {attempt} для функции {func.__name__} не удалась: {e}")
                    if attempt < max_attempts:
                        await asyncio.sleep(delay)
            logger.error(f"Все {max_attempts} попыток для функции {func.__name__} не удались.")
            raise RuntimeError(
                f"Функция {func.__name__} не смогла завершиться успешно после {max_attempts} попыток."
            ) from last_exception
        return wrapper
    return decorator

@retry(max_attempts=5, delay=2, exceptions=(aiosqlite.Error,))
async def async_set_journal_mode_wal(db_path):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.commit()
            logger.info("Режим журналирования установлен на WAL.")
    except Exception as e:
        logger.warning(f"Не удалось установить journal_mode=WAL: {e}")

async def async_vacuum_analyze(db_path):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("VACUUM;")
            await db.execute("ANALYZE;")
            await db.commit()
            logger.info("VACUUM и ANALYZE успешно выполнены.")
    except Exception as e:
        logger.warning(f"Не удалось выполнить VACUUM/ANALYZE: {e}")

async def async_set_foreign_keys(db_path, enable=False):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(f"PRAGMA foreign_keys={'ON' if enable else 'OFF'};")
            await db.commit()
            logger.info(f"PRAGMA foreign_keys установлен на {'ON' if enable else 'OFF'}.")
    except Exception as e:
        logger.warning(f"Не удалось установить PRAGMA foreign_keys: {e}")

async def async_set_cache_size(db_path, cache_size=-2000000):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute(f"PRAGMA cache_size={cache_size};")
            await db.commit()
            logger.info(f"PRAGMA cache_size установлен на {cache_size}.")
    except Exception as e:
        logger.warning(f"Не удалось установить PRAGMA cache_size: {e}")

async def async_set_synchronous_normal(db_path):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.commit()
            logger.info("PRAGMA synchronous установлен на NORMAL.")
    except Exception as e:
        logger.warning(f"Не удалось установить PRAGMA synchronous: {e}")

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
        raise
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
        raise

async def init_db_mod(db_path, table_name='data_table'):
    await async_set_foreign_keys(db_path, enable=True)
    await async_set_journal_mode_wal(db_path)
    await async_set_synchronous_normal(db_path)
    await async_set_cache_size(db_path, cache_size=-2000000)  # Настройте значение по необходимости
    await async_create_table(db_path, table_name)
    await async_vacuum_analyze(db_path)
    await async_create_indexes(db_path, table_name)

async def async_alter_table_set_primary_key(db_path, table_name='data_table'):
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("BEGIN")
            
            # Создание новой таблицы с Transaction_id как PRIMARY KEY
            await db.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name}_new (
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
            
            # Копирование данных из старой таблицы в новую
            await db.execute(f"""
                INSERT INTO {table_name}_new (Transaction_id, Wallet_id, Amount, Btc_block_time_price, Block_time, Block_height, Block_hash, n)
                SELECT Transaction_id, Wallet_id, Amount, Btc_block_time_price, Block_time, Block_height, Block_hash, n FROM {table_name};
            """)
            
            # Удаление старой таблицы
            await db.execute(f"DROP TABLE {table_name};")
            
            # Переименование новой таблицы в старое имя
            await db.execute(f"ALTER TABLE {table_name}_new RENAME TO {table_name};")
            
            await db.commit()
            logger.info(f"Таблица '{table_name}' успешно изменена с Transaction_id как PRIMARY KEY.")
    except Exception as e:
        if 'db' in locals():
            await db.rollback()
        logger.error(f"Ошибка при изменении структуры таблицы: {e}")
        raise

async def async_print_db_schema(db_path, table_name='data_table'):
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            result = await cursor.fetchone()
            await cursor.close()
            if result:
                logger.info(f"Схема таблицы '{table_name}':\n{result[0]}")
            else:
                logger.warning(f"Таблица '{table_name}' не найдена.")
    except Exception as e:
        logger.warning(f"Не удалось получить схему базы данных: {e}")


