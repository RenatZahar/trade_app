import asyncio
import os


from db_servise_funcs import (
    init_db_mod,
    async_print_db_schema,
    async_alter_table_set_primary_key
)
from settings.paths import BLOCKS_SQL_DATA
# проверить чтобы все действия были реализованы через копирование на диск С. 

import logging
logger = logging.getLogger("app")
def setup_temp_directory(temp_dir='C:/sqlite_temp'):
    """
    Настройка временного каталога для SQLite.
    
    :param temp_dir: Путь к временной директории.
    """
    os.environ['TEMP'] = temp_dir
    os.environ['TMP'] = temp_dir
    os.makedirs(temp_dir, exist_ok=True)
    logger.info(f"Временная директория установлена на {temp_dir}")

async def main_db_servise():
    logger.info("Начало инициализации базы данных")
    
    setup_temp_directory('I:/sqlite_temp')
    logger.info(f"Путь к базе данных: {BLOCKS_SQL_DATA}")

    await init_db_mod(BLOCKS_SQL_DATA, table_name='data_table')

    await async_alter_table_set_primary_key(BLOCKS_SQL_DATA, table_name='data_table')
    
    await async_print_db_schema(BLOCKS_SQL_DATA, table_name='data_table')
    
    logger.info("Инициализация базы данных завершена")

if __name__ == "__main__":
    asyncio.run(main_db_servise())


# Да, такая практика существует, и ее часто применяют в Python проектах. 
# Вы можете назвать файл как угодно (например, module_runner.py или любое другое осмысленное название), 
# и при этом сохранить возможность запускать его как самостоятельный скрипт или импортировать 
# и вызывать его функциональность из другого файла (например, из main.py). 
# Для этого используется специальная конструкция 
# if __name__ == "__main__":, которая позволяет контролировать, когда и как выполняется код.

