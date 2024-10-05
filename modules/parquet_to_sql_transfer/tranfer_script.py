# tranfer_script

import os
import pandas as pd
import sqlite3
from config import TXS_PARQUET_DIR, BLOCKS_SQL_DATA
import time

TEST = 1

pd.set_option('display.expand_frame_repr', False)  # не переносить строки
pd.set_option('display.max_colwidth', None)
pd.set_option('display.float_format', lambda x: '%.3f' % x)
pd.set_option('display.max_rows', 30)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)

def get_existing_indexes(conn):
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = cursor.fetchall()
    cursor.close()
    return [index[0] for index in indexes]

def create_needed_indexes(conn):
    existing_indexes = get_existing_indexes(conn)

    if 'idx_wallet_id' not in existing_indexes:
        print("Создание индекса на wallet_id")
        conn.execute("CREATE INDEX idx_wallet_id ON data_table(wallet_id);")
        conn.commit()
        print("Индекс на wallet_id создан")
    else:
        print("Индекс на wallet_id уже существует")

    if 'idx_Block_time' not in existing_indexes:
        print("Создание индекса на Block_time")
        conn.execute("CREATE INDEX idx_Block_time ON data_table(Block_time);")
        conn.commit()
        print("Индекс на Block_time создан")
    else:
        print("Индекс на Block_time уже существует")



def conn_settings(new_conn):
    new_conn.execute("PRAGMA synchronous = OFF;")
    new_conn.execute("PRAGMA journal_mode = OFF;")
    new_conn.execute("PRAGMA temp_store = MEMORY;")
    new_conn.execute("PRAGMA cache_size = -2000000;")  # Установите размер кэша в зависимости от вашей оперативной памяти
    return new_conn





def get_total_rows(conn, condition=None):
    cursor = conn.cursor()
    if condition:
        query = f"SELECT COUNT(*) FROM data_table WHERE {condition};"
    else:
        query = "SELECT COUNT(*) FROM data_table;"
    cursor.execute(query)
    total_rows = cursor.fetchone()[0]
    cursor.close()
    return total_rows

def create_new_database_with_settings(new_db_path):
    new_conn = sqlite3.connect(new_db_path)

    # Устанавливаем необходимые PRAGMA настройки
    new_conn.execute("PRAGMA auto_vacuum = INCREMENTAL;")
    new_conn.execute("PRAGMA journal_mode = MEMORY;")
    new_conn.execute("PRAGMA temp_store = MEMORY;")
    new_conn.execute("PRAGMA cache_size = -500000;")  
    new_conn.execute("PRAGMA synchronous = OFF;")
    new_conn.execute("PRAGMA locking_mode = EXCLUSIVE;")
    new_conn.execute("VACUUM;")  # Закрепляем режим auto_vacuum
    new_conn.commit()
    return new_conn

def transfer_script():
    # Устанавливаем временные директории на диск D:
    os.environ['TEMP'] = 'D:/sqlite_temp'
    os.environ['TMP'] = 'D:/sqlite_temp'
    os.makedirs('D:/sqlite_temp', exist_ok=True)

    # Путь к старой базе данных (открываем в режиме только для чтения)
    old_sqlite_db = fr'file:{BLOCKS_SQL_DATA}/database.db?mode=ro'
    old_conn = sqlite3.connect(old_sqlite_db, uri=True)

    # Устанавливаем PRAGMA настройки для старой базы данных
    old_conn.execute("PRAGMA temp_store = MEMORY;")
    old_conn.execute("PRAGMA cache_size = -500000;")  # 500 MB кэша
    old_conn.execute("PRAGMA journal_mode = OFF;")
    old_conn.execute("PRAGMA synchronous = OFF;")

    # Путь к новой базе данных на диске D
    new_sqlite_db = r'D:\sql_folder\database.db'
    os.makedirs(r'D:\sql_folder', exist_ok=True)

    # total_rows = get_total_rows(old_conn)
    # print(f"Общее количество строк в таблице: {total_rows}")



    # Проверяем, существует ли файл, и удаляем его
    if os.path.exists(new_sqlite_db):
        os.remove(new_sqlite_db)
        print(f"Старый файл базы данных {new_sqlite_db} удалён.")

    new_conn = create_new_database_with_settings(new_sqlite_db)

    # Получаем SQL-запрос для создания таблицы из старой базы данных
    create_table_sql = old_conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='data_table';").fetchone()[0]
    new_conn.execute(create_table_sql)
    new_conn.commit()

    # Не создаем индексы до окончания переноса данных
    # create_needed_indexes(new_conn)

    # Перенос данных по частям без использования DataFrame
    batch_size = 15000000  # Размер пакета данных

    # Создаем курсор для старой базы данных
    old_cursor = old_conn.cursor()
    old_cursor.execute("""
        SELECT *
        FROM data_table
        WHERE block_height >= 770000
    """)

    # Создаём подготовленный запрос для вставки данных
    columns = [desc[0] for desc in old_cursor.description]
    placeholders = ', '.join(['?'] * len(columns))
    insert_query = f"INSERT INTO data_table ({', '.join(columns)}) VALUES ({placeholders})"

    total_rows_transferred = 0

    while True:
        start_time = time.time()


        # Получаем следующую партию строк
        rows = old_cursor.fetchmany(batch_size)

        if not rows:
            break

        print("Перенос следующего пакета данных")

        # Вставляем данные в новую базу данных
        new_conn.executemany(insert_query, rows)
        new_conn.commit()  # Фиксируем транзакцию после каждого пакета

        total_rows_transferred += len(rows)
        end_time = time.time()
        print(f'Перенос занял {end_time - start_time:.2f} секунд')
        print(f"Всего перенесено строк: {total_rows_transferred}")

    # Создаем необходимые индексы в новой базе данных после переноса данных
    create_needed_indexes(new_conn)

    # Закрываем курсоры и соединения
    old_cursor.close()
    old_conn.close()
    new_conn.close()

    print("Перенос данных завершен.")
