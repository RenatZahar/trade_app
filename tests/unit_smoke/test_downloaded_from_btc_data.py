import pandas as pd

from tests.integration_live import test_downloaded_from_btc_data as downloaded_btc


def _compare_row(block_height: int) -> dict:
    return {
        "Transaction_id": f"tx_{block_height}",
        "Wallet_id": "wallet",
        "Btc_block_time_price": 100.0,
        "Block_time": 1000,
        "Block_height": block_height,
        "Block_hash": f"hash_{block_height}",
        "n": 0,
        "Amount": 1.0,
        "Transactions_Count": 1,
    }


def test_downloaded_from_btc_test_accepts_explicit_blocks_without_full_sql_scan(monkeypatch):
    requested_by_sql = []
    compare_data = pd.DataFrame(
        [
            _compare_row(873754),
            _compare_row(873755),
        ]
    )

    monkeypatch.setattr(downloaded_btc, "ensure_bitcoin_core_ready_for_test", lambda: None)
    monkeypatch.setattr(
        downloaded_btc,
        "get_existing_block_heights_from_sql",
        lambda: (_ for _ in ()).throw(AssertionError("full SQL block scan is not needed")),
    )
    monkeypatch.setattr(
        downloaded_btc,
        "get_existing_requested_block_heights_from_sql",
        lambda blocks: list(blocks),
    )
    monkeypatch.setattr(
        downloaded_btc,
        "get_sql_data_for_blocks",
        lambda blocks: requested_by_sql.append(list(blocks)) or compare_data.copy(),
    )
    monkeypatch.setattr(
        downloaded_btc,
        "get_chain_data_for_blocks",
        lambda _blocks: downloaded_btc.canonicalize_sql_data_for_compare(compare_data.copy()),
    )
    monkeypatch.setattr(downloaded_btc, "save_compare_artifacts", lambda *_args: {})

    summary = downloaded_btc.run_downloaded_from_btc_data_test(
        requested_blocks=[873754, 873755, 873754],
    )

    assert requested_by_sql == [[873754, 873755]]
    assert summary["selection_mode"] == "explicit_blocks"
    assert summary["requested_blocks"] == [873754, 873755]
    assert summary["comparison_status"] == "all_blocks_identical"
