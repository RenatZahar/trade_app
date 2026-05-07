"""SQLite schema contracts shared by runtime checks and smoke tests."""

DB_TABLE_CONTRACTS = {
    "data_table": {
        "required": True,
        "columns": (
            "Wallet_id",
            "Block_height",
            "Block_time",
        ),
        "indexes": (
            "idx_wallet_id",
            "idx_block_height",
            "idx_txs_blocktime",
            "idx_block_height_wallet_id",
        ),
    },
    "wallet_stats": {
        "required": False,
        "columns": (
            "Wallet_id",
            "total_tx_count",
            "first_block_height",
            "last_block_height",
            "total_abs_amount",
            "updated_until_block",
            "updated_at",
        ),
        "indexes": (
            "idx_wallet_stats_activity",
            "idx_wallet_stats_updated_until_block",
        ),
    },
    "wallet_stats_service_data": {
        "required": False,
        "columns": (
            "key",
            "value",
            "comment",
            "updated_at",
        ),
        "indexes": (),
    },
}


SCENARIO_DB_TABLE_DEPENDENCIES = {
    "main_pipeline": ("data_table",),
    "param_grid": ("data_table",),
    "start_parser": ("data_table",),
    "start_parser_background": ("data_table",),
    "integration_live.downloaded_from_btc_data": ("data_table",),
}


REQUIRED_DB_TABLES = frozenset(
    table_name
    for table_name, contract in DB_TABLE_CONTRACTS.items()
    if contract.get("required")
)

REQUIRED_DATA_TABLE_INDEXES = frozenset(DB_TABLE_CONTRACTS["data_table"]["indexes"])

WALLET_STATS_REQUIRED_DATA_TABLE_INDEXES = frozenset(
    {
        "idx_wallet_id_block_height",
    }
)
