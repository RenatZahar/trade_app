


"""Design notes and runtime entrypoint for live BTC-vs-SQL consistency checks."""


# 
# Цель:
# - выбрать n блоков из реально существующих Block_height в SQL;
# - независимо реконструировать эти же блоки через BTC RPC;
# - привести SQL-данные и BTC-данные к одинаковому табличному виду;
# - сравнить строки на логическую идентичность.
#
# Входные параметры теста:
# - n: сколько блоков проверять;
# - seed: для воспроизводимой случайной выборки;
# - при отсутствии live-зависимостей тест должен skip, а не падать шумно.
#
# Логика теста:
# 1. Через SQL получить минимальный и максимальный Block_height.
# 2. Проверить диапазон на дырки:
#    - сформировать список отсутствующих блоков;
#    - сохранить его в один перезаписываемый диагностический файл.
# 3. Получить список реально существующих Block_height.
# 4. Выбрать n случайных блоков именно из реально существующих значений,
#    а не просто из диапазона min/max.
# 5. Для выбранных блоков собрать SQL-таблицу.
# 6. Для тех же блоков заново скачать block data из BTC RPC.
# 7. Отдельной логикой реконструировать vout.
# 8. Отдельной логикой реконструировать vin через prev_txid + vout.
# 9. Свести BTC-результат в таблицу того же вида, что и в SQL.
#
# Канонизация перед сравнением обязательна:
# - одинаковый набор столбцов;
# - одинаковый порядок столбцов;
# - одинаковые типы данных;
# - одинаковая сортировка строк внутри каждого блока;
# - одинаковая обработка NULL/пустых значений;
# - заранее оговоренная логика сравнения float-полей.
#
# Сравнение:
# - допускается разница в порядке строк;
# - сравниваются все столбцы после канонизации;
# - сравнение делается поблочно и по всей выборке.
#
# Результат теста:
# - список идентичных блоков;
# - список неидентичных блоков;
# - диагностическая таблица по неидентичным блокам, как минимум:
#   - block_height;
#   - sql_rows;
#   - btc_rows;
#   - only_in_sql_rows;
#   - only_in_btc_rows;
#   - avg_amount_only_in_sql;
#   - avg_amount_only_in_btc.
#
# Тест должен ловить:
# - неправильную привязку vin к prev_tx.vout;
# - пропущенные входы/выходы;
# - дубляжи строк;
# - ошибки группировки;
# - неполную запись в SQL;
# - расхождение старых данных БД с текущей логикой реконструкции.

import random
import sqlite3
import time
from collections import Counter

import pandas as pd

from modules.blockchain_parser import async_parser_functions as apf
from modules.btc_core_init.btc_core_manager import get_btc_status
from settings.parser import MIN_VALUE_THRESHOLD
from settings.paths import APP_TEMP_DIR, BLOCKS_SQL_DATA, CLEARED_PRICES_DIR
from settings.sql import LOW_TX_WALLET_MAX_TX_COUNT, TXS_MOVED


RAW_RECORD_COLUMNS = [
    "Transaction_id",
    "Wallet_id",
    "Amount",
    "Btc_block_time_price",
    "Block_time",
    "Block_height",
    "Block_hash",
    "n",
]

COMPARE_COLUMNS = [
    "Transaction_id",
    "Wallet_id",
    "Btc_block_time_price",
    "Block_time",
    "Block_height",
    "Block_hash",
    "n",
    "Amount",
    "Transactions_Count",
]

COMPARE_SORT_COLUMNS = [
    "Block_height",
    "Transaction_id",
    "Wallet_id",
    "n",
]

ARTIFACTS_DIR = APP_TEMP_DIR / "downloaded_from_btc_data_test"


def get_sql_source_tables() -> list[str]:
    if TXS_MOVED:
        return ["data_table", "few_tx_wallets"]
    return ["data_table"]


def get_existing_sql_tables(conn: sqlite3.Connection, requested_tables: list[str]) -> list[str]:
    placeholders = ", ".join(["?"] * len(requested_tables))
    cursor = conn.cursor()
    cursor.execute(
        f"""
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name IN ({placeholders})
        ORDER BY name
        """,
        requested_tables,
    )
    rows = cursor.fetchall()
    return [str(row[0]) for row in rows]


