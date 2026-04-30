import pytest

import cli_args


def test_parse_args_accepts_start_parser_flag():
    args = cli_args.parse_args(["--start_parser"])

    assert args.start_parser is True
    assert getattr(args, "command", None) is None


def test_parse_args_rejects_legacy_service_mode():
    with pytest.raises(SystemExit):
        cli_args.parse_args(["--service", "move_txs"])


def test_parse_args_accepts_integration_test_mode_with_blocks_and_seed():
    args = cli_args.parse_args(
        ["test", "downloaded-from-btc-data", "5", "13"]
    )

    assert args.command == "test"
    assert args.data_test == "downloaded-from-btc-data"
    assert args.blocks_count == 5
    assert args.seed == 13


def test_parse_args_accepts_main_pipeline_command():
    args = cli_args.parse_args(["main-pipeline"])

    assert args.command == "main-pipeline"
    assert args.start_parser is False


def test_parse_args_accepts_param_grid_command_with_seed_and_test_fraction():
    args = cli_args.parse_args(["param-grid", "--test-fraction", "0.25", "--seed", "34"])

    assert args.command == "param-grid"
    assert args.test_fraction == 0.25
    assert args.seed == 34
    assert args.start_parser is False


def test_parse_args_requires_blocks_count_for_downloaded_btc_test():
    with pytest.raises(SystemExit):
        cli_args.parse_args(["test", "downloaded-from-btc-data"])


def test_parse_args_rejects_blocks_count_without_integration_test_command():
    with pytest.raises(SystemExit):
        cli_args.parse_args(["3"])


def test_parse_args_requires_one_top_level_scenario():
    with pytest.raises(SystemExit):
        cli_args.parse_args([])
