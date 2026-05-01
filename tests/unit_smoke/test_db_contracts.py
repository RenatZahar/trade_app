from settings.db_contracts import (
    DB_TABLE_CONTRACTS,
    SCENARIO_DB_TABLE_DEPENDENCIES,
)
from settings.runtime_contracts import SCENARIO_RUNTIME_DEPENDENCIES


def test_all_db_runtime_scenarios_have_table_dependencies():
    scenarios_requiring_db = {
        scenario_name
        for scenario_name, dependencies in SCENARIO_RUNTIME_DEPENDENCIES.items()
        if "blocks_sql_data" in dependencies
    }

    assert scenarios_requiring_db <= set(SCENARIO_DB_TABLE_DEPENDENCIES)


def test_all_scenario_table_dependencies_are_declared_in_db_contract():
    declared_tables = set(DB_TABLE_CONTRACTS)
    missing_tables = {
        table_name
        for table_names in SCENARIO_DB_TABLE_DEPENDENCIES.values()
        for table_name in table_names
        if table_name not in declared_tables
    }

    assert missing_tables == set()


def test_required_table_contracts_include_columns():
    required_tables_without_columns = {
        table_name
        for table_name, contract in DB_TABLE_CONTRACTS.items()
        if contract.get("required") and not contract.get("columns")
    }

    assert required_tables_without_columns == set()