def get_existing_block_heights_from_sql(db_path=BLOCKS_SQL_DATA) -> list[int]:
    """Return sorted unique Block_height values already present in SQL."""
    with sqlite3.connect(db_path) as conn:
        source_tables = get_existing_sql_tables(conn, get_sql_source_tables())
        if not source_tables:
            return []

        union_query = "\nUNION\n".join(
            [
                f"SELECT Block_height FROM {table_name} WHERE Block_height IS NOT NULL"
                for table_name in source_tables
            ]
        )
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT DISTINCT Block_height
            FROM (
                {union_query}
            )
            ORDER BY Block_height
            """
        )
        rows = cursor.fetchall()
    
    return [int(row[0]) for row in rows]


def get_existing_requested_block_heights_from_sql(
    requested_blocks: list[int],
    db_path=BLOCKS_SQL_DATA,
) -> list[int]:
    """Return requested Block_height values that already exist in SQL."""
    if not requested_blocks:
        return []

    placeholders = ", ".join(["?"] * len(requested_blocks))
    with sqlite3.connect(db_path) as conn:
        source_tables = get_existing_sql_tables(conn, get_sql_source_tables())
        if not source_tables:
            return []

        union_query = "\nUNION\n".join(
            [
                f"""
                SELECT Block_height
                FROM {table_name}
                WHERE Block_height IN ({placeholders})
                """
                for table_name in source_tables
            ]
        )
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT DISTINCT Block_height
            FROM (
                {union_query}
            )
            ORDER BY Block_height
            """,
            requested_blocks * len(source_tables),
        )
        rows = cursor.fetchall()

    return [int(row[0]) for row in rows]


def normalize_requested_blocks(requested_blocks: list[int]) -> list[int]:
    normalized_blocks = []
    seen_blocks = set()
    for block_height in requested_blocks:
        block_height = int(block_height)
        if block_height <= 0:
            raise RuntimeError("requested_blocks must contain only positive block heights.")
        if block_height in seen_blocks:
            continue
        normalized_blocks.append(block_height)
        seen_blocks.add(block_height)
    return normalized_blocks


def ensure_bitcoin_core_ready_for_test() -> None:
    for _ in range(5):
        if get_btc_status():
            return
        time.sleep(5)

    raise RuntimeError(
        "Bitcoin Core is not ready for the integration test. "
        "The node could not be started or is still unavailable for RPC."
    )

def get_absent_blocks(blocks_list):
    min_block = min(blocks_list)
    max_block = max(blocks_list)
    blocks_list = set(blocks_list)
    range_length = max_block-min_block+1
    absent_blocks = []
    current_block = min_block
    for _ in range(0, range_length):
        if current_block not in blocks_list:
            absent_blocks.append(current_block)
        current_block+=1

    return absent_blocks


def get_sql_data_for_blocks(
    random_blocks: list[int],
    db_path=BLOCKS_SQL_DATA,
) -> pd.DataFrame:
    if not random_blocks:
        return pd.DataFrame()

    placeholders = ", ".join(["?"] * len(random_blocks))
    with sqlite3.connect(db_path) as conn:
        source_tables = get_existing_sql_tables(conn, get_sql_source_tables())
        if not source_tables:
            return pd.DataFrame()

        union_query = "\nUNION ALL\n".join(
            [
                f"""
                SELECT *
                FROM {table_name}
                WHERE Block_height IN ({placeholders})
                """
                for table_name in source_tables
            ]
        )
        query = f"""
            SELECT *
            FROM (
                {union_query}
            )
            ORDER BY Block_height, Transaction_id, Wallet_id, n
        """
        params = random_blocks * len(source_tables)
        return pd.read_sql_query(query, conn, params=params)


def is_coinbase_transaction(tx_details: dict) -> bool:
    return any("coinbase" in vin_entry for vin_entry in tx_details.get("vin", []))


