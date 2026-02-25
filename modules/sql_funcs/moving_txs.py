# moving_txs.py

import sqlite3
import traceback
import time
import sys
from datetime import datetime
from config import setup_logging, BLOCKS_SQL_DATA, TXS_PER_WALLET_MORE_THAN, SQL_LIMIT_BATCH_SIZE

# SQL_LIMIT_BATCH_SIZE подается в функции напрямую а BLOCKS_SQL_DATA - как аргумент фунцкии - как правильно делать? 
# надо переделывать логику. слишком медленно.

def list_tables(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return tables

def check_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # 1) проверяем структуру таблиц
        if not check_table_structures(conn, 'few_tx_wallets', 'data_table'):
            raise Exception("Структуры таблиц не совпадают!")

        # 2) удаляем полные дубликаты строк из data_table
        #    — оставляем только одну строку для каждой комбинации значений во всех столбцах
        cursor.execute("PRAGMA table_info(data_table);")
        cols = [r[1] for r in cursor.fetchall()]
        if not cols:
            raise Exception("data_table не содержит столбцов")

        #комментарий: строим GROUP BY по всем колонкам (кавычки на случай спец.символов)
        group_by = ", ".join(['"{}"'.format(c) for c in cols])

        #комментарий: удаляем все дубликаты, оставляя строку с минимальным rowid для каждой полной комбинации значений
        sql = (
            "DELETE FROM {tbl} "
            "WHERE rowid NOT IN ("
            "  SELECT MIN(rowid) FROM {tbl} "
            "  GROUP BY {grp}"
            ");"
        ).format(tbl="data_table", grp=group_by)

        cursor.execute(sql)
        conn.commit()

    finally:
        cursor.close()
        conn.close()

def get_table_columns(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = [(col[1], normalize_sqlite_type(col[2])) for col in cursor.fetchall()]
    cursor.close()
    return columns

def normalize_sqlite_type(type_name):
    # Оставляем только логически значимые типы
    t = type_name.strip().upper()
    if t in ("INT", "INTEGER", "INT4", "INT8"):
        return "INTEGER"
    if t in ("REAL", "FLOAT", "DOUBLE"):
        return "REAL"
    if t == "TEXT":
        return "TEXT"
    return t

def check_table_structures(conn, table1, table2):
    cols1 = get_table_columns(conn, table1)
    cols2 = get_table_columns(conn, table2)
    # print(cols1)
    # print(cols2)
    if cols1 != cols2:
        print(f"ВНИМАНИЕ! Структуры таблиц не совпадают!")
        print(f"{table1}: {cols1}")
        print(f"{table2}: {cols2}")
        return False
    print("Структуры таблиц совпадают.")
    return True

def get_unique_indices(conn, table_name):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA index_list({table_name});")
    # [('0', 'sqlite_autoindex_data_table_1', 1, ...), ...]
    unique_indices = [row[1] for row in cursor.fetchall() if row[2]]
    cursor.close()
    return unique_indices

def return_few_tx_wallets_to_data_table(db_path,
                                        source_table='few_tx_wallets',
                                        target_table='data_table',
                                        batch_size=SQL_LIMIT_BATCH_SIZE):
    """
    Пакетно переносит все строки из source_table в target_table с помощью executemany
    и удаляет их из source_table.
    """
    print('start return_few_tx_wallets_to_data_table (batch executemany)')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        # Получаем список столбцов для INSERT
        cursor.execute("PRAGMA table_info({});".format(source_table))
        cols = [col[1] for col in cursor.fetchall()]


        col_list = ", ".join(cols)
        placeholders = ", ".join("?" for _ in cols)
        insert_sql = (
            "INSERT INTO {tgt} ({cols}) VALUES ({ph});"
        ).format(tgt=target_table, cols=col_list, ph=placeholders)

        # Предполагаем, что первый столбец — первичный ключ, по нему будем удалять
        pk = 'Transaction_id'
        if pk not in cols:
            raise Exception(f"Ключ {pk} отсутствует в таблице {source_table}")
        pk_idx = cols.index(pk)

        while True:
            # Выбираем очередной батч строк
            cursor.execute(
                "SELECT {cols} FROM {src} LIMIT ?;".format(cols=col_list, src=source_table),
                (batch_size,)
            )
            rows = cursor.fetchall()
            if not rows:
                break

            # Пакетно вставляем
            cursor.executemany(insert_sql, rows)

            # Собираем ключи для удаления этой партии
            ids = [row[pk_idx] for row in rows]
            placeholders_ids = ", ".join("?" for _ in ids)
            delete_sql = (
                "DELETE FROM {src} WHERE {pk} IN ({ph});"
            ).format(src=source_table, pk=pk, ph=placeholders_ids)
            cursor.execute(delete_sql, ids)

            conn.commit()
            print("Перенесено {} строк".format(len(rows)))

        print("Все данные успешно возвращены из {} в {}.".format(source_table, target_table))

    except Exception as e:
        print("Ошибка при возврате данных: {}".format(e))
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_count_in_table(db_path, table_name='temp_wallets'):
    print('start get_count_in_table')
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # #comment: Выполнение запроса для получения количества записей
        cursor.execute("SELECT COUNT(*) FROM {tbl};".format(tbl=table_name))
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count
    except Exception as e:
        print(f"Ошибка при подсчёте записей в таблице {table_name}: {e}")
        return None

def create_target_table(db_path, target_table='few_tx_wallets', source_table='data_table'):
    """
    1. Создает новую таблицу (например, few_tx_wallets) с такой же схемой, как у исходной таблицы (data_table).
    """
    print('start create_target_table')

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # #comment: создание целевой таблицы по схеме исходной таблицы (без данных)
        sql = (
            "CREATE TABLE IF NOT EXISTS {tgt} "
            "AS SELECT * FROM {src} WHERE 0;"
        ).format(tgt=target_table, src=source_table)
        cursor.execute(sql)
        conn.commit()
        print(f"Таблица {target_table} создана или уже существует.")
    except Exception as e:
        print(f"Ошибка при создании таблицы {target_table}: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


def create_temp_wallets_table(db_path, txs_count, source_table='data_table', temp_table='temp_wallets'):
    """
    2. Создает служебную таблицу (temp_wallets) для хранения id кошельков, у которых количество транзакций ≤ txs_count.
       Если таблица уже существует, создание и заполнение пропускается.
    """
    print('start create_temp_wallets_table')
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # #comment: проверка наличия служебной таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", (temp_table,))
        if cursor.fetchone():
            print(f"Таблица {temp_table} уже существует. Пропускаем создание и заполнение.")
            return

        # Создаем служебную таблицу temp_wallets
        sql = """
            CREATE TABLE {tmp} (
                wallet_id TEXT PRIMARY KEY
            );
        """.format(tmp=temp_table)
        cursor.execute(sql)
        conn.commit()

        # Заполняем temp_wallets идентификаторами кошельков с количеством транзакций ≤ 2
        sql = (
            "INSERT INTO {tmp} (wallet_id) "
            "SELECT Wallet_id FROM ( "
            "  SELECT Wallet_id, COUNT(*) AS cnt "
            "  FROM {src} "
            "  GROUP BY Wallet_id "
            ") WHERE cnt <= ?;"
            ).format(tmp=temp_table, src=source_table)
        
        cursor.execute(sql, (txs_count,))
        conn.commit()
        print(f"Таблица {temp_table} успешно создана и заполнена.")
    except Exception as e:
        print(f"Ошибка при создании или заполнении таблицы {temp_table}: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()


def optimize_db(db_path):
    """
    Включает режим WAL и устанавливает оптимальные параметры для ускорения операций записи.
    """
    print('start optimize_db')

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # #comment: включаем режим WAL для улучшения параллелизма и производительности записи
        cursor.execute("PRAGMA journal_mode=WAL;")
        # #comment: устанавливаем нормальную синхронизацию для ускорения записи
        cursor.execute("PRAGMA synchronous=NORMAL;")
        conn.commit()
        cursor.close()
        conn.close()
        print("База данных оптимизирована: включен режим WAL, synchronous=NORMAL.")
    except Exception as e:
        print(f"Ошибка при оптимизации БД: {e}")
        traceback.print_exc()

def process_wallets(db_path, source_table='data_table', target_table='few_tx_wallets', 
                    temp_table='temp_wallets', batch_size=SQL_LIMIT_BATCH_SIZE):
    """
    Порционно обрабатывает кошельки из temp_wallets:
    - Выбирает батчи кошельков из temp_wallets.
    - Для каждого батча вызывает process_wallets_batch.
    - Если temp_wallets пуста, таблица удаляется.
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM {tmp};".format(tmp=temp_table))
        total = cursor.fetchone()[0]
        processed = 0
        start_all = time.time()

        while True:
            cursor.execute("SELECT wallet_id FROM {tmp} LIMIT ?;".format(tmp=temp_table), (batch_size,))
            wallets = [row[0] for row in cursor.fetchall()]
            if not wallets:
                print(f"Таблица {temp_table} пуста. Удаляем таблицу {temp_table}.")
                cursor.execute("DROP TABLE IF EXISTS {tmp};".format(tmp=temp_table))
                conn.commit()
                break

            process_wallets_batch(db_path,
                                source_table=source_table,
                                target_table=target_table,
                                temp_table=temp_table,
                                wallet_ids=wallets)
            
            processed += len(wallets)
            elapsed = time.time() - start_all
            eta = (elapsed / processed) * (total - processed) / 60
            sys.stdout.write(f'\rProcessed: {processed}/{total}, ETA: {eta:.2f} min')
            sys.stdout.flush()

        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Ошибка при обработке кошельков: {e}")
        traceback.print_exc()

def process_wallets_batch(db_path, source_table='data_table', target_table='few_tx_wallets', 
                          temp_table='temp_wallets', wallet_ids=None):
    """
    Обрабатывает одну порцию кошельков за одну транзакцию:
    - Копирует все строки для указанных кошельков из source_table в target_table.
    - Удаляет скопированные строки из source_table.
    - Удаляет обработанные id кошельков из temp_table.
    """
    print('start process_wallets_batch')

    if not wallet_ids:
        return
    try:
        start_time = time.time()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in wallet_ids)  # #comment: генерируем строку "?, ?, ... ?"
        
        # Начинаем транзакцию для всей порции
        cursor.execute("BEGIN;")
        
        # Копируем строки из source_table в target_table для всех кошельков из списка
        sql = (
            "INSERT INTO {target} "
            "SELECT * FROM {source} "
            "WHERE Wallet_id IN ({ph});"
        ).format(
            target=target_table,
            source=source_table,
            ph=placeholders
        )
        cursor.execute(sql, wallet_ids)
        
        # Удаляем скопированные строки из source_table
        sql = "DELETE FROM {src} WHERE Wallet_id IN ({ph});".format(
            src=source_table,
            ph=placeholders
        )
        cursor.execute(sql, wallet_ids)
            
        # Удаляем id кошельков из temp_table
        query_delete_temp = "DELETE FROM {tmp} WHERE wallet_id IN ({ph});".format(
            tmp=temp_table, ph=placeholders
            )
        cursor.execute(query_delete_temp, wallet_ids)
        conn.commit()  # #comment: фиксируем транзакцию для всей группы кошельков
        # print(f"Обработана порция из {len(wallet_ids)} кошельков.")
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при обработке порции кошельков {wallet_ids}: {e}")
        traceback.print_exc()
    finally:
        cursor.close()
        conn.close()

def print_now():
    print(f'Старт в {datetime.now()}')

def create_indexes(db_path):
    # создаём индекс по Wallet_id и Transaction_id во всех таблицах, где есть соответствующие столбцы
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # получаем список всех таблиц
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        # узнаём, какие столбцы есть в таблице
        cursor.execute(f"PRAGMA table_info({table});")
        cols = [col[1] for col in cursor.fetchall()]
        # если есть Wallet_id — создаём индекс
        if 'Wallet_id' in cols:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_wallet_id ON {table}(Wallet_id);"
            )
        # если есть Transaction_id — создаём индекс
        if 'Transaction_id' in cols:
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table}_transaction_id ON {table}(Transaction_id);"
            )
    conn.commit()
    cursor.close()
    conn.close()

def moving_txs():
    print_now()
    #комментрий: после основного переноса выводим количество строк в каждой таблице
    tables = list_tables(BLOCKS_SQL_DATA)
    for tbl in tables:
        cnt = get_count_in_table(BLOCKS_SQL_DATA, table_name=tbl)
        print(f"Таблица {tbl}: {cnt} записей")

    # check_db(BLOCKS_SQL_DATA)
    # create_indexes(BLOCKS_SQL_DATA)
    # return_few_tx_wallets_to_data_table(BLOCKS_SQL_DATA)

    return_few_tx_wallets_to_data_table(BLOCKS_SQL_DATA)   # #коммент: сначала объединяем данные
    check_db(BLOCKS_SQL_DATA)                              # #коммент: чистим и валидируем уже объединённое
    create_indexes(BLOCKS_SQL_DATA)                        # #коммент: индексы после bulk-вставок быстрее строить

    # Шаг 2: Создаем целевую таблицу few_tx_wallets по схеме data_table
    create_target_table(BLOCKS_SQL_DATA, target_table="few_tx_wallets", source_table="data_table")
    
    # Шаг 3: Создаем служебную таблицу temp_wallets и заполняем её идентификаторами кошельков с ≤ 2 транзакциями
    create_temp_wallets_table(BLOCKS_SQL_DATA, TXS_PER_WALLET_MORE_THAN, source_table="data_table", temp_table="temp_wallets")
    
    # Шаг 3.1: Оптимизируем базу (режим WAL и synchronous=NORMAL) для ускорения записи
    optimize_db(BLOCKS_SQL_DATA)
    
    # Шаг 4: Порционно обрабатываем кошельки из temp_wallets
    process_wallets(BLOCKS_SQL_DATA, source_table="data_table", target_table="few_tx_wallets", temp_table="temp_wallets")
    
    print("Работа завершена.")

    tables = list_tables(BLOCKS_SQL_DATA)
    for tbl in tables:
        cnt = get_count_in_table(BLOCKS_SQL_DATA, table_name=tbl)
        print(f"Таблица {tbl}: {cnt} записей")

if __name__ == "__main__":
    moving_txs()
