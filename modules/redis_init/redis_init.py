# redis_init.py

import subprocess
import psutil
import logging
import os
import redis
import threading
import time
from settings.runtime import REDIS_EXECUTABLE_PATH, REDIS_PROCESS_NAME

logger = logging.getLogger("app")

redis_client = None


def start_redis_client():
    global redis_client
    redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

def is_redis_running():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == REDIS_PROCESS_NAME:
            return True
    return False

def get_redis_status():
    if is_redis_running():
        return True
    else:
        return start_redis()
    
def start_redis():
    if not os.path.exists(REDIS_EXECUTABLE_PATH):
        logger.error(f"Файл {REDIS_EXECUTABLE_PATH} не найден.")
        return False
    try:
        subprocess.Popen([REDIS_EXECUTABLE_PATH])
        time.sleep(1)
        return True
    except Exception as e:
        logger.error(f"Не удалось запустить Redis сервер: {e}")
        return False

def send_message(channel, message):
    global redis_client
    if redis_client is None:
        logger.error("Redis клиент не инициализирован. Вызовите start_redis_client() перед отправкой сообщений.")
        logger.error('cначала запускается тот модуль, который подписывается на канал Redis и ждет сообщений')

        return
    redis_client.publish(channel, message)

def waiting_for_message(channel, message_handler):
    global redis_client
    if redis_client is None:
        logger.error("Redis клиент не инициализирован. Вызовите start_redis_client() перед получением сообщений.")

        return

    def listen():
        pubsub = redis_client.pubsub()
        pubsub.subscribe(channel)
        for message in pubsub.listen():
            if message['type'] == 'message':
                threading.Thread(target=message_handler, args=(message['data'].decode(),)).start()

    threading.Thread(target=listen, daemon=True).start()