def passes_min_value_threshold(tx_details: dict) -> bool:
    return any(
        float(vout.get("value", 0)) >= MIN_VALUE_THRESHOLD
        for vout in tx_details.get("vout", [])
    )


def get_btc_price_frame() -> pd.DataFrame:
    return pd.read_parquet(CLEARED_PRICES_DIR)


def get_btc_price_for_block_time(block_time: int, btc_price: pd.DataFrame) -> float:
    target_time = pd.to_datetime(int(block_time), unit="s")
    index = btc_price["Human_time"].searchsorted(target_time)
    closest_index = max(min(index, len(btc_price) - 1), 0)
    return round(float(btc_price.iloc[closest_index]["Price"]), 2)


def get_block_from_chain(block_height: int, rpc_connection) -> dict:
    block_hash = apf.sync_rpc_connection(rpc_connection, "getblockhash", block_height)
    return apf.sync_rpc_connection(rpc_connection, "getblock", block_hash)


def get_transactions_for_block(block_data: dict, rpc_connection) -> list[dict]:
    commands = [
        ["getrawtransaction", txid, 1, block_data["hash"]]
        for txid in block_data["tx"]
    ]
    tx_details_list = apf.sync_rpc_connection(rpc_connection, None, commands)
    return [
        tx_details
        for tx_details in tx_details_list
        if (
            tx_details
            and not is_coinbase_transaction(tx_details)
            and passes_min_value_threshold(tx_details)
        )
    ]


def get_prev_txids_for_block(tx_details_list: list[dict]) -> set[str]:
    prev_txids = set()
    for tx_details in tx_details_list:
        for vin in tx_details.get("vin", []):
            prev_txid = vin.get("txid")
            if prev_txid:
                prev_txids.add(prev_txid)
    return prev_txids


def get_prev_transactions(prev_txids: set[str], rpc_connection) -> dict[str, dict]:
    if not prev_txids:
        return {}

    commands = [
        ["getrawtransaction", prev_txid, 1]
        for prev_txid in sorted(prev_txids)
    ]
    prev_tx_details_list = apf.sync_rpc_connection(rpc_connection, None, commands)
    return {
        tx_details["txid"]: tx_details
        for tx_details in prev_tx_details_list
        if tx_details and not is_coinbase_transaction(tx_details)
    }


def get_current_chain_height(rpc_connection) -> int:
    return int(apf.sync_rpc_connection(rpc_connection, "getblockcount"))


def validate_requested_blocks_are_available(
    requested_blocks: list[int],
    rpc_connection,
) -> None:
    current_chain_height = get_current_chain_height(rpc_connection)
    max_requested_block = max(requested_blocks)
    if current_chain_height < max_requested_block:
        raise RuntimeError(
            "Bitcoin Core is not synced to the required height for this test. "
            f"Current local height={current_chain_height}, "
            f"max requested block={max_requested_block}."
        )


def build_vout_records_for_block(
    tx_details_list: list[dict],
    block_data: dict,
    btc_time_price: float,
) -> list[list]:
    records = []
    for tx_details in tx_details_list:
        txid = tx_details["txid"]
        for vout in tx_details.get("vout", []):
            wallet_id = vout.get("scriptPubKey", {}).get("address")
            if wallet_id is None:
                continue
            records.append(
                [
                    txid,
                    wallet_id,
                    vout["value"],
                    btc_time_price,
                    block_data["time"],
                    block_data["height"],
                    block_data["hash"],
                    vout["n"],
                ]
            )
    return records


def build_vin_records_for_block(
    tx_details_list: list[dict],
    prev_tx_map: dict[str, dict],
    block_data: dict,
    btc_time_price: float,
) -> list[list]:
    records = []
    for tx_details in tx_details_list:
        current_txid = tx_details["txid"]
        for vin in tx_details.get("vin", []):
            prev_txid = vin.get("txid")
            prev_vout_index = vin.get("vout")
            if prev_txid is None or prev_vout_index is None:
                continue

            prev_tx_details = prev_tx_map.get(prev_txid)
            if prev_tx_details is None:
                continue

            matching_vout = next(
                (
                    vout
                    for vout in prev_tx_details.get("vout", [])
                    if vout.get("n") == prev_vout_index
                ),
                None,
            )
            if matching_vout is None:
                continue

            records.append(
                [
                    current_txid,
                    matching_vout.get("scriptPubKey", {}).get("address"),
                    -matching_vout["value"],
                    btc_time_price,
                    block_data["time"],
                    block_data["height"],
                    block_data["hash"],
                    prev_vout_index,
                ]
            )
    return records


