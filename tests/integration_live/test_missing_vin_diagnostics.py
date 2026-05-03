import os
from collections import Counter

import pytest

from modules.blockchain_parser import async_parser_functions as apf
from settings.parser import MIN_VALUE_THRESHOLD


DIAGNOSTIC_BLOCKS_ENV = "MISSING_VIN_DIAGNOSTIC_BLOCKS"


def parse_requested_blocks(raw_blocks: str) -> list[int]:
    blocks = []
    seen = set()
    for raw_block in raw_blocks.replace("[", "").replace("]", "").split(","):
        raw_block = raw_block.strip()
        if not raw_block:
            continue
        block_height = int(raw_block)
        if block_height <= 0:
            raise ValueError("Block height must be positive.")
        if block_height not in seen:
            blocks.append(block_height)
            seen.add(block_height)
    return blocks


def is_coinbase_transaction(tx_details: dict) -> bool:
    return any("coinbase" in vin_entry for vin_entry in tx_details.get("vin", []))


def passes_min_value_threshold(tx_details: dict) -> bool:
    return any(
        float(vout.get("value", 0)) >= MIN_VALUE_THRESHOLD
        for vout in tx_details.get("vout", [])
    )


def get_block_from_chain(block_height: int, rpc_connection) -> dict:
    block_hash = apf.sync_rpc_connection(rpc_connection, "getblockhash", block_height)
    return apf.sync_rpc_connection(rpc_connection, "getblock", block_hash)


def get_current_transactions_for_parser(block_data: dict, rpc_connection) -> list[dict]:
    commands = [
        ["getrawtransaction", txid, 1, block_data["hash"]]
        for txid in block_data["tx"]
    ]
    tx_details_list = apf.sync_rpc_connection(rpc_connection, None, commands)
    return [
        tx_details
        for tx_details in tx_details_list
        if (
            tx_details
            and not is_coinbase_transaction(tx_details)
            and passes_min_value_threshold(tx_details)
        )
    ]


def build_expected_vin_refs(tx_details_list: list[dict]) -> list[tuple[str, int, str]]:
    refs = []
    for tx_details in tx_details_list:
        current_txid = tx_details["txid"]
        for vin in tx_details.get("vin", []):
            prev_txid = vin.get("txid")
            prev_vout_index = vin.get("vout")
            if prev_txid is None or prev_vout_index is None:
                continue
            refs.append((prev_txid, int(prev_vout_index), current_txid))
    return refs


def get_prev_transactions(prev_txids: set[str], rpc_connection) -> dict[str, dict]:
    if not prev_txids:
        return {}
    commands = [
        ["getrawtransaction", prev_txid, 1]
        for prev_txid in sorted(prev_txids)
    ]
    prev_tx_details_list = apf.sync_rpc_connection(rpc_connection, None, commands)
    return {
        tx_details["txid"]: tx_details
        for tx_details in prev_tx_details_list
        if tx_details
    }


def classify_expected_ref(
    ref: tuple[str, int, str],
    prev_tx_map: dict[str, dict],
) -> str:
    prev_txid, prev_vout_index, _current_txid = ref
    prev_tx_details = prev_tx_map.get(prev_txid)
    if prev_tx_details is None:
        return "prev_tx_not_returned"
    if is_coinbase_transaction(prev_tx_details):
        return "prev_tx_is_coinbase"

    matching_vout = next(
        (
            vout
            for vout in prev_tx_details.get("vout", [])
            if vout.get("n") == prev_vout_index
        ),
        None,
    )
    if matching_vout is None:
        return "missing_vout_index"
    return "would_create_record"


def diagnose_missing_vin_refs(block_height: int, rpc_connection) -> dict:
    block_data = get_block_from_chain(block_height, rpc_connection)
    tx_details_list = get_current_transactions_for_parser(block_data, rpc_connection)
    expected_refs = build_expected_vin_refs(tx_details_list)
    prev_tx_map = get_prev_transactions(
        {prev_txid for prev_txid, _prev_vout, _current_txid in expected_refs},
        rpc_connection,
    )

    classifications = Counter(
        classify_expected_ref(ref, prev_tx_map)
        for ref in expected_refs
    )
    missing_reasons = Counter(
        {
            reason: count
            for reason, count in classifications.items()
            if reason != "would_create_record"
        }
    )

    sample_missing = []
    for ref in expected_refs:
        reason = classify_expected_ref(ref, prev_tx_map)
        if reason == "would_create_record":
            continue
        prev_txid, prev_vout_index, current_txid = ref
        sample_missing.append(
            {
                "reason": reason,
                "prev_txid": prev_txid,
                "vout": prev_vout_index,
                "current_txid": current_txid,
            }
        )
        if len(sample_missing) >= 10:
            break

    return {
        "block": block_height,
        "current_transactions_after_parser_filter": len(tx_details_list),
        "expected_vin_refs": len(expected_refs),
        "records_parser_would_create": classifications["would_create_record"],
        "missing_total": sum(missing_reasons.values()),
        "missing_reasons": dict(sorted(missing_reasons.items())),
        "sample_missing": sample_missing,
    }


@pytest.mark.integration_live
def test_missing_vin_refs_are_explained_by_coinbase_spends():
    raw_blocks = os.getenv(DIAGNOSTIC_BLOCKS_ENV, "")
    if not raw_blocks.strip():
        pytest.skip(f"Set {DIAGNOSTIC_BLOCKS_ENV}=873243,873774 to run diagnostics.")

    requested_blocks = parse_requested_blocks(raw_blocks)
    rpc_connection = apf.get_rpc_connection()

    diagnostics = [
        diagnose_missing_vin_refs(block_height, rpc_connection)
        for block_height in requested_blocks
    ]
    for diagnostic in diagnostics:
        print(diagnostic)

    unexpected = [
        diagnostic
        for diagnostic in diagnostics
        if set(diagnostic["missing_reasons"]) - {"prev_tx_is_coinbase"}
    ]
    assert not unexpected
