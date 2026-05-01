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
}


SCENARIO_DB_TABLE_DEPENDENCIES = {
    "main_pipeline": ("data_table",),
    "param_grid": ("data_table",),
    "start_parser": ("data_table",),
    "integration_live.downloaded_from_btc_data": ("data_table",),
}


REQUIRED_DB_TABLES = frozenset(
    table_name
    for table_name, contract in DB_TABLE_CONTRACTS.items()
    if contract.get("required")
)

REQUIRED_DATA_TABLE_INDEXES = frozenset(DB_TABLE_CONTRACTS["data_table"]["indexes"])
