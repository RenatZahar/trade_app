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


LOW_TX_WALLET_MAX_TX_COUNT = 4  # Кошельки с количеством строк <= порога выносятся в few_tx_wallets.
# True: транзакции разнесены между data_table и few_tx_wallets.
# False: все строки собраны обратно в data_table.
TXS_MOVED = False
# TODO(iteration_05): проверить, где еще используется TXS_PER_WALLET_MORE_THAN,
# и явно зафиксировать, как этот порог должен соотноситься с состоянием TXS_MOVED = False.
# Сейчас это legacy alias на тот же порог, но семантика состояния БД требует отдельной проверки.
TXS_PER_WALLET_MORE_THAN = LOW_TX_WALLET_MAX_TX_COUNT
# TODO(iteration_05): перепроверить участки кода, где Transaction_id мог ошибочно
# трактоваться как уникальный ключ строки. В текущей модели одному Transaction_id
# соответствуют разные строки из-за различий по Wallet_id, n и Amount, поэтому
# любые delete/update/merge по одному Transaction_id потенциально небезопасны.
SQL_LIMIT_BATCH_SIZE =  min(int(_max_sql_vars()*0.9), 5000) # возможная точка для оптимизации (900 для SQL_IN_LIST_MAX — для размера IN (?,…,?) и SQL_EXECUTEMANY_BATCH — для «строк на коммит» в executemany (можно держать больше, чем IN))
SQL_RETURN_BATCH_SIZE = 50000  # Батч для обычного sql-to-sql возврата few_tx_wallets -> data_table.
SQL_MOVE_TXS_BATCH_ROWS = 1_000_000  # Целевой размер батча move_txs в строках; фактический батч режется по кошелькам.
SQL_MOVE_TXS_BACK_BATCH_ROWS = 1_000_000  # Крупный батч для maintenance-возврата few_tx_wallets -> data_table.
