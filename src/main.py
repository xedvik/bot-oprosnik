"""
Основной файл бота для проведения опросов
"""

import asyncio
import logging
import sys
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ConversationHandler, filters
)

from config import BOT_TOKEN, ADMIN_IDS, SPREADSHEET_ID, setup_logging
from utils.sheets import GoogleSheets
from utils.helpers import setup_commands, is_admin
from models.states import *
from handlers.survey_handlers import SurveyHandler
from handlers.admin_handlers import AdminHandler
from handlers.edit_handlers import EditHandler

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
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
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
    survey_handler = SurveyHandler(sheets)
    admin_handler = AdminHandler(sheets, application)
    edit_handler = EditHandler(sheets)
    
    # Настройка команд бота
    await setup_commands(application, admin_ids)
    
    # Создаем словарь состояний для опроса динамически
    survey_states = {
        WAITING_START: [
            MessageHandler(filters.Regex(r"^▶️ Начать опрос$"), survey_handler.begin_survey)
        ],
        CONFIRMING: [
            MessageHandler(filters.Regex(r"^✅ Подтвердить$"), survey_handler.handle_answer),
            MessageHandler(filters.Regex(r"^🔄 Начать заново$"), survey_handler.begin_survey)
        ],
    }
    
    # Добавляем динамические состояния для вопросов
    survey_states.update({
        f"QUESTION_{i}": [MessageHandler(filters.TEXT & ~filters.COMMAND, survey_handler.handle_answer)]
        for i in range(len(survey_handler.questions))
    })
    
    # Создание основного обработчика опроса
    survey_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", survey_handler.start),
            MessageHandler(filters.Regex(r"^▶️ Начать опрос$"), survey_handler.begin_survey)
        ],
        states=survey_states,
        fallbacks=[
            CommandHandler("restart", survey_handler.restart)
        ],
        name="survey_conversation"
    )
    
    # Создание обработчика для добавления вопросов
    add_question_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add_question", admin_handler.add_question, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            ADDING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_new_question)
            ],
            CHOOSING_OPTIONS_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_options_choice)
            ],
            ADDING_OPTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_option_input)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="add_question_conversation"
    )
    
    # Создание обработчика для редактирования вопросов
    edit_question_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("edit_question", edit_handler.edit_question, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            CHOOSING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_question_choice)
            ],
            EDITING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_edit_menu_choice)
            ],
            EDITING_QUESTION_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_question_text_edit)
            ],
            EDITING_OPTIONS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_options_edit)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", edit_handler.cancel_editing)
        ],
        name="edit_question_conversation"
    )
    
    # Создание обработчика для удаления вопросов
    delete_question_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("delete_question", edit_handler.delete_question, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            DELETING_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_question_delete)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", edit_handler.cancel_editing)
        ],
        name="delete_question_conversation"
    )
    
    # Создание обработчика для очистки данных
    clear_data_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("clear_data", admin_handler.clear_data, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            CONFIRMING_CLEAR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_clear_confirmation)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="clear_data_conversation"
    )
    
    # Создание обработчика для добавления администратора
    add_admin_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add_admin", admin_handler.add_admin, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            ADDING_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_new_admin)
            ],
            ADDING_ADMIN_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_admin_name)
            ],
            ADDING_ADMIN_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_admin_description)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="add_admin_conversation"
    )
    
    # Создание обработчика для удаления администратора
    remove_admin_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("remove_admin", admin_handler.remove_admin, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            REMOVING_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_admin_remove)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="remove_admin_conversation"
    )
    
    # Создание обработчика для сброса опроса пользователя
    reset_user_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("reset_user", admin_handler.reset_user, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            RESETTING_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_reset_user)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="reset_user_conversation"
    )
    
    # Добавление обработчиков в приложение
    application.add_handler(survey_conv_handler)
    application.add_handler(add_question_conv_handler)
    application.add_handler(edit_question_conv_handler)
    application.add_handler(delete_question_conv_handler)
    application.add_handler(clear_data_conv_handler)
    application.add_handler(add_admin_conv_handler)
    application.add_handler(remove_admin_conv_handler)
    application.add_handler(reset_user_conv_handler)
    
    # Добавление обработчиков для административных команд
    application.add_handler(CommandHandler("restart", survey_handler.restart))
    application.add_handler(CommandHandler("stats", survey_handler.show_statistics, 
                                          filters=filters.User(user_id=admin_ids)))
    application.add_handler(CommandHandler("list_questions", admin_handler.list_questions, 
                                          filters=filters.User(user_id=admin_ids)))
    application.add_handler(CommandHandler("list_admins", admin_handler.list_admins, 
                                          filters=filters.User(user_id=admin_ids)))
    
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