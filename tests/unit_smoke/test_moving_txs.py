import sqlite3

from modules.sql_funcs import moving_txs


def _insert_rows(conn, table_name, wallet_id, rows_count):
    conn.executemany(
        f"""
        INSERT INTO {table_name} (Transaction_id, Wallet_id, Amount)
        VALUES (?, ?, ?);
        """,
        [
            (f"{table_name}_{wallet_id}_{idx}", wallet_id, float(idx))
            for idx in range(rows_count)
        ],
    )


def _wallets_by_table(conn):
    result = {}
    for table_name in ("data_table", "few_tx_wallets"):
        rows = conn.execute(
            f"""
            SELECT Wallet_id, COUNT(*)
            FROM {table_name}
            GROUP BY Wallet_id
            ORDER BY Wallet_id;
            """
        ).fetchall()
        result[table_name] = dict(rows)
    return result


def test_move_txs_helpers_place_wallets_by_total_rows_across_two_tables(tmp_path):
    db_path = tmp_path / "blocks.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE data_table (
            Transaction_id TEXT,
            Wallet_id TEXT,
            Amount REAL
        );
        """
    )
    conn.execute("CREATE TABLE few_tx_wallets AS SELECT * FROM data_table WHERE 0;")

    _insert_rows(conn, "data_table", "low_from_data", 4)
    _insert_rows(conn, "data_table", "high_from_data", 5)
    _insert_rows(conn, "few_tx_wallets", "high_from_storage", 5)
    _insert_rows(conn, "few_tx_wallets", "low_from_storage", 2)
    conn.commit()
    conn.close()

    moving_txs.create_wallet_targets_table(str(db_path), txs_count=4)
    moving_txs.create_move_rowids_table(
        str(db_path),
        "data_table",
        "few_tx_wallets",
        rowids_table="service_move_to_few_rowids",
    )
    moving_txs.create_move_rowids_table(
        str(db_path),
        "few_tx_wallets",
        "data_table",
        rowids_table="service_move_to_data_rowids",
    )
    moving_txs.move_prepared_rows(
        str(db_path),
        "data_table",
        "few_tx_wallets",
        rowids_table="service_move_to_few_rowids",
        batch_size=2,
    )
    moving_txs.move_prepared_rows(
        str(db_path),
        "few_tx_wallets",
        "data_table",
        rowids_table="service_move_to_data_rowids",
        batch_size=2,
    )
    moving_txs.cleanup_move_txs_service_tables(str(db_path))

    conn = sqlite3.connect(db_path)
    try:
        assert _wallets_by_table(conn) == {
            "data_table": {
                "high_from_data": 5,
                "high_from_storage": 5,
            },
            "few_tx_wallets": {
                "low_from_data": 4,
                "low_from_storage": 2,
            },
        }
        service_tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name LIKE 'service_%';
            """
        ).fetchall()
        assert service_tables == []
    finally:
        conn.close()


def test_rebuild_wallet_tables_places_wallets_by_total_rows_across_two_tables(tmp_path):
    db_path = tmp_path / "blocks.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE data_table (
            Transaction_id TEXT,
            Wallet_id TEXT,
            Amount REAL
        );
        """
    )
    conn.execute("CREATE TABLE few_tx_wallets AS SELECT * FROM data_table WHERE 0;")

    _insert_rows(conn, "data_table", "low_from_data", 4)
    _insert_rows(conn, "data_table", "high_from_data", 5)
    _insert_rows(conn, "few_tx_wallets", "high_from_storage", 5)
    _insert_rows(conn, "few_tx_wallets", "low_from_storage", 2)
    conn.commit()
    conn.close()

    moving_txs.create_wallet_targets_table(str(db_path), txs_count=4)
    moving_txs.rebuild_wallet_tables(str(db_path))
    moving_txs.cleanup_move_txs_service_tables(str(db_path))

    conn = sqlite3.connect(db_path)
    try:
        assert _wallets_by_table(conn) == {
            "data_table": {
                "high_from_data": 5,
                "high_from_storage": 5,
            },
            "few_tx_wallets": {
                "low_from_data": 4,
                "low_from_storage": 2,
            },
        }
        service_tables = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name LIKE 'service_%';
            """
        ).fetchall()
        assert service_tables == []
    finally:
        conn.close()
