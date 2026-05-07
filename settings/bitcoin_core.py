"""Bitcoin Core startup profiles owned by the application runtime."""

from pathlib import Path
import os

from settings.runtime import DATA_BLOCKCHAIN_DIR, rpc_password, rpc_port, rpc_user


BITCOIN_CORE_CONFIG_DIR_NAME = "trade_app_generated_configs"
BITCOIN_CORE_SHUTDOWN_TIMEOUT_SEC = int(
    os.getenv("BITCOIN_CORE_SHUTDOWN_TIMEOUT_SEC", "120")
)


BITCOIN_CORE_BASE_CONFIG = {
    "txindex": "1",
    "listen": "1",
    "dnsseed": "0",
    "maxconnections": "50",
    "upnp": "0",
    "natpmp": "0",
    "maxmempool": "5",
    "dbcache": os.getenv("BITCOIN_CORE_DBCACHE_MB", "300"),
    "par": "10",
    "blocksonly": "1",
    "server": "1",
    "rpcallowip": os.getenv("BITCOIN_CORE_RPC_ALLOW_IP", "127.0.0.1"),
    "rpcbind": os.getenv("BITCOIN_CORE_RPC_BIND", "127.0.0.1"),
    "rpcport": rpc_port,
    "rpcthreads": "16",
    "rpcworkqueue": "128",
    "zmqpubrawblock": os.getenv(
        "BITCOIN_CORE_ZMQ_RAW_BLOCK", "tcp://127.0.0.1:28334"
    ),
    "zmqpubrawtx": os.getenv("BITCOIN_CORE_ZMQ_RAW_TX", "tcp://127.0.0.1:28335"),
    "disablewallet": "1",
}


BITCOIN_CORE_PROFILE_OVERRIDES = {
    "standard": {},
    "background": {
        "listen": "0",
        "maxconnections": "8",
        "dbcache": os.getenv("BITCOIN_CORE_BACKGROUND_DBCACHE_MB", "128"),
        "par": "2",
        "rpcthreads": "4",
        "rpcworkqueue": "32",
    },
}


def normalize_bitcoin_core_profile(profile_name: str | None) -> str:
    profile = (profile_name or "standard").strip().lower()
    if profile not in BITCOIN_CORE_PROFILE_OVERRIDES:
        choices = ", ".join(sorted(BITCOIN_CORE_PROFILE_OVERRIDES))
        raise ValueError(f"Unknown Bitcoin Core profile: {profile_name}. Choices: {choices}")
    return profile


def get_bitcoin_core_profile_config(profile_name: str | None) -> dict[str, str]:
    profile = normalize_bitcoin_core_profile(profile_name)
    config = {
        key: value
        for key, value in BITCOIN_CORE_BASE_CONFIG.items()
        if value is not None and str(value).strip()
    }
    config.update(BITCOIN_CORE_PROFILE_OVERRIDES[profile])

    if not rpc_user or not str(rpc_user).strip():
        raise ValueError("RPC_USER is required to generate Bitcoin Core config")
    if not rpc_password or not str(rpc_password).strip():
        raise ValueError("RPC_PASSWORD is required to generate Bitcoin Core config")

    config["rpcuser"] = str(rpc_user)
    config["rpcpassword"] = str(rpc_password)
    return config


def get_bitcoin_core_config_path(
    profile_name: str | None,
    data_blockchain_dir: str | Path | None = None,
) -> Path:
    profile = normalize_bitcoin_core_profile(profile_name)
    data_dir = Path(data_blockchain_dir or DATA_BLOCKCHAIN_DIR).expanduser()
    return data_dir / BITCOIN_CORE_CONFIG_DIR_NAME / f"bitcoin-{profile}.conf"


def render_bitcoin_core_config(profile_name: str | None) -> str:
    config = get_bitcoin_core_profile_config(profile_name)
    return "\n".join(f"{key}={value}" for key, value in config.items()) + "\n"


def validate_existing_blockchain_datadir(data_blockchain_dir: str | Path | None = None) -> Path:
    if not data_blockchain_dir:
        raise ValueError("DATA_BLOCKCHAIN_DIR is required before starting Bitcoin Core")

    data_dir = Path(data_blockchain_dir).expanduser().resolve()
    if not data_dir.exists():
        raise ValueError(f"Bitcoin datadir does not exist: {data_dir}")
    if not data_dir.is_dir():
        raise ValueError(f"Bitcoin datadir is not a directory: {data_dir}")

    blocks_dir = data_dir / "blocks"
    chainstate_dir = data_dir / "chainstate"
    if not blocks_dir.is_dir() or not chainstate_dir.is_dir():
        raise ValueError(
            "Bitcoin datadir must already contain blocks/ and chainstate/ "
            f"to avoid starting a fresh blockchain sync: {data_dir}"
        )
    if next(blocks_dir.glob("blk*.dat"), None) is None:
        raise ValueError(
            "Bitcoin datadir blocks/ does not contain blk*.dat files; "
            f"refusing to start against possible empty datadir: {data_dir}"
        )
    return data_dir


def write_bitcoin_core_config(
    profile_name: str | None,
    data_blockchain_dir: str | Path | None = None,
) -> Path:
    data_dir = validate_existing_blockchain_datadir(data_blockchain_dir or DATA_BLOCKCHAIN_DIR)
    config_path = get_bitcoin_core_config_path(profile_name, data_dir)
    config_path.parent.mkdir(parents=True, exist_ok=True)

    config_path.write_text(render_bitcoin_core_config(profile_name), encoding="utf-8")
    return config_path
