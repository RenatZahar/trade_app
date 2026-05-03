import asyncio
import sqlite3

import pytest

from modules.blockchain_parser import async_parser_functions as apf
from settings.parser import MIN_VALUE_THRESHOLD


def test_amount_and_coinbase_filter_keeps_only_non_coinbase_txs_above_threshold():
    txs = [
        {
            "txid": "coinbase_tx",
            "vin": [{"coinbase": "abcd"}],
            "vout": [{"value": MIN_VALUE_THRESHOLD * 10}],
        },
        {
            "txid": "small_tx",
            "vin": [{"txid": "prev", "vout": 0}],
            "vout": [{"value": MIN_VALUE_THRESHOLD / 10}],
        },
        {
            "txid": "normal_tx",
            "vin": [{"txid": "prev", "vout": 1}],
            "vout": [{"value": MIN_VALUE_THRESHOLD}],
        },
    ]

    filtered_txs = asyncio.run(apf.amount_and_counbase_filter(txs))

    assert [tx["txid"] for tx in filtered_txs] == ["normal_tx"]


def test_records_to_df_preserves_distinct_rows_with_same_transaction_id():
    records = [
        ["tx_1", "wallet_a", 1.0, 100.0, 1000, 10, "hash_10", 0],
        ["tx_1", "wallet_a", 2.0, 100.0, 1000, 10, "hash_10", 0],
        ["tx_1", "wallet_b", -3.0, 100.0, 1000, 10, "hash_10", 1],
    ]

    df = apf.records_to_df(records)

    assert len(df) == 2
    assert list(df.columns) == [
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

    wallet_a_row = df.loc[df["Wallet_id"] == "wallet_a"].iloc[0]
    wallet_b_row = df.loc[df["Wallet_id"] == "wallet_b"].iloc[0]

    assert wallet_a_row["Transaction_id"] == "tx_1"
    assert wallet_a_row["Amount"] == 3.0
    assert wallet_a_row["Transactions_Count"] == 2

    assert wallet_b_row["Transaction_id"] == "tx_1"
    assert wallet_b_row["Amount"] == -3.0
    assert wallet_b_row["Transactions_Count"] == 1


def test_async_save_data_to_db_does_not_treat_transaction_id_as_unique_row_id(tmp_path):
    db_path = tmp_path / "parser.sqlite"
    df = apf.records_to_df(
        [
            ["tx_1", "wallet_a", 1.0, 100.0, 1000, 10, "hash_10", 0],
            ["tx_1", "wallet_b", -1.0, 100.0, 1000, 10, "hash_10", 1],
        ]
    )

    asyncio.run(apf.async_save_data_to_db(df, str(db_path)))

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT Transaction_id, Wallet_id, n, Amount
            FROM data_table
            ORDER BY Wallet_id, n;
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("tx_1", "wallet_a", 0, 1.0),
        ("tx_1", "wallet_b", 1, -1.0),
    ]


def test_save_to_cache_skips_tx_cache_when_limit_is_zero(monkeypatch):
    monkeypatch.setattr(apf, "MAX_LINES_IN_TX_CACHE", 100000)
    monkeypatch.setattr(apf, "MAX_LINES_IN_HASH_CACHE", 0)
    apf.tx_cache.clear()
    apf.blocks_hash_cache.clear()

    apf.configure_cache_limits(tx_cache_lines=0)
    asyncio.run(
        apf.save_to_cache(
            [
                {
                    "txid": "tx_1",
                    "vin": [{"txid": "prev", "vout": 0}],
                    "vout": [{"n": 0, "scriptPubKey": {"address": "wallet"}}],
                }
            ],
            "tx_cache",
        )
    )

    assert apf.get_cache_metadata()["tx_cache_enabled"] is False
    assert len(apf.tx_cache) == 0


def test_extract_json_rpc_results_fails_on_batch_item_error():
    with pytest.raises(RuntimeError, match="JSON-RPC batch вернул ошибки"):
        apf.extract_json_rpc_results(
            [
                {"id": 0, "result": {"txid": "ok"}},
                {"id": 1, "error": {"code": -5, "message": "No such mempool transaction"}},
            ],
            expected_count=2,
        )


def test_extract_json_rpc_results_fails_on_partial_batch_response():
    with pytest.raises(RuntimeError, match="неполный ответ"):
        apf.extract_json_rpc_results(
            [{"id": 0, "result": {"txid": "ok"}}],
            expected_count=2,
        )


def test_extract_json_rpc_results_returns_ordered_results():
    results = apf.extract_json_rpc_results(
        [
            {"id": 0, "result": {"txid": "a"}},
            {"id": 1, "result": {"txid": "b"}},
        ],
        expected_count=2,
    )

    assert results == [{"txid": "a"}, {"txid": "b"}]
