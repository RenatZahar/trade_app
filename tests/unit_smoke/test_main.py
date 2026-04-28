import pytest

import main


def test_parse_args_accepts_start_parser_flag():
    args = main.parse_args(["--start_parser"])

    assert args.start_parser is True
    assert args.service is None
    assert getattr(args, "command", None) is None


def test_parse_args_accepts_service_mode():
    args = main.parse_args(["--service", "move_txs"])

    assert args.start_parser is False
    assert args.service == "move_txs"
    assert getattr(args, "command", None) is None


def test_parse_args_accepts_return_few_tx_wallets_service_mode():
    args = main.parse_args(["--service", "return_few_tx_wallets"])

    assert args.start_parser is False
    assert args.service == "return_few_tx_wallets"
    assert getattr(args, "command", None) is None


def test_parse_args_accepts_integration_test_mode_with_blocks_and_seed():
    args = main.parse_args(
        ["test", "downloaded-from-btc-data", "5", "13"]
    )

    assert args.command == "test"
    assert args.data_test == "downloaded-from-btc-data"
    assert args.blocks_count == 5
    assert args.seed == 13


def test_parse_args_requires_blocks_count_for_downloaded_btc_test():
    with pytest.raises(SystemExit):
        main.parse_args(["test", "downloaded-from-btc-data"])


def test_parse_args_rejects_blocks_count_without_integration_test_command():
    with pytest.raises(SystemExit):
        main.parse_args(["3"])


def test_parse_args_requires_one_top_level_scenario():
    with pytest.raises(SystemExit):
        main.parse_args([])
