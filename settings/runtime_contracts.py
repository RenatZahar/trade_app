"""Runtime dependency contracts shared by scenarios and config validation."""

REQUIRED_ENV_BY_DEPENDENCY = {
    "bitcoin_rpc": (
        "RPC_USER",
        "RPC_PASSWORD",
        "RPC_HOST",
        "RPC_PORT",
    ),
    "bitcoin_core": (
        "RPC_USER",
        "RPC_PASSWORD",
        "RPC_HOST",
        "RPC_PORT",
        "BITCOIN_CORE_PROCESS_NAME",
        "BITCOIN_CORE_PATH",
        "DATA_BLOCKCHAIN_DIR",
    ),
    "redis": (
        "REDIS_PROCESS_NAME",
    ),
    "flask_app": (),
    "blocks_sql_data": (),
}


SCENARIO_RUNTIME_DEPENDENCIES = {
    "main_pipeline": ("blocks_sql_data", "flask_app"),
    "param_grid": ("blocks_sql_data",),
    "start_parser": ("blocks_sql_data", "redis", "bitcoin_core"),
    "integration_live.downloaded_from_btc_data": ("blocks_sql_data", "bitcoin_rpc"),
}


CLI_SCENARIO_TO_RUNTIME_SCENARIO = {
    "--start_parser": "start_parser",
    "main-pipeline": "main_pipeline",
    "param-grid": "param_grid",
    "test downloaded-from-btc-data": "integration_live.downloaded_from_btc_data",
}
