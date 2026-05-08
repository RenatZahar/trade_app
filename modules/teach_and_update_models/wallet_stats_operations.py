"""Wallet statistics storage and wallet-stats collector helpers.

Responsibility:
- own the `wallet_stats` and `wallet_stats_service_data` derived-cache schema;
- provide preflight checks that decide whether `wallet_stats` can be trusted;
- provide resumable wallet stats rebuild helpers;
- select candidate wallets for the wallet-stats collector.

Non-responsibility:
- do not mutate raw transaction rows in `data_table`;
- do not decide which collector is active;
- do not replace dataframe feature/correlation logic outside the collector path.
"""

from __future__ import annotations

from datetime import datetime
import gc
import logging
from pathlib import Path
import sqlite3

from .determinism import sample_fraction
from settings.db_contracts import WALLET_STATS_REQUIRED_DATA_TABLE_INDEXES
from settings.paths import BLOCKS_SQL_DATA


logger = logging.getLogger("app")

WALLET_STATS_TABLE = "wallet_stats"
WALLET_STATS_SERVICE_TABLE = "wallet_stats_service_data"

DEFAULT_ALLOWED_LAG_BLOCKS = 26_000
DEFAULT_ALLOWED_LAG_COMMENT = (
    "Temporarily large lag while blockchain backfill is still running."
)

SERVICE_KEY_STATS_UNTIL_BLOCK = "stats_until_block"
SERVICE_KEY_ALLOWED_LAG_BLOCKS = "allowed_lag_blocks"
SERVICE_KEY_LAST_REBUILD_STATUS = "last_rebuild_status"
SERVICE_KEY_LAST_REBUILD_ERROR = "last_rebuild_error"
SERVICE_KEY_TARGET_UNTIL_BLOCK = "target_until_block"

REBUILD_STATUS_RUNNING = "running"
REBUILD_STATUS_SUCCESS = "success"
REBUILD_STATUS_FAILED = "failed"


def _db_path(db_path):
    return str(db_path) if isinstance(db_path, Path) else db_path


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _quote(identifier):
    return '"{}"'.format(str(identifier).replace('"', '""'))


def _table_exists(conn, table_name):
    cursor = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type='table'
          AND name=?;
        """,
        (table_name,),
    )
    return cursor.fetchone() is not None


def _data_table_indexes(conn):
    cursor = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='index'
          AND tbl_name='data_table';
        """
    )
    return {row[0] for row in cursor.fetchall()}


