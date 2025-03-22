"""
Основной файл бота для проведения опросов
"""

import asyncio
import logging
import sys
import os
from telegram.ext import (
    Application, CommandHandler,
    ConversationHandler, filters, CallbackQueryHandler,
    MessageHandler as TelegramMessageHandler
)
from telegram.request import HTTPXRequest

from config import BOT_TOKEN, ADMIN_IDS, SPREADSHEET_ID, setup_logging
from utils.sheets import GoogleSheets
from utils.helpers import setup_commands, is_admin
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

# Настройка логирования
logger = setup_logging()

async def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота")
    
    # Проверка наличия необходимых переменных окружения
    if not BOT_TOKEN:
        logger.error("Не указан BOT_TOKEN в переменных окружения")
        sys.exit(1)
        
    if not SPREADSHEET_ID:
        logger.error("Не указан SPREADSHEET_ID в переменных окружения")
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
    
    # Инициализация Google Sheets
    try:
        sheets = GoogleSheets()
        # Получаем список админов из таблицы
        admin_ids = sheets.get_admins()
    except Exception as e:
        logger.error(f"Ошибка при инициализации Google Sheets: {e}")
        # Используем админов из переменной окружения
        admin_ids = ADMIN_IDS
        logger.info(f"Используем админов из переменной окружения: {admin_ids}")
    
    # Инициализация обработчиков
    survey_handler = SurveyHandler(sheets, application)
    admin_handler = AdminHandler(sheets, application)
    edit_handler = EditHandler(sheets, application)
    message_handler = MessageEditHandler(sheets, application)
    post_handler = PostHandler(sheets, application)
    
    # Настройка команд бота
    await setup_commands(application, admin_ids)
    
    # Создание обработчиков
    survey_conv_handler = create_survey_handler(survey_handler)
    admin_handlers = create_admin_handlers(admin_handler, admin_ids)
    edit_handlers = create_edit_handlers(edit_handler, admin_ids)
    message_conv_handler = create_message_handlers(message_handler, admin_ids)
    post_handlers = create_post_handlers(post_handler, admin_ids)
    
    # Добавление обработчиков в приложение
    application.add_handler(survey_conv_handler)
    
    # Добавляем административные обработчики
    for handler in admin_handlers:
        application.add_handler(handler)
    
    # Добавляем обработчики редактирования
    for handler in edit_handlers:
        application.add_handler(handler)
    
    # Добавляем обработчик сообщений
    application.add_handler(message_conv_handler)
    
    # Добавляем обработчики постов
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
    
    # Добавляем обработчик команды event_info для всех пользователей
    application.add_handler(CommandHandler("event_info", survey_handler.show_event_info))
    
    # Запуск бота
    logger.info("Бот запущен")
    
    # Правильный порядок запуска приложения
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Ждем сигнала завершения
    try:
        # Бесконечный цикл для поддержания работы бота
        await asyncio.Event().wait()
    finally:
        # Корректное завершение работы бота
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        sys.exit(1) 