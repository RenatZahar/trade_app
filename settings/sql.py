import sqlite3

def _max_sql_vars():
    # #коммент: читаем compile-options у in-memory БД; файл базы не трогаем
    try:
        with sqlite3.connect(":memory:") as conn:
            for (opt,) in conn.execute("PRAGMA compile_options;"):
                if opt.startswith("MAX_VARIABLE_NUMBER="):
                    return int(opt.split("=", 1)[1])
    except Exception:
        pass
    return 999

# TODO(iteration_05): перепроверить участки кода, где Transaction_id мог ошибочно
# трактоваться как уникальный ключ строки. В текущей модели одному Transaction_id
# соответствуют разные строки из-за различий по Wallet_id, n и Amount, поэтому
# любые delete/update/merge по одному Transaction_id потенциально небезопасны.
SQL_LIMIT_BATCH_SIZE =  min(int(_max_sql_vars()*0.9), 5000) # возможная точка для оптимизации (900 для SQL_IN_LIST_MAX — для размера IN (?,…,?) и SQL_EXECUTEMANY_BATCH — для «строк на коммит» в executemany (можно держать больше, чем IN))
