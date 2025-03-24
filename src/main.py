"""
Основной файл бота для проведения опросов
"""

import asyncio
import sys
import os
import signal
import logging
from datetime import datetime
import telegram
import warnings
from telegram.ext import (
    Application, CommandHandler,
    ConversationHandler, filters, CallbackQueryHandler,
    MessageHandler as TelegramMessageHandler
)
from telegram.request import HTTPXRequest
from telegram import Update, BotCommand

from config import BOT_TOKEN, ADMIN_IDS, SPREADSHEET_ID, configure_logging, GOOGLE_CREDENTIALS_FILE
from utils.sheets import GoogleSheets
from utils.helpers import setup_commands, setup_commands_async, is_admin
from utils.logger import get_logger
from models.states import *
from handlers.survey_handlers import SurveyHandler
from handlers.admin_handlers import AdminHandler
from handlers.edit_handlers import EditHandler
from handlers.message_handlers import MessageHandler as MessageEditHandler
from handlers.post_handlers import PostHandler
from handlers.conversation_handlers import (
    create_survey_handler,
    create_admin_handlers,
    create_edit_handlers,
    create_message_handlers,
    create_post_handlers
)

# Глобальный флаг для управления работой бота
running = True

# Настройка логирования
logger = configure_logging()

# Функция обработки сигналов для корректного завершения работы
def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы"""
    logger.info("Получен сигнал завершения работы", details={"signal": sig})
    # Устанавливаем глобальный флаг для завершения работы
    global running
    running = False

async def main():
    """Основная функция запуска бота"""
    # Логгер уже настроен через configure_logging() при импорте
    logger.data_processing("система", "Запуск бота", details={"action": "bot_started"})

    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Проверка и создание необходимых директорий
    os.makedirs("logs", exist_ok=True)
    
    # Проверка наличия необходимых переменных окружения
    if not BOT_TOKEN:
        logger.error("missing_bot_token", exception=Exception("BOT_TOKEN не указан в переменных окружения"))
        sys.exit(1)
        
    if not SPREADSHEET_ID:
        logger.error("missing_spreadsheet_id", exception=Exception("SPREADSHEET_ID не указан в переменных окружения"))
        sys.exit(1)
        
    # Проверка наличия файла с учетными данными Google
    if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
        logger.error("missing_credentials_file", 
                  exception=Exception(f"Файл с учетными данными Google не найден: {GOOGLE_CREDENTIALS_FILE}"))
        sys.exit(1)
    
    # Создаем приложение с настройками таймаутов
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30,
        pool_timeout=30
    )
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .build()
    )
    
    # Инициализация Google Sheets с явной передачей необходимых параметров
    try:
        sheets = GoogleSheets(
            google_credentials_file=GOOGLE_CREDENTIALS_FILE,
            spreadsheet_id=SPREADSHEET_ID
        )
        logger.data_processing("система", "Инициализация и загрузка вопросов", details={"action": "init_sheets"})
        # Получаем список админов из таблицы
        admin_ids = sheets.get_admins()
        logger.data_load("админы", "Google Sheets", details={"ids": admin_ids})
    except Exception as e:
        logger.error("инициализация_google_sheets", exception=e)
        # Используем админов из переменной окружения
        if not admin_ids and os.environ.get("ADMIN_IDS"):
            admin_ids = [int(id.strip()) for id in os.environ.get("ADMIN_IDS").split(",")]
            logger.data_processing("система", "Используем админов из переменной окружения", details={"admin_ids": admin_ids, "action": "config_fallback"})
    
    # Инициализация обработчиков с общим экземпляром sheets
    logger.data_processing("система", "Инициализация обработчиков", details={"action": "init_handlers"})
    survey_handler = SurveyHandler(sheets, application)
    admin_handler = AdminHandler(sheets, application)
    edit_handler = EditHandler(sheets, application)
    message_handler = MessageEditHandler(sheets, application)
    post_handler = PostHandler(sheets, application)
    logger.data_processing("система", "Обработчики инициализированы", details={"action": "init_handlers_complete"})
    
    # Настройка команд бота
    await setup_commands_async(application, admin_ids)
    
    # Создание обработчиков
    logger.data_processing("система", "Создание обработчиков диалогов", details={"action": "create_conv_handlers"})
    survey_conv_handler = create_survey_handler(survey_handler)
    admin_handlers = create_admin_handlers(admin_handler, admin_ids)
    edit_handlers = create_edit_handlers(edit_handler, admin_ids)
    message_conv_handler = create_message_handlers(message_handler, admin_ids)
    post_handlers = create_post_handlers(post_handler, admin_ids)
    logger.data_processing("система", "Обработчики диалогов созданы", details={"action": "create_conv_handlers_complete"})
    
    # Добавление обработчиков в приложение
    logger.data_processing("система", "Регистрация обработчиков в приложении", details={"action": "register_handlers"})
    application.add_handler(survey_conv_handler)
    
    # Добавляем обработчики администрирования
    for handler in admin_handlers:
        application.add_handler(handler)
    
    # Добавляем обработчики редактирования
    for handler in edit_handlers:
        application.add_handler(handler)
    
    # Добавляем обработчик редактирования сообщений
    application.add_handler(message_conv_handler)
    
    # Добавляем обработчики для постов
    for handler in post_handlers:
        application.add_handler(handler)
    
    # Добавляем обработчик колбеков для постов
    application.add_handler(
        CallbackQueryHandler(post_handler.handle_post_callback, 
                            pattern=r"^(send_post:|confirm_send:|cancel_posts|delete_post:|confirm_delete:|post_help|manage_posts_back)")
    )
    
    # Добавление обработчиков для административных команд
    application.add_handler(CommandHandler("restart", survey_handler.restart, 
                                          filters=filters.User(user_id=admin_ids)))
    application.add_handler(CommandHandler("stats", survey_handler.show_statistics, 
                                          filters=filters.User(user_id=admin_ids)))
    
    logger.data_processing("система", "Обработчики зарегистрированы", details={"action": "register_handlers_complete"})
    
    # Запуск бота
    logger.data_processing("система", "Бот запущен и готов к работе", details={"action": "bot_ready"})
    
    # Настраиваем бота для получения обновлений из Telegram
    await application.bot.set_my_commands(commands=[BotCommand("start", "Начать")])
    
    # Запускаем Updater для получения обновлений
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    try:
        # Бесконечный цикл для поддержания работы бота
        # Будет прерван по изменению глобальной переменной running
        while running:
            await asyncio.sleep(1)
    finally:
        # Корректное завершение работы бота
        logger.data_processing("система", "Бот остановлен пользователем", details={"action": "bot_shutdown"})
        # Плавное завершение работы updater и application
        await application.updater.stop()
        await application.stop()

if __name__ == "__main__":
    try:
        # Запускаем асинхронную функцию main через asyncio.run
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.data_processing("система", "Бот остановлен пользователем", details={"action": "bot_shutdown"})
    except Exception as e:
        logger.error("критическая_ошибка", e)
        sys.exit(1) 