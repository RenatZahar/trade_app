import asyncio
from argparse import Namespace

import pandas as pd

from modules.blockchain_parser import main_parser
from modules.logger import timing
from modules.logger import run_tracker


def test_build_parser_progress_snapshot_uses_recent_groups_for_speed_and_eta():
    snapshot = main_parser._build_parser_progress_snapshot(
        last_range="101-110",
        processed_blocks=20,
        remaining_blocks=30,
        recent_groups=[
            {"blocks": 10, "duration_sec": 60},
            {"blocks": 10, "duration_sec": 60},
        ],
    )

    assert snapshot == {
        "last_range": "101-110",
        "processed_blocks": 20,
        "remaining_blocks": 30,
        "recent_groups_count": 2,
        "recent_blocks": 20,
        "recent_duration_sec": 120,
        "recent_blocks_per_min": 10,
        "eta": "00:03:00",
    }


def test_parser_finishes_non_empty_block_stage_once(monkeypatch):
    monkeypatch.setattr(run_tracker, "get_init_number", lambda: 700)
    run_tracker.RunTracker(Namespace(start_parser=True))
    finished_stages = []

    async def fake_set_wal_mode(_db_path):
        return None

    async def fake_existing_last_block(_db_path, _start_block):
        return 9

    async def fake_parsing_data(_blocks_group):
        return pd.DataFrame({"Block_height": [10], "Amount": [1.0]})

    async def fake_save_data_to_db_with_semaphore(_data, _db_path):
        return None

    monkeypatch.setattr(main_parser, "send_message", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(main_parser.apf, "set_wal_mode", fake_set_wal_mode)
    monkeypatch.setattr(main_parser.apf, "async_get_existing_last_block", fake_existing_last_block)
    monkeypatch.setattr(main_parser.apf, "get_rpc_connection", lambda: object())
    monkeypatch.setattr(main_parser.apf, "get_list_of_blocks_to_download", lambda *_args: [10])
    monkeypatch.setattr(
        main_parser.apf,
        "split_list_into_chunks",
        lambda *_args: iter([[10]]),
    )
    monkeypatch.setattr(main_parser.apf, "parsing_data", fake_parsing_data)
    monkeypatch.setattr(main_parser.apf, "get_statistik_data", lambda _data: (10, 10))
    monkeypatch.setattr(
        main_parser.apf,
        "save_data_to_db_with_semaphore",
        fake_save_data_to_db_with_semaphore,
    )
    monkeypatch.setattr(main_parser.apf, "print_cicle_info", lambda *_args: 60)
    monkeypatch.setattr(main_parser.apf, "get_avg_blocks_in_minut", lambda _time_of_circle: None)
    monkeypatch.setattr(
        main_parser.app_logger_module,
        "log_tracker_stage_started",
        lambda _tracker, _stage_data: None,
    )
    monkeypatch.setattr(
        main_parser.app_logger_module,
        "log_tracker_stage_finished",
        lambda _tracker, stage_data: finished_stages.append(stage_data),
    )
    monkeypatch.setattr(
        timing.app_logger_module,
        "log_tracker_stage_progress",
        lambda _tracker, _details: None,
    )

    asyncio.run(main_parser.parser())

    process_stage_finishes = [
        stage
        for stage in finished_stages
        if stage["stage"] == "parser.process_blocks_group"
    ]

    assert len(process_stage_finishes) == 1
    assert process_stage_finishes[0]["details"] == "blocks=1 range=10-10"
    assert all(stage is not None for stage in finished_stages)
