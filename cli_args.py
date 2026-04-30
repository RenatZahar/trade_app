import argparse


EPILOG = (
    "Runtime commands:\n"
    "  main-pipeline - Flask + updater + peaks + train a new model\n"
    "  param-grid    - запуск подбора параметров\n"
    "\n"
    "Integration live tests:\n"
    "  test downloaded-from-btc-data <blocks_count> [seed] - сравнение SQL-данных с повторной реконструкцией из BTC RPC\n"
)


def validate_cli_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    active_top_level_modes = [
        args.start_parser,
        args.command is not None,
    ]
    if sum(active_top_level_modes) == 0:
        parser.error("Choose one scenario: --start_parser or a runtime command")
    if sum(active_top_level_modes) > 1:
        parser.error("Use only one top-level scenario at a time")

    if args.command == "test" and args.data_test == "downloaded-from-btc-data":
        if args.blocks_count is None:
            parser.error("blocks_count is required for downloaded-from-btc-data")
        if args.blocks_count <= 0:
            parser.error("blocks_count must be greater than 0")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified entrypoint for trade_app",
        epilog=EPILOG,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("-p", "--start_parser", action="store_true", help="Старт парсера блокчейна")

    scenario_subparsers = parser.add_subparsers(dest="command")

    main_pipeline_parser = scenario_subparsers.add_parser(
        "main-pipeline",
        help="Запустить price updater, подготовку peaks и обучение новой модели",
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
        help="Сколько случайных блоков проверить",
    )
    downloaded_btc_parser.add_argument(
        "seed",
        type=int,
        nargs="?",
        help="Опциональный seed для воспроизводимой выборки",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_cli_args(parser, args)
    return args
