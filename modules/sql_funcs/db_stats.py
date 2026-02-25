import sqlite3

def get_sqlite_stat1(db_path):
    try:
        # Устанавливаем соединение с базой данных
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Выполняем запрос к sqlite_stat1
        cursor.execute("SELECT * FROM sqlite_stat1;")
        
        # Получаем содержимое таблицы
        stat_data = cursor.fetchall()
        return stat_data
    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")
    finally:
        if conn:
            conn.close()  # Закрываем соединение с базой данных

def get_table_columns(db_path, table_name):
    """
    Получает информацию о столбцах таблицы.
    
    :param db_path: Путь к базе данных SQLite.
    :param table_name: Имя таблицы.
    :return: DataFrame с информацией о столбцах.
    """
    if isinstance(db_path, Path):
        db_path = str(db_path)
    
    conn = sqlite3.connect(db_path)
    try:
        query = f"PRAGMA table_info('{table_name}');"
        cursor = conn.execute(query)
        columns_info = cursor.fetchall()
        
        # Столбцы: cid, name, type, notnull, dflt_value, pk
        df_columns = pd.DataFrame(columns_info, columns=['cid', 'name', 'type', 'notnull', 'dflt_value', 'pk'])
        return df_columns
    finally:
        conn.close()

def get_table_indexes(db_path, table_name):
    """
    Получает информацию об индексах таблицы.
    
    :param db_path: Путь к базе данных SQLite.
    :param table_name: Имя таблицы.
    :return: DataFrame с информацией об индексах.
    """
    if isinstance(db_path, Path):
        db_path = str(db_path)
    
    conn = sqlite3.connect(db_path)
    try:
        # Получаем список индексов
        query = f"PRAGMA index_list('{table_name}');"
        cursor = conn.execute(query)
        indexes = cursor.fetchall()
        
        # Столбцы: seq, name, unique, origin, partial
        df_indexes = pd.DataFrame(indexes, columns=['seq', 'name', 'unique', 'origin', 'partial'])
        
        # Получаем подробную информацию о каждом индексе
        index_details = []
        for _, row in df_indexes.iterrows():
            index_name = row['name']
            detail_query = f"PRAGMA index_info('{index_name}');"
            detail_cursor = conn.execute(detail_query)
            index_info = detail_cursor.fetchall()
            # Столбцы: seqno, cid, name
            df_index_info = pd.DataFrame(index_info, columns=['seqno', 'cid', 'name'])
            index_details.append((index_name, df_index_info))
        
        return df_indexes, index_details
    finally:
        conn.close()

def display_table_info(db_path, table_name):
    """
    Выводит информацию о столбцах и индексах таблицы.
    
    :param db_path: Путь к базе данных SQLite.
    :param table_name: Имя таблицы.
    """
    # Получаем информацию о столбцах
    df_columns = get_table_columns(db_path, table_name)
    print(f"Информация о столбцах таблицы '{table_name}':")
    print(df_columns)
    print("\n")
    
    # Получаем информацию об индексах
    df_indexes, index_details = get_table_indexes(db_path, table_name)
    print(f"Список индексов таблицы '{table_name}':")
    print(df_indexes)
    print("\n")
    
    # Подробная информация о каждом индексе
    for index_name, df_index_info in index_details:
        print(f"Подробная информация об индексе '{index_name}':")
        print(df_index_info)
        print("\n")


# Путь к файлу базы данных
BLOCKS_SQL_DATA = r"C:\blocks_sql_data\blocks_sql_data_db.db"
table_name = 'data_table'

stat_data = get_sqlite_stat1(BLOCKS_SQL_DATA)
print("Содержимое sqlite_stat1:", stat_data)

display_table_info(BLOCKS_SQL_DATA, table_name)

