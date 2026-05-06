import pytest

import cli_args
from settings.runtime_contracts import (
    CLI_SCENARIO_TO_RUNTIME_SCENARIO,
    SCENARIO_RUNTIME_DEPENDENCIES,
)


def _subparser_action(parser):
    for action in parser._actions:
        if hasattr(action, "choices") and action.choices:
            return action
    raise AssertionError("Parser has no subparser action")


def _test_subparser_action(parser):
    test_parser = _subparser_action(parser).choices["test"]
    return _subparser_action(test_parser)


def _cli_scenarios_from_parser():
    parser = cli_args.build_parser()
    top_level_commands = set(_subparser_action(parser).choices)
    test_commands = {
        f"test {command_name}"
        for command_name in _test_subparser_action(parser).choices
    }

    return {"--start_parser", *top_level_commands - {"test"}, *test_commands}


def test_parse_args_accepts_start_parser_flag():
    args = cli_args.parse_args(["--start_parser"])

    assert args.start_parser is True
    assert getattr(args, "command", None) is None
    assert args.parser_tx_cache_lines is None
    assert args.parser_hash_cache_lines is None


def test_parse_args_accepts_parser_cache_overrides_with_start_parser():
    args = cli_args.parse_args(
        [
            "--start_parser",
            "--parser-tx-cache-lines",
            "0",
            "--parser-hash-cache-lines",
            "0",
        ]
    )

    assert args.parser_tx_cache_lines == 0
    assert args.parser_hash_cache_lines == 0


def test_parse_args_rejects_parser_cache_overrides_without_start_parser():
    with pytest.raises(SystemExit):
        cli_args.parse_args(["main-pipeline", "--parser-tx-cache-lines", "0"])


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
    assert args.blocks is None


def test_parse_args_accepts_integration_test_mode_with_explicit_blocks():
    args = cli_args.parse_args(
        ["test", "downloaded-from-btc-data", "--blocks", "blocks[873754,873755]"]
    )

    assert args.command == "test"
    assert args.data_test == "downloaded-from-btc-data"
    assert args.blocks_count is None
    assert args.seed is None
    assert args.blocks == [873754, 873755]


def test_parse_args_rejects_blocks_count_with_explicit_blocks():
    with pytest.raises(SystemExit):
        cli_args.parse_args(["test", "downloaded-from-btc-data", "2", "--blocks", "873754"])


def test_parse_args_accepts_main_pipeline_command():
    args = cli_args.parse_args(["main-pipeline"])

    assert args.command == "main-pipeline"
    assert args.collector == "legacy"
    assert args.start_parser is False


def test_parse_args_accepts_main_pipeline_wallet_stats_collector():
    args = cli_args.parse_args(["main-pipeline", "--collector", "wallet-stats"])

    assert args.command == "main-pipeline"
    assert args.collector == "wallet-stats"


def test_parse_args_rejects_unknown_main_pipeline_collector():
    with pytest.raises(SystemExit):
        cli_args.parse_args(["main-pipeline", "--collector", "unknown"])


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


def test_arg_parser_exposes_expected_cli_scenarios():
    assert _cli_scenarios_from_parser() == {
        "--start_parser",
        "main-pipeline",
        "param-grid",
        "test downloaded-from-btc-data",
    }


def test_cli_scenarios_have_runtime_contract_mapping():
    cli_scenarios = _cli_scenarios_from_parser()

    assert set(CLI_SCENARIO_TO_RUNTIME_SCENARIO) == cli_scenarios
    assert set(CLI_SCENARIO_TO_RUNTIME_SCENARIO.values()) <= set(
        SCENARIO_RUNTIME_DEPENDENCIES
    )
