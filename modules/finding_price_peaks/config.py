import os
from dotenv import load_dotenv
from pathlib import Path
from config import setup_logging
load_dotenv() 

BASE_DIR = Path(__file__).resolve().parent #перенести BASE_DIR в главный конфиг

how_much_data_test_after_learning_mounth=6
cicle = 16
price_diff_pct = 8
plato = 1.0