def _service_get(conn, key):
    cursor = conn.execute(
        f"SELECT value FROM {_quote(WALLET_STATS_SERVICE_TABLE)} WHERE key=?;",
        (key,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _service_set(conn, key, value, comment=None):
    conn.execute(
        f"""
        INSERT INTO {_quote(WALLET_STATS_SERVICE_TABLE)} (key, value, comment, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            value=excluded.value,
            comment=COALESCE(excluded.comment, {_quote(WALLET_STATS_SERVICE_TABLE)}.comment),
            updated_at=excluded.updated_at;
        """,
        (key, str(value), comment, _now()),
    )


def _service_get_int(conn, key):
    value = _service_get(conn, key)
    return int(value) if value not in (None, "") else None


def ensure_wallet_stats_schema(
    db_path=BLOCKS_SQL_DATA,
    *,
    allowed_lag_blocks=DEFAULT_ALLOWED_LAG_BLOCKS,
    allowed_lag_comment=DEFAULT_ALLOWED_LAG_COMMENT,
):
    """Create derived-cache tables/indexes without touching `data_table` rows."""

    with sqlite3.connect(_db_path(db_path)) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote(WALLET_STATS_TABLE)} (
                Wallet_id TEXT PRIMARY KEY,
                total_tx_count INTEGER,
                first_block_height INTEGER,
                last_block_height INTEGER,
                total_abs_amount REAL,
                updated_until_block INTEGER,
                updated_at TEXT
            );
            """
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_wallet_stats_activity
            ON {_quote(WALLET_STATS_TABLE)}
            (total_tx_count, last_block_height, first_block_height);
            """
        )
        conn.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_wallet_stats_updated_until_block
            ON {_quote(WALLET_STATS_TABLE)} (updated_until_block);
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_quote(WALLET_STATS_SERVICE_TABLE)} (
                key TEXT PRIMARY KEY,
                value TEXT,
                comment TEXT,
                updated_at TEXT
            );
            """
        )
        if _service_get(conn, SERVICE_KEY_ALLOWED_LAG_BLOCKS) is None:
            _service_set(
                conn,
                SERVICE_KEY_ALLOWED_LAG_BLOCKS,
                allowed_lag_blocks,
                allowed_lag_comment,
            )
        conn.commit()


def get_data_table_block_range(db_path=BLOCKS_SQL_DATA, table_name="data_table"):
    with sqlite3.connect(_db_path(db_path)) as conn:
        cursor = conn.execute(
            f"SELECT MIN(Block_height), MAX(Block_height) FROM {_quote(table_name)};"
        )
        row = cursor.fetchone()
    if not row or row[0] is None or row[1] is None:
        return None, None
    return int(row[0]), int(row[1])


def get_wallet_stats_service_state(db_path=BLOCKS_SQL_DATA):
    with sqlite3.connect(_db_path(db_path)) as conn:
        if not _table_exists(conn, WALLET_STATS_SERVICE_TABLE):
            return {}
        cursor = conn.execute(
            f"SELECT key, value, comment, updated_at FROM {_quote(WALLET_STATS_SERVICE_TABLE)};"
        )
        return {
            key: {
                "value": value,
                "comment": comment,
                "updated_at": updated_at,
            }
            for key, value, comment, updated_at in cursor.fetchall()
        }


def validate_wallet_stats_ready(db_path=BLOCKS_SQL_DATA):
    with sqlite3.connect(_db_path(db_path)) as conn:
        for table_name in (WALLET_STATS_TABLE, WALLET_STATS_SERVICE_TABLE):
            if not _table_exists(conn, table_name):
                raise RuntimeError(
                    f"{table_name} table is required for wallet-stats collector."
                )
        missing_indexes = sorted(
            WALLET_STATS_REQUIRED_DATA_TABLE_INDEXES - _data_table_indexes(conn)
        )
        if missing_indexes:
            raise RuntimeError(
                "wallet-stats collector requires data_table indexes: "
                + ", ".join(missing_indexes)
            )

        _, current_max_block = get_data_table_block_range(db_path)
        if current_max_block is None:
            raise RuntimeError("data_table has no blocks for wallet-stats validation.")

        stats_until_block = _service_get_int(conn, SERVICE_KEY_STATS_UNTIL_BLOCK)
        allowed_lag_blocks = _service_get_int(conn, SERVICE_KEY_ALLOWED_LAG_BLOCKS)
        last_rebuild_status = _service_get(conn, SERVICE_KEY_LAST_REBUILD_STATUS)

    if stats_until_block is None:
        raise RuntimeError("wallet_stats has no stats_until_block service value.")
    if allowed_lag_blocks is None:
        raise RuntimeError("wallet_stats has no allowed_lag_blocks service value.")
    if last_rebuild_status != REBUILD_STATUS_SUCCESS:
        raise RuntimeError(
            "wallet_stats last rebuild is not successful: "
            f"{last_rebuild_status or 'missing'}"
        )

    lag_blocks = current_max_block - stats_until_block
    if lag_blocks > allowed_lag_blocks:
        raise RuntimeError(
            "wallet_stats is stale: "
            f"current_max_block={current_max_block} "
            f"stats_until_block={stats_until_block} "
            f"allowed_lag_blocks={allowed_lag_blocks}"
        )

    return {
        "current_max_block": current_max_block,
        "stats_until_block": stats_until_block,
        "allowed_lag_blocks": allowed_lag_blocks,
        "lag_blocks": lag_blocks,
        "last_rebuild_status": last_rebuild_status,
    }


def _calculate_stats_for_block_chunk(conn, start_block, end_block, table_name):
    cursor = conn.execute(
        f"""
        SELECT
            CAST(Wallet_id AS TEXT) AS Wallet_id,
            COUNT(*) AS total_tx_count,
            MIN(Block_height) AS first_block_height,
            MAX(Block_height) AS last_block_height,
            COALESCE(SUM(ABS(Amount)), 0) AS total_abs_amount
        FROM {_quote(table_name)}
        WHERE Block_height BETWEEN ? AND ?
          AND Wallet_id IS NOT NULL
        GROUP BY Wallet_id;
        """,
        (start_block, end_block),
    )
    return cursor.fetchall()


def rebuild_wallet_stats(
    db_path=BLOCKS_SQL_DATA,
    *,
    target_until_block=None,
    block_chunk_size=10_000,
    allowed_lag_blocks=DEFAULT_ALLOWED_LAG_BLOCKS,
    allowed_lag_comment=DEFAULT_ALLOWED_LAG_COMMENT,
    table_name="data_table",
):
    """Incrementally rebuild wallet stats by non-overlapping block chunks.

    The function mutates only derived `wallet_stats*` tables. It does not update,
    delete, or insert raw rows in `data_table`.
    """

    ensure_wallet_stats_schema(
        db_path,
        allowed_lag_blocks=allowed_lag_blocks,
        allowed_lag_comment=allowed_lag_comment,
    )
    min_block, current_max_block = get_data_table_block_range(db_path, table_name=table_name)
    if current_max_block is None:
        raise RuntimeError("data_table has no blocks for wallet_stats rebuild.")
    target_until_block = int(target_until_block or current_max_block)
    if min_block is None or target_until_block < min_block:
        raise RuntimeError(
            f"Invalid wallet_stats target block: {target_until_block}"
        )

    processed_wallet_groups = 0
    try:
        with sqlite3.connect(_db_path(db_path)) as conn:
            stats_until_block = _service_get_int(conn, SERVICE_KEY_STATS_UNTIL_BLOCK)
            last_status = _service_get(conn, SERVICE_KEY_LAST_REBUILD_STATUS)
            can_resume = (
                stats_until_block is not None
                and last_status in {REBUILD_STATUS_SUCCESS, REBUILD_STATUS_RUNNING}
            )
            if can_resume:
                logger.info(
                    "wallet_stats rebuild resume: status=%s stats_until_block=%s "
                    "target_until_block=%s block_chunk_size=%s",
                    last_status,
                    stats_until_block,
                    target_until_block,
                    block_chunk_size,
                )
            else:
                logger.info(
                    "wallet_stats rebuild reset: status=%s stats_until_block=%s "
                    "target_until_block=%s block_chunk_size=%s",
                    last_status,
                    stats_until_block,
                    target_until_block,
                    block_chunk_size,
                )
                conn.execute(f"DELETE FROM {_quote(WALLET_STATS_TABLE)};")
                stats_until_block = min_block - 1

            _service_set(conn, SERVICE_KEY_LAST_REBUILD_STATUS, REBUILD_STATUS_RUNNING)
            _service_set(conn, SERVICE_KEY_TARGET_UNTIL_BLOCK, target_until_block)
            _service_set(
                conn,
                SERVICE_KEY_ALLOWED_LAG_BLOCKS,
                allowed_lag_blocks,
                allowed_lag_comment,
            )
            conn.commit()

            next_block = max(stats_until_block + 1, min_block)
            while next_block <= target_until_block:
                end_block = min(next_block + block_chunk_size - 1, target_until_block)
                rows = _calculate_stats_for_block_chunk(
                    conn,
                    next_block,
                    end_block,
                    table_name,
                )
                conn.executemany(
                    f"""
                    INSERT INTO {_quote(WALLET_STATS_TABLE)} (
                        Wallet_id,
                        total_tx_count,
                        first_block_height,
                        last_block_height,
                        total_abs_amount,
                        updated_until_block,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(Wallet_id) DO UPDATE SET
                        total_tx_count=COALESCE({_quote(WALLET_STATS_TABLE)}.total_tx_count, 0)
                            + excluded.total_tx_count,
                        first_block_height=MIN(
                            COALESCE({_quote(WALLET_STATS_TABLE)}.first_block_height, excluded.first_block_height),
                            excluded.first_block_height
                        ),
                        last_block_height=MAX(
                            COALESCE({_quote(WALLET_STATS_TABLE)}.last_block_height, excluded.last_block_height),
                            excluded.last_block_height
                        ),
                        total_abs_amount=COALESCE({_quote(WALLET_STATS_TABLE)}.total_abs_amount, 0)
                            + excluded.total_abs_amount,
                        updated_until_block=excluded.updated_until_block,
                        updated_at=excluded.updated_at;
                    """,
                    [
                        (
                            wallet_id,
                            total_tx_count,
                            first_block_height,
                            last_block_height,
                            total_abs_amount,
                            end_block,
                            _now(),
                        )
                        for (
                            wallet_id,
                            total_tx_count,
                            first_block_height,
                            last_block_height,
                            total_abs_amount,
                        ) in rows
                    ],
                )
                _service_set(conn, SERVICE_KEY_STATS_UNTIL_BLOCK, end_block)
                conn.commit()
                processed_wallet_groups += len(rows)
                next_block = end_block + 1

            final_stats_until_block = max(stats_until_block, target_until_block)
            _service_set(conn, SERVICE_KEY_LAST_REBUILD_STATUS, REBUILD_STATUS_SUCCESS)
            _service_set(conn, SERVICE_KEY_LAST_REBUILD_ERROR, "")
            conn.commit()
    except Exception as exc:
        with sqlite3.connect(_db_path(db_path)) as conn:
            _service_set(conn, SERVICE_KEY_LAST_REBUILD_STATUS, REBUILD_STATUS_FAILED)
            _service_set(conn, SERVICE_KEY_LAST_REBUILD_ERROR, str(exc))
            conn.commit()
        raise

    return {
        "target_until_block": target_until_block,
        "stats_until_block": final_stats_until_block,
        "processed_wallet_groups": processed_wallet_groups,
    }


def get_candidate_wallets_for_training_window(
    db_path,
    *,
    min_tx_count,
    teaching_start_block,
    teaching_end_block,
):
    min_tx_count = int(min_tx_count or 0)
    with sqlite3.connect(_db_path(db_path)) as conn:
        cursor = conn.execute(
            f"""
            SELECT Wallet_id
            FROM {_quote(WALLET_STATS_TABLE)}
            WHERE total_tx_count > ?
              AND last_block_height >= ?
              AND first_block_height <= ?
            ORDER BY Wallet_id;
            """,
            (min_tx_count, teaching_start_block, teaching_end_block),
        )
        return [row[0] for row in cursor.fetchall()]


def _require_block_height(value, name):
    if value is None:
        raise RuntimeError(f"Could not resolve {name} for wallet-stats collector.")
    return int(value)


def collect_correlation_training_data_with_wallet_stats(
    request,
    *,
    db_path=BLOCKS_SQL_DATA,
):
    from . import data_operations as do

    readiness = validate_wallet_stats_ready(db_path)
    tmps = request.time_window
    teaching_start_block = _require_block_height(
        do.get_blocks_by_tmsp([tmps["teaching_start_tmsp"]], direction="forward"),
        "teaching_start_block",
    )
    teaching_end_block = _require_block_height(
        do.get_blocks_by_tmsp([tmps["teaching_end_tmsp"]], direction="backward"),
        "teaching_end_block",
    )
    min_tx_count = request.filter_params.get("txs_count_of_wallets", 0)
    candidate_wallets = get_candidate_wallets_for_training_window(
        db_path,
        min_tx_count=min_tx_count,
        teaching_start_block=teaching_start_block,
        teaching_end_block=teaching_end_block,
    )
    if request.test_fraction:
        candidate_wallets = sample_fraction(
            candidate_wallets,
            request.test_fraction,
            seed=request.seed,
        )
    if not candidate_wallets:
        raise RuntimeError("wallet-stats collector found no candidate wallets.")

    chunks_list = do.get_chunks_of_wallets(candidate_wallets, request.chunk_size)
    if not chunks_list:
        raise RuntimeError("wallet-stats collector built no wallet chunks.")

    dask_client = do.get_dask_client()
    try:
        all_wallets_corelation_ddf, all_txs_of_wallets_ddf = (
            do.get_corelation_of_wallets_df_with_dask(
                dask_client,
                chunks_list,
                tmps,
                request.correlation_type,
                request.chunk_size,
                request.filter_params,
            )
        )
        all_wallets_corelation_ddf = all_wallets_corelation_ddf.persist()
        do.wait(all_wallets_corelation_ddf)
        do.wait(all_txs_of_wallets_ddf)

        train_df, profit_test_df = do.get_data_for_teach_with_dask(
            tmps,
            all_txs_of_wallets_ddf,
            all_wallets_corelation_ddf,
            request.correlation_type,
        )
    finally:
        do.close_dask_client(dask_client)
        gc.collect()

    train_df.reset_index(inplace=True)
    profit_test_df.reset_index(inplace=True)

    return train_df, profit_test_df, {
        "collector": "wallet-stats",
        "source": "wallet_stats",
        "candidate_wallets": len(candidate_wallets),
        "wallet_chunks": len(chunks_list),
        "teaching_start_block": teaching_start_block,
        "teaching_end_block": teaching_end_block,
        **readiness,
    }
