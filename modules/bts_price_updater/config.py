import os
from dotenv import load_dotenv
from pathlib import Path
from config import setup_logging
load_dotenv() 

BASE_DIR = Path(__file__).resolve().parent #перенести BASE_DIR в главный конфиг

# Константы и настройки
URL = 'https://www.cryptoarchive.com.au/bars/BTCUSDT'
