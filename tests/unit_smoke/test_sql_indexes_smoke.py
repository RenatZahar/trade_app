import sqlite3

from modules.sql_funcs.moving_txs import create_indexes


def test_create_indexes_creates_expected_data_table_indexes(tmp_path):
    db_path = tmp_path / "test.sqlite"

    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE data_table (
            Wallet_id INTEGER,
            Block_height INTEGER,
            Block_time INTEGER
        );
        """
    )
    conn.commit()
    conn.close()

    create_indexes(str(db_path))

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'index'
          AND tbl_name = 'data_table';
        """
    ).fetchall()
    conn.close()

    index_names = {row[0] for row in rows}

    assert "idx_wallet_id" in index_names
    assert "idx_block_height" in index_names
    assert "idx_txs_blocktime" in index_names
    assert "idx_block_height_wallet_id" in index_names
