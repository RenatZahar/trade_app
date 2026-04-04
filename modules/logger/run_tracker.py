# описываем инфраструктуру наблюдаемости

import os
import time
from datetime import datetime
from settings.paths import INIT_NUMBER_FILE_NAME, INIT_NUMBER_FILE_DIR

CURRENT_RUN_TRACKER = None

def get_init_number():
    os.makedirs(INIT_NUMBER_FILE_DIR, exist_ok=True) 
    path_ = INIT_NUMBER_FILE_DIR / INIT_NUMBER_FILE_NAME
    with open(path_, 'a+', encoding='utf-8') as file:
        file.seek(0)
        content = file.read()
        content = content.strip()
        count = 1 if not content else int(content)+1
        file.seek(0)
        file.truncate()
        file.write(str(count))
    return count

def get_arg(args):
    args_dict = vars(args)
    starting_arg = None
    for key, value in args_dict.items():
        if value:
            if starting_arg:
                starting_arg = starting_arg + ', ' + f'{key}, {value}'
            else:
                starting_arg = f'{key}, {value}'
    
    return starting_arg
        
class RunTracker():
    def __init__(self, args):
        global CURRENT_RUN_TRACKER
        self.id = get_init_number()
        self.start_arg = get_arg(args)
        self.args_dict = vars(args)

        self.started_at_dt = datetime.now()
        self.started_at = self.started_at_dt.strftime("%Y-%m-%d %H:%M:%S")

        self.started_at_ts = int(self.started_at_dt.timestamp())
        self.started_perf_counter = time.perf_counter()
        self.finished_at = None
        self.duration_sec = None
        self.duration_human = None
        self.status = 'running'
        self.error = None
        self.current_stage = None
        self.current_stage_started_at = None
        self.current_stage_started_perf_counter = None
        self.stages = []
        CURRENT_RUN_TRACKER = self

    
    def get_run_data(self):
        return {
            'run_id': self.id,
            'start_arg': self.start_arg,
            'args': self.args_dict,
            'started_at': self.started_at,
            'started_at_ts': self.started_at_ts,
            'finished_at': self.finished_at,
            'duration_sec': self.duration_sec,
            'duration_human': self.duration_human,
            'status': self.status,
            'error': self.error,
            'current_stage': self.current_stage,
            'current_stage_started_at': self.current_stage_started_at,
            'stages': self.stages,
        }

    def get_duration_data(self, start_perf_counter):
        elapsed = time.perf_counter() - start_perf_counter
        duration_sec = round(elapsed, 2)

        total_seconds = int(elapsed)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        duration_human = f"{hours:02}:{minutes:02}:{seconds:02}"

        return duration_sec, duration_human

    def start_stage(self, stage):
        stage_started_at_dt = datetime.now()
        self.current_stage = stage
        self.current_stage_started_at = stage_started_at_dt.strftime("%Y-%m-%d %H:%M:%S")
        self.current_stage_started_perf_counter = time.perf_counter()
        return {
            'stage': self.current_stage,
            'started_at': self.current_stage_started_at,
            'status': 'running',
        }

    def finish_stage(self, status='success', details=None):
        if self.current_stage is None or self.current_stage_started_perf_counter is None:
            return

        duration_sec, duration_human = self.get_duration_data(self.current_stage_started_perf_counter)
        stage_data = {
            'stage': self.current_stage,
            'started_at': self.current_stage_started_at,
            'status': status,
            'duration_sec': duration_sec,
            'duration_human': duration_human,
            'details': details,
        }
        self.stages.append(stage_data)
        self.current_stage = None
        self.current_stage_started_at = None
        self.current_stage_started_perf_counter = None
        return stage_data

        
    def finish_run(self, status, e = None):
        self.status = status
        if self.status == 'error' or self.status == 'interrupted':
            self.error = str(e)
        finished_at_dt = datetime.now()
        self.finished_at = finished_at_dt.strftime("%Y-%m-%d %H:%M:%S")

        self.duration_sec, self.duration_human = self.get_duration_data(self.started_perf_counter)
        return self.get_run_data()


def get_current_run_tracker():
    return CURRENT_RUN_TRACKER
