# Константы и настройки
QUANTITY_OF_BLOCKS_IN_ITERATION = 40
MAX_ITERATIONS = 10000
REQUESTS_QUANTITY = 800
ASYNC_RPC_BATCH_SIZE = 2000
MAX_CONCURRENT_BLOCK_TASKS = 4
MIN_VALUE_THRESHOLD = 0.01
MAX_LINES_IN_TX_CACHE = 200000
MAX_LINES_IN_HASH_CACHE = 0
START_BLOCK = 770000
MAX_SAVE_TASKS = 1

# Список проблемных блоков, если есть
PROBLEM_BLOCKS_LIST = 0


PARSER_RUNTIME_PROFILES = {
    "standard": {
        "quantity_of_blocks_in_iteration": QUANTITY_OF_BLOCKS_IN_ITERATION,
        "requests_quantity": REQUESTS_QUANTITY,
        "async_rpc_batch_size": ASYNC_RPC_BATCH_SIZE,
        "max_concurrent_block_tasks": MAX_CONCURRENT_BLOCK_TASKS,
        "max_save_tasks": MAX_SAVE_TASKS,
        "group_pause_seconds": 0,
        "tx_cache_lines": MAX_LINES_IN_TX_CACHE,
        "hash_cache_lines": MAX_LINES_IN_HASH_CACHE,
    },

    "background": {
        "quantity_of_blocks_in_iteration": 4,
        "requests_quantity": 100,
        "async_rpc_batch_size": 300,
        "max_concurrent_block_tasks": 1,
        "max_save_tasks": 1,
        "group_pause_seconds": 5,
        "tx_cache_lines": 20000,
        "hash_cache_lines": MAX_LINES_IN_HASH_CACHE,
    },
}


def normalize_parser_runtime_profile(profile_name):
    profile = (profile_name or "standard").strip().lower()
    if profile not in PARSER_RUNTIME_PROFILES:
        choices = ", ".join(sorted(PARSER_RUNTIME_PROFILES))
        raise ValueError(f"Unknown parser runtime profile: {profile_name}. Choices: {choices}")
    return profile


def get_parser_runtime_profile(profile_name):
    profile = normalize_parser_runtime_profile(profile_name)
    return dict(PARSER_RUNTIME_PROFILES[profile])