def normalize_records_to_compare_df(raw_records: list[list]) -> pd.DataFrame:
    if not raw_records:
        return pd.DataFrame(columns=COMPARE_COLUMNS)

    data = pd.DataFrame(raw_records, columns=RAW_RECORD_COLUMNS)
    data["Amount"] = data["Amount"].astype("float64")
    data = data.groupby(
        [
            "Transaction_id",
            "Wallet_id",
            "Btc_block_time_price",
            "Block_time",
            "Block_height",
            "Block_hash",
            "n",
        ],
        dropna=False,
    ).agg(
        Amount=("Amount", "sum"),
        Transactions_Count=("n", "count"),
    ).reset_index()

    data = data[COMPARE_COLUMNS]
    data["Transaction_id"] = data["Transaction_id"].astype(str)
    data["Wallet_id"] = data["Wallet_id"].astype(str)
    data["Btc_block_time_price"] = data["Btc_block_time_price"].astype(float)
    data["Block_time"] = data["Block_time"].astype(int)
    data["Block_height"] = data["Block_height"].astype(int)
    data["Block_hash"] = data["Block_hash"].astype(str)
    data["n"] = data["n"].astype(int)
    data["Amount"] = data["Amount"].astype(float)
    data["Transactions_Count"] = data["Transactions_Count"].astype(int)
    data = data.sort_values(by=COMPARE_SORT_COLUMNS).reset_index(drop=True)
    return data


def canonicalize_sql_data_for_compare(sql_data: pd.DataFrame) -> pd.DataFrame:
    if sql_data.empty:
        return pd.DataFrame(columns=COMPARE_COLUMNS)

    data = sql_data.copy()
    data = data[COMPARE_COLUMNS]
    data["Transaction_id"] = data["Transaction_id"].astype(str)
    data["Wallet_id"] = data["Wallet_id"].astype(str)
    data["Btc_block_time_price"] = data["Btc_block_time_price"].astype(float)
    data["Block_time"] = data["Block_time"].astype(int)
    data["Block_height"] = data["Block_height"].astype(int)
    data["Block_hash"] = data["Block_hash"].astype(str)
    data["n"] = data["n"].astype(int)
    data["Amount"] = data["Amount"].astype(float)
    data["Transactions_Count"] = data["Transactions_Count"].astype(int)
    data = data.sort_values(by=COMPARE_SORT_COLUMNS).reset_index(drop=True)
    return data


def compare_sql_and_chain_data(
    sql_data: pd.DataFrame,
    chain_data: pd.DataFrame,
) -> tuple[list[int], list[int], pd.DataFrame]:
    identical_blocks = []
    non_identical_blocks = []
    diagnostics = []
    amount_index = COMPARE_COLUMNS.index("Amount")

    block_heights = sorted(
        set(sql_data["Block_height"].tolist()) | set(chain_data["Block_height"].tolist())
    )

    for block_height in block_heights:
        sql_block = sql_data.loc[sql_data["Block_height"] == block_height].reset_index(drop=True)
        chain_block = chain_data.loc[chain_data["Block_height"] == block_height].reset_index(drop=True)

        if sql_block.equals(chain_block):
            identical_blocks.append(block_height)
            continue

        non_identical_blocks.append(block_height)
        sql_counter = Counter(map(tuple, sql_block.to_numpy()))
        chain_counter = Counter(map(tuple, chain_block.to_numpy()))
        only_in_sql = list((sql_counter - chain_counter).elements())
        only_in_chain = list((chain_counter - sql_counter).elements())

        avg_amount_only_in_sql = (
            round(sum(row[amount_index] for row in only_in_sql) / len(only_in_sql), 8)
            if only_in_sql
            else 0.0
        )
        avg_amount_only_in_chain = (
            round(sum(row[amount_index] for row in only_in_chain) / len(only_in_chain), 8)
            if only_in_chain
            else 0.0
        )

        diagnostics.append(
            {
                "block_height": block_height,
                "sql_rows": len(sql_block),
                "btc_rows": len(chain_block),
                "only_in_sql_rows": len(only_in_sql),
                "only_in_btc_rows": len(only_in_chain),
                "avg_amount_only_in_sql": avg_amount_only_in_sql,
                "avg_amount_only_in_btc": avg_amount_only_in_chain,
            }
        )

    return identical_blocks, non_identical_blocks, pd.DataFrame(diagnostics)


