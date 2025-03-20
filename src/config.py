"""
Конфигурация бота
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Выводим все переменные окружения для отладки
print("Переменные окружения:")
print(f"BOT_TOKEN: {'*' * 8 + os.getenv('BOT_TOKEN', '')[-4:] if os.getenv('BOT_TOKEN') else 'Не указан'}")
print(f"SPREADSHEET_ID: {os.getenv('SPREADSHEET_ID', 'Не указан')}")
print(f"GOOGLE_CREDENTIALS_FILE: {os.getenv('GOOGLE_CREDENTIALS_FILE', 'Не указан')}")

# Настройки бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(id.strip()) for id in ADMIN_IDS_STR.split(",") if id.strip()]

# Настройки Google Sheets
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "/app/credentials.json")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
QUESTIONS_SHEET = os.getenv("QUESTIONS_SHEET", "Вопросы с вариантами ответов")
ANSWERS_SHEET = os.getenv("ANSWERS_SHEET", "Ответы")
STATS_SHEET = os.getenv("STATS_SHEET", "Статистика")
ADMINS_SHEET = os.getenv("ADMINS_SHEET", "Админы")

# Названия листов в Google таблице
SHEET_NAMES = {
    'questions': QUESTIONS_SHEET,
    'answers': ANSWERS_SHEET,
    'statistics': STATS_SHEET,
    'admins': ADMINS_SHEET,
    'users': os.getenv("USERS_SHEET", "Пользователи")
}

# Заголовки листов
SHEET_HEADERS = {
    'questions': ['ID', 'Вопрос', 'Варианты ответов'],
    'answers': ['ID пользователя', 'ID вопроса', 'Ответ', 'Дата ответа'],
    'statistics': ['ID вопроса', 'Вариант ответа', 'Количество'],
    'admins': ['ID пользователя', 'Дата добавления'],
    'users': ['ID', 'Telegram ID', 'Username', 'Дата регистрации']
}

# Проверяем наличие критически важных переменных
if not SPREADSHEET_ID:
    print("ВНИМАНИЕ: SPREADSHEET_ID не указан в переменных окружения!")
    print("Содержимое переменной:", repr(os.getenv("SPREADSHEET_ID")))
    print("Тип переменной:", type(os.getenv("SPREADSHEET_ID")))

# Настройки логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "/app/logs/bot.log")
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def setup_logging():
    """Настройка логирования"""
    # Создаем директорию для логов, если она не существует
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настраиваем логирование
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            RotatingFileHandler(
                LOG_FILE,
                maxBytes=10*1024*1024,  # 10 MB
                backupCount=5
            ),
            logging.StreamHandler()
        ]
    )
    
    # Отключаем лишние логи от библиотек
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("telegram").setLevel(logging.INFO)
    
    # Создаем логгер для нашего приложения
    logger = logging.getLogger(__name__)
    logger.info("Логирование настроено")
    
    # Логируем важные переменные окружения
    logger.info(f"BOT_TOKEN: {'Указан' if BOT_TOKEN else 'Не указан'}")
    logger.info(f"SPREADSHEET_ID: {SPREADSHEET_ID or 'Не указан'}")
    logger.info(f"GOOGLE_CREDENTIALS_FILE: {GOOGLE_CREDENTIALS_FILE}")
    
    return logger


