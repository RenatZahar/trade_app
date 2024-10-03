import requests
import os
from dotenv import load_dotenv
from pathlib import Path
import logging
from bs4 import BeautifulSoup

load_dotenv()

LOGIN = os.getenv('LOGIN')
PASSWORD = os.getenv('PASS')
ACCEPT = os.getenv('ACCEPT')

logging.info(f"Старт price_updater (WIP)")
# отказался от идеи подгружать новый файл с криптоархива. буду подгружать новые цены по апи
# потооооооом как нибудь скачивать цены продажи и покупки и на них делать дф для обучения

# def download_btc_price_file(save_directory):
#     url = 'https://www.cryptoarchive.com.au/bars/BTCUSDT'

#     # Создаём сессию
#     session = requests.Session()



#     try:
#         # URL для авторизации (уточните точный URL, если требуется)
#         login_url = 'https://www.cryptoarchive.com.au/login'

#         # Получаем страницу входа
#         login_page = session.get(login_url)
#         login_page.raise_for_status()
#         print("Cookies до авторизации:", session.cookies.get_dict())

#         # Извлекаем CSRF-токен
#         print('login_page.text')
#         print(login_page.text)
#         soup = BeautifulSoup(login_page.text, 'html.parser')
#         csrf_token_input = soup.find('input', {'name': 'csrfToken'})
#         if csrf_token_input:
#             csrf_token = csrf_token_input['value']
#         else:
#             csrf_token = ''
#             logging.warning("CSRF-токен не найден на странице входа.")
        
#         # Данные для входа
#         login_data = {
#             'email': LOGIN,
#             'password': PASSWORD,
#             'accept': ACCEPT,
#             'csrfToken': csrf_token
#         }

#         # Авторизация на сайте
#         response = session.post(login_url, data=login_data)
#         response.raise_for_status()
#         print("Cookies после авторизации:", session.cookies.get_dict())
#         print("История перенаправлений:", response.history)
#         print("Окончательный URL:", response.url)
#         # Проверяем, успешен ли вход
#         if 'User Dashboard' not in response.text:
#             logging.error("Не удалось войти на сайт. Проверьте логин и пароль.")
#             return False

#         logging.info("Успешно авторизованы на сайте.")

#         # Загрузка файла с данными
#         file_response = session.get(url, stream=True)
#         file_response.raise_for_status()
#         print(file_response.status_code)
#         print(file_response.text)
#         print(session.cookies.get_dict())

#         # Определяем имя файла из заголовка ответа
#         filename = 'BTCUSDT.csv.gz'
#         print(file_response.headers)
#         if 'Content-Disposition' in file_response.headers:
#             content_disposition = file_response.headers['Content-Disposition']
#             print(content_disposition)
#             if 'filename=' in content_disposition:
#                 filename = content_disposition.split('filename=')[1].strip('"')

#         # Путь для сохранения файла
#         save_path = Path(save_directory) / filename

#         # Сохраняем файл
#         with open(save_path, 'wb') as f:
#             for chunk in file_response.iter_content(chunk_size=8192):
#                 f.write(chunk)

#         logging.info(f"Файл сохранён по пути: {save_path}")
#         return True

#     except requests.HTTPError as http_err:
#         logging.error(f"HTTP ошибка: {http_err}")
#         return False
#     except Exception as err:
#         logging.error(f"Ошибка при загрузке файла: {err}")
#         return False