def build_difference_rows(
    sql_data: pd.DataFrame,
    chain_data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    only_in_sql_rows = []
    only_in_btc_rows = []

    block_heights = sorted(
        set(sql_data["Block_height"].tolist()) | set(chain_data["Block_height"].tolist())
    )

    for block_height in block_heights:
        sql_block = sql_data.loc[sql_data["Block_height"] == block_height].reset_index(drop=True)
        chain_block = chain_data.loc[chain_data["Block_height"] == block_height].reset_index(drop=True)

        sql_counter = Counter(map(tuple, sql_block.to_numpy()))
        chain_counter = Counter(map(tuple, chain_block.to_numpy()))

        only_in_sql_rows.extend(list((sql_counter - chain_counter).elements()))
        only_in_btc_rows.extend(list((chain_counter - sql_counter).elements()))

    only_in_sql_df = pd.DataFrame(only_in_sql_rows, columns=COMPARE_COLUMNS)
    only_in_btc_df = pd.DataFrame(only_in_btc_rows, columns=COMPARE_COLUMNS)
    return only_in_sql_df, only_in_btc_df


def save_compare_artifacts(
    sql_data: pd.DataFrame,
    chain_data: pd.DataFrame,
    diagnostics_df: pd.DataFrame,
    only_in_sql_df: pd.DataFrame,
    only_in_btc_df: pd.DataFrame,
) -> dict[str, str]:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    sql_path = ARTIFACTS_DIR / "sql_compare.parquet"
    chain_path = ARTIFACTS_DIR / "btc_compare.parquet"
    diagnostics_path = ARTIFACTS_DIR / "diagnostics.parquet"
    only_in_sql_path = ARTIFACTS_DIR / "only_in_sql.parquet"
    only_in_btc_path = ARTIFACTS_DIR / "only_in_btc.parquet"

    sql_data.to_parquet(sql_path, index=False)
    chain_data.to_parquet(chain_path, index=False)
    diagnostics_df.to_parquet(diagnostics_path, index=False)
    only_in_sql_df.to_parquet(only_in_sql_path, index=False)
    only_in_btc_df.to_parquet(only_in_btc_path, index=False)

    return {
        "sql_compare_parquet": str(sql_path),
        "btc_compare_parquet": str(chain_path),
        "diagnostics_parquet": str(diagnostics_path),
        "only_in_sql_parquet": str(only_in_sql_path),
        "only_in_btc_parquet": str(only_in_btc_path),
    }


def get_chain_data_for_blocks(requested_blocks):
    if not requested_blocks:
        return pd.DataFrame(columns=COMPARE_COLUMNS)

    rpc_connection = apf.get_rpc_connection()
    validate_requested_blocks_are_available(requested_blocks, rpc_connection)
    btc_price = get_btc_price_frame()
    all_records = []

    for block_height in requested_blocks:
        block_data = get_block_from_chain(block_height, rpc_connection)
        tx_details_list = get_transactions_for_block(block_data, rpc_connection)
        prev_txids = get_prev_txids_for_block(tx_details_list)
        prev_tx_map = get_prev_transactions(prev_txids, rpc_connection)
        btc_time_price = get_btc_price_for_block_time(block_data["time"], btc_price)

        all_records.extend(
            build_vout_records_for_block(tx_details_list, block_data, btc_time_price)
        )
        all_records.extend(
            build_vin_records_for_block(tx_details_list, prev_tx_map, block_data, btc_time_price)
        )

    return normalize_records_to_compare_df(all_records)


def run_downloaded_from_btc_data_test(
    blocks_count: int | None = None,
    seed: int | None = None,
    requested_blocks: list[int] | None = None,
) -> dict:
    """Runtime entrypoint for the future live consistency test.

    The actual BTC-vs-SQL comparison logic is intentionally left for the next
    implementation step; for now this function gives `main.py` a typed,
    loggable integration-test entrypoint with explicit parameters.
    """
    summary = {
        "test_name": "test_downloaded_from_btc_data",
        "seed": seed,
        "txs_moved": TXS_MOVED,
        "low_tx_wallet_max_tx_count": LOW_TX_WALLET_MAX_TX_COUNT,
        "sql_source_tables": get_sql_source_tables(),
    }
    ensure_bitcoin_core_ready_for_test()

    if requested_blocks is not None:
        requested_blocks = normalize_requested_blocks(requested_blocks)
        if not requested_blocks:
            raise RuntimeError("requested_blocks must contain at least one block height.")

        existing_requested_blocks = set(
            get_existing_requested_block_heights_from_sql(requested_blocks)
        )
        missing_blocks = [
            block_height
            for block_height in requested_blocks
            if block_height not in existing_requested_blocks
        ]
        if missing_blocks:
            raise RuntimeError(
                "Requested blocks are not present in SQL: "
                f"{missing_blocks}"
            )
        summary["selection_mode"] = "explicit_blocks"
    else:
        if blocks_count is None:
            raise RuntimeError("blocks_count is required when requested_blocks is not provided.")

        blocks_list = get_existing_block_heights_from_sql()

        if not blocks_list:
            raise RuntimeError("SQL table data_table does not contain any Block_height values.")

        absent_blocks = get_absent_blocks(blocks_list)

        if absent_blocks:
            summary["qnt_absent_blocks"] = len(absent_blocks)
            summary["absent_blocks"] = absent_blocks

        if blocks_count > len(blocks_list):
            raise RuntimeError("blocks_list для проверки больше чем blocks_count")

        requested_blocks = random.Random(seed).sample(blocks_list, blocks_count)
        summary["selection_mode"] = "random_sample"

    summary["requested_blocks"] = requested_blocks
    blocks_sql_data = canonicalize_sql_data_for_compare(get_sql_data_for_blocks(requested_blocks))
    summary["sql_rows_count"] = len(blocks_sql_data)

    blocks_chain_data = get_chain_data_for_blocks(requested_blocks)
    summary["chain_rows_count"] = len(blocks_chain_data)
    identical_blocks, non_identical_blocks, diagnostics_df = compare_sql_and_chain_data(
        blocks_sql_data,
        blocks_chain_data,
    )
    only_in_sql_df, only_in_btc_df = build_difference_rows(
        blocks_sql_data,
        blocks_chain_data,
    )
    artifact_paths = save_compare_artifacts(
        blocks_sql_data,
        blocks_chain_data,
        diagnostics_df,
        only_in_sql_df,
        only_in_btc_df,
    )
    summary["identical_blocks"] = identical_blocks
    summary["non_identical_blocks"] = non_identical_blocks
    summary["identical_blocks_count"] = len(identical_blocks)
    summary["non_identical_blocks_count"] = len(non_identical_blocks)
    summary["diagnostics_rows_count"] = len(diagnostics_df)
    summary["diagnostics_records"] = diagnostics_df.to_dict(orient="records")
    summary["only_in_sql_rows_count"] = len(only_in_sql_df)
    summary["only_in_btc_rows_count"] = len(only_in_btc_df)
    summary.update(artifact_paths)
    summary["comparison_status"] = (
        "all_blocks_identical"
        if not non_identical_blocks
        else "mismatch_found"
    )

    summary["status"] = "finished"
    return summary
