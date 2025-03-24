"""
Конфигурация бота
"""

import os
import json
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
MESSAGES_SHEET = os.getenv("MESSAGES_SHEET", "Сообщения")
POSTS_SHEET = os.getenv("POSTS_SHEET", "Посты")

# Названия листов в Google таблице
SHEET_NAMES = {
    'questions': QUESTIONS_SHEET,
    'answers': ANSWERS_SHEET,
    'statistics': STATS_SHEET,
    'admins': ADMINS_SHEET,
    'users': os.getenv("USERS_SHEET", "Пользователи"),
    'messages': MESSAGES_SHEET,
    'posts': POSTS_SHEET
}

# Заголовки листов
SHEET_HEADERS = {
    'questions': ['ID', 'Вопрос', 'Варианты ответов'],
    'answers': ['ID пользователя', 'ID вопроса', 'Ответ', 'Дата ответа'],
    'statistics': ['ID вопроса', 'Вариант ответа', 'Количество'],
    'admins': ['ID пользователя', 'Дата добавления'],
    'users': ['Уникальный числовой ID', 'Telegram ID', 'Username', 'Дата регистрации'],
    'messages': ['Тип сообщения', 'Текст сообщения', 'Изображение', 'Последнее обновление'],
    'posts': ['ID', 'Название', 'Текст', 'Изображение', 'Кнопка (текст)', 'Кнопка (ссылка)', 'Дата создания', 'Создал']
}

# Типы системных сообщений
MESSAGE_TYPES = {
    'start': 'Приветственное сообщение',
    'finish': 'Сообщение после опроса',
    'event_info': 'Информация о мероприятии'
}

# Значения по умолчанию для системных сообщений
DEFAULT_MESSAGES = {
    'start': 'Здравствуйте, {username}! 👋\n\nПриглашаем вас поучаствовать в ДОДе Партии Новые Люди.\nНажмите кнопку ниже, чтобы зарегистрироваться.',
    'finish': 'Спасибо за регистрацию в мероприятии! 🎉\n\nБудем ждать вас 5 апреля в 12:00 по адресу: г. Москва, ул. Пушкина, д. 1\n\nДо встречи! 👋',
    'event_info': 'Информация о мероприятии:\n\nДень открытых дверей Партии Новые Люди состоится 5 апреля в 12:00 по адресу: г. Москва, ул. Пушкина, д. 1.\n\nВ программе:\n- Встреча с лидерами партии\n- Презентация программы\n- Интерактивные дискуссии\n- Фуршет\n\nПриходите, будет интересно! 🎯'
}

# Максимальный размер изображения для постов (в байтах)
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 МБ

# Проверяем наличие критически важных переменных
if not SPREADSHEET_ID:
    print("ВНИМАНИЕ: SPREADSHEET_ID не указан в переменных окружения!")
    print("Содержимое переменной:", repr(os.getenv("SPREADSHEET_ID")))
    print("Тип переменной:", type(os.getenv("SPREADSHEET_ID")))

# Настройки логирования
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "/app/logs/bot.log")
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Теперь подключаем utils.logger после определения всех констант
from utils.logger import get_logger, setup_logging, DEBUG, INFO, WARNING

# Определяем уровень логирования после импорта констант
LOG_LEVEL = INFO  # По умолчанию INFO
if LOG_LEVEL_STR == "DEBUG":
    LOG_LEVEL = DEBUG
elif LOG_LEVEL_STR == "WARNING":
    LOG_LEVEL = WARNING

# Настройки для уровней логирования модулей
MODULE_LOG_LEVELS = {
    'utils.sheets': os.getenv("SHEETS_LOG_LEVEL", "INFO"),
    'utils.questions_cache': os.getenv("CACHE_LOG_LEVEL", "INFO"),
    'handlers.base_handler': os.getenv("HANDLER_LOG_LEVEL", "INFO"),
    'httpx': "WARNING",
    'telegram': "INFO",
    'apscheduler': "INFO",
    'gspread': "WARNING"
}

def configure_logging():
    """
    Настройка логирования для поддержки новой системы с AppLogger.
    """
    # Создаем директорию для логов, если она не существует
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Настраиваем глобальное логирование
    setup_logging(
        level=LOG_LEVEL,
        log_file=LOG_FILE,
        date_format=LOG_DATE_FORMAT
    )
    
    # Получаем экземпляр нового логгера
    app_logger = get_logger()
    app_logger.data_processing("Логирование", "настроено", details={"action": "config_init"})
    
    # Логируем важные переменные окружения
    app_logger.data_processing(
        "Проверка", 
        "переменные окружения", 
        details={
            "BOT_TOKEN": 'Указан' if BOT_TOKEN else 'Не указан',
            "SPREADSHEET_ID": SPREADSHEET_ID or 'Не указан',
            "GOOGLE_CREDENTIALS_FILE": GOOGLE_CREDENTIALS_FILE,
            "action": "env_variables"
        }
    )
    
    return app_logger


