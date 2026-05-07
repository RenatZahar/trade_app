import sqlite3

import pytest

from modules.teach_and_update_models import wallet_stats_operations as wso


def _create_data_table(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE data_table (
                Wallet_id TEXT,
                Block_height INTEGER,
                Block_time INTEGER,
                Amount REAL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO data_table (Wallet_id, Block_height, Block_time, Amount)
            VALUES (?, ?, ?, ?);
            """,
            [
                ("wallet_a", 1, 100, 1.0),
                ("wallet_b", 2, 200, 2.0),
                ("wallet_a", 3, 300, -3.0),
                ("wallet_b", 4, 400, -4.0),
                ("wallet_c", 10, 1000, 5.0),
            ],
        )
        conn.execute(
            "CREATE INDEX idx_wallet_id_block_height ON data_table (Wallet_id, Block_height);"
        )
        conn.commit()


def _drop_wallet_stats_index(db_path):
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP INDEX idx_wallet_id_block_height;")
        conn.commit()


def test_rebuild_wallet_stats_populates_derived_stats_in_chunks(tmp_path):
    db_path = tmp_path / "blocks.sqlite"
    _create_data_table(db_path)

    result = wso.rebuild_wallet_stats(
        db_path,
        target_until_block=4,
        block_chunk_size=2,
    )

    assert result == {
        "target_until_block": 4,
        "stats_until_block": 4,
        "processed_wallet_groups": 4,
    }

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT Wallet_id, total_tx_count, first_block_height, last_block_height,
                   total_abs_amount, updated_until_block
            FROM wallet_stats
            ORDER BY Wallet_id;
            """
        ).fetchall()
        service_rows = dict(
            conn.execute(
                "SELECT key, value FROM wallet_stats_service_data;"
            ).fetchall()
        )

    assert rows == [
        ("wallet_a", 2, 1, 3, 4.0, 4),
        ("wallet_b", 2, 2, 4, 6.0, 4),
    ]
    assert service_rows[wso.SERVICE_KEY_STATS_UNTIL_BLOCK] == "4"
    assert service_rows[wso.SERVICE_KEY_LAST_REBUILD_STATUS] == wso.REBUILD_STATUS_SUCCESS


def test_validate_wallet_stats_ready_rejects_stale_stats(tmp_path):
    db_path = tmp_path / "blocks.sqlite"
    _create_data_table(db_path)
    wso.rebuild_wallet_stats(
        db_path,
        target_until_block=4,
        allowed_lag_blocks=0,
    )

    with pytest.raises(RuntimeError, match="wallet_stats is stale"):
        wso.validate_wallet_stats_ready(db_path)


def test_get_candidate_wallets_for_training_window_uses_train_window_overlap(tmp_path):
    db_path = tmp_path / "blocks.sqlite"
    _create_data_table(db_path)
    wso.rebuild_wallet_stats(db_path, target_until_block=10)

    candidates = wso.get_candidate_wallets_for_training_window(
        db_path,
        min_tx_count=1,
        teaching_start_block=2,
        teaching_end_block=4,
    )

    assert candidates == ["wallet_a", "wallet_b"]


def test_validate_wallet_stats_ready_requires_schema(tmp_path):
    db_path = tmp_path / "blocks.sqlite"
    _create_data_table(db_path)

    with pytest.raises(RuntimeError, match="wallet_stats table is required"):
        wso.validate_wallet_stats_ready(db_path)


def test_validate_wallet_stats_ready_requires_wallet_block_index(tmp_path):
    db_path = tmp_path / "blocks.sqlite"
    _create_data_table(db_path)
    wso.rebuild_wallet_stats(db_path, target_until_block=10)
    _drop_wallet_stats_index(db_path)

    with pytest.raises(RuntimeError, match="idx_wallet_id_block_height"):
        wso.validate_wallet_stats_ready(db_path)
