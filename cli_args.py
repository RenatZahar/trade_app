import argparse
import re


EPILOG = (
    "Runtime commands:\n"
    "  main-pipeline - Flask + updater + peaks + train a new model\n"
    "  param-grid    - запуск подбора параметров\n"
    "\n"
    "Parser scenarios:\n"
    "  --start_parser            - штатный parser run: managed standard Bitcoin Core config,\n"
    "                              legacy parser throughput settings\n"
    "  --start_parser_background - тихий parser run: managed Bitcoin Core config,\n"
    "                              lower parser/RPC/save concurrency, resume-only DB guard\n"
    "\n"
    "Integration live tests:\n"
    "  test downloaded-from-btc-data <blocks_count> [seed] - сравнение случайной выборки SQL-данных с BTC RPC\n"
    "  test downloaded-from-btc-data --blocks 873754,873755 - сравнение конкретных блоков\n"
)


def parse_blocks_arg(raw_blocks: list[str] | None) -> list[int] | None:
    if raw_blocks is None:
        return None

    raw_value = " ".join(raw_blocks).strip()
    if raw_value.startswith("blocks"):
        raw_value = raw_value[len("blocks"):]
    raw_value = raw_value.strip().strip("[]()")

    block_values = [value for value in re.split(r"[\s,]+", raw_value) if value]
    if not block_values:
        raise ValueError("--blocks must contain at least one block height")

    blocks = []
    for value in block_values:
        try:
            block_height = int(value)
        except ValueError as exc:
            raise ValueError(f"Invalid block height in --blocks: {value}") from exc
        if block_height <= 0:
            raise ValueError("Block heights in --blocks must be greater than 0")
        blocks.append(block_height)

    return blocks


def validate_cli_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    active_top_level_modes = [
        args.start_parser,
        args.start_parser_background,
        args.command is not None,
    ]
    if sum(active_top_level_modes) == 0:
        parser.error(
            "Choose one scenario: --start_parser, --start_parser_background, "
            "or a runtime command"
        )
    if sum(active_top_level_modes) > 1:
        parser.error("Use only one top-level scenario at a time")

    parser_cache_overrides = [
        args.parser_tx_cache_lines,
        args.parser_hash_cache_lines,
    ]
    parser_mode_enabled = args.start_parser or args.start_parser_background
    if any(value is not None for value in parser_cache_overrides) and not parser_mode_enabled:
        parser.error(
            "Parser cache overrides can only be used with --start_parser "
            "or --start_parser_background"
        )
    if any(value is not None and value < 0 for value in parser_cache_overrides):
        parser.error("Parser cache limits must be greater than or equal to 0")

    if args.command == "param-grid":
        if args.test_fraction is not None and not 0 <= args.test_fraction <= 1:
            parser.error("--test-fraction must be between 0 and 1")

    if args.command == "test" and args.data_test == "downloaded-from-btc-data":
        try:
            args.blocks = parse_blocks_arg(args.blocks)
        except ValueError as exc:
            parser.error(str(exc))

        if args.blocks is not None and args.blocks_count is not None:
            parser.error("Use either blocks_count or --blocks, not both")
        if args.blocks is None and args.blocks_count is None:
            parser.error("blocks_count is required for downloaded-from-btc-data")
        if args.blocks_count is not None and args.blocks_count <= 0:
            parser.error("blocks_count must be greater than 0")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified entrypoint for trade_app",
        epilog=EPILOG,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-p",
        "--start_parser",
        action="store_true",
        help="Старт парсера блокчейна со standard managed Bitcoin Core config",
    )
    parser.add_argument(
        "--start_parser_background",
        action="store_true",
        help="Старт парсера с тихим профилем и перезапуском Bitcoin Core под managed config",
    )
    parser.add_argument(
        "--parser-tx-cache-lines",
        type=int,
        help="Переопределить лимит tx_cache для парсера; 0 отключает tx_cache",
    )
    parser.add_argument(
        "--parser-hash-cache-lines",
        type=int,
        help="Переопределить лимит blocks_hash_cache для парсера; 0 отключает blocks_hash_cache",
    )

    scenario_subparsers = parser.add_subparsers(dest="command")

    main_pipeline_parser = scenario_subparsers.add_parser(
        "main-pipeline",
        help="Запустить price updater, подготовку peaks и обучение новой модели",
    )
    main_pipeline_parser.add_argument(
        "--collector",
        choices=("legacy", "wallet-stats"),
        default="legacy",
        help="Метод сбора train/profit данных для main-pipeline",
    )

    param_grid_parser = scenario_subparsers.add_parser(
        "param-grid",
        help="Запустить подбор параметров модели",
    )
    param_grid_parser.add_argument(
        "--test-fraction",
        type=float,
        default=0,
        help="Доля grid/data для тестового прогона; 0 означает полный grid",
    )
    param_grid_parser.add_argument(
        "--seed",
        type=int,
        help="Опциональный seed для воспроизводимого test-fraction среза",
    )

    test_parser = scenario_subparsers.add_parser(
        "test",
        help="Запуск тестовых сценариев",
    )

    test_subparsers = test_parser.add_subparsers(
        dest="data_test",
        required=True,
        title="available tests",
    )
    downloaded_btc_parser = test_subparsers.add_parser(
        "downloaded-from-btc-data",
        help="Сравнение SQL-данных с реконструкцией из BTC RPC",
    )
    downloaded_btc_parser.add_argument(
        "blocks_count",
        type=int,
        nargs="?",
        help="Сколько случайных блоков проверить",
    )
    downloaded_btc_parser.add_argument(
        "seed",
        type=int,
        nargs="?",
        help="Опциональный seed для воспроизводимой выборки",
    )
    downloaded_btc_parser.add_argument(
        "--blocks",
        nargs="+",
        help="Конкретные блоки для проверки: 873754 или 873754,873755",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_cli_args(parser, args)
    return args
