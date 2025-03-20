"""
Модуль для создания обработчиков диалогов
"""

import logging
from telegram.ext import (
    CommandHandler, MessageHandler as TelegramMessageHandler, 
    ConversationHandler, filters
)

from models.states import *
from handlers.survey_handlers import SurveyHandler
from handlers.admin_handlers import AdminHandler
from handlers.edit_handlers import EditHandler
from handlers.message_handlers import MessageHandler as CustomMessageHandler

# Настройка логирования
logger = logging.getLogger(__name__)

def create_survey_handler(survey_handler: SurveyHandler) -> ConversationHandler:
    """Создает обработчик для проведения опроса"""
    logger.info("Создание обработчика опроса")
    
    # Создаем базовые состояния
    survey_states = {}
    
    # Добавляем состояния для ожидания начала и подтверждения
    survey_states[WAITING_START] = [
        TelegramMessageHandler(filters.Regex(r"^▶️ Начать опрос$"), survey_handler.begin_survey)
    ]
    
    survey_states[CONFIRMING] = [
        TelegramMessageHandler(filters.Regex(r"^✅ Подтвердить$"), survey_handler.handle_answer),
        TelegramMessageHandler(filters.Regex(r"^🔄 Начать заново$"), survey_handler.begin_survey)
    ]
    
    # Добавляем динамические состояния для каждого вопроса
    questions_count = len(survey_handler.questions)
    logger.info(f"Добавление состояний для {questions_count} вопросов")
    
    for i in range(questions_count):
        question_state = f"QUESTION_{i}"
        survey_states[question_state] = [
            TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, survey_handler.handle_answer)
        ]
    
    # Создаем обработчик диалога
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", survey_handler.start)
        ],
        states=survey_states,
        fallbacks=[
            CommandHandler("restart", survey_handler.restart)
        ],
        name="survey_conversation"
    )

def create_admin_handlers(admin_handler: AdminHandler, admin_ids: list) -> list:
    """Создает обработчики для административных команд"""
    logger.info("Создание обработчиков администрирования")
    
    handlers = []
    
    # Обработчик добавления вопроса
    add_question_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add_question", admin_handler.add_question, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            ADDING_QUESTION: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_new_question)
            ],
            CHOOSING_OPTIONS_TYPE: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_options_choice)
            ],
            ADDING_OPTIONS: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_option_input)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="add_question_conversation"
    )
    handlers.append(add_question_handler)
    
    # Обработчик сброса прохождения опроса для пользователя
    reset_user_handler = ConversationHandler(
        entry_points=[
            CommandHandler("reset_user", admin_handler.reset_user, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            RESETTING_USER: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_reset_user)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="reset_user_conversation"
    )
    handlers.append(reset_user_handler)
    
    # Обработчик очистки данных
    clear_data_handler = ConversationHandler(
        entry_points=[
            CommandHandler("clear_data", admin_handler.clear_data, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            CONFIRMING_CLEAR: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_clear_confirmation)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="clear_data_conversation"
    )
    handlers.append(clear_data_handler)
    
    # Обработчик добавления администратора
    add_admin_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add_admin", admin_handler.add_admin, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            ADDING_ADMIN: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_new_admin)
            ],
            ADDING_ADMIN_NAME: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_admin_name)
            ],
            ADDING_ADMIN_DESCRIPTION: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_admin_description)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="add_admin_conversation"
    )
    handlers.append(add_admin_handler)
    
    # Обработчик удаления администратора
    remove_admin_handler = ConversationHandler(
        entry_points=[
            CommandHandler("remove_admin", admin_handler.remove_admin, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            REMOVING_ADMIN: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_admin_remove)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="remove_admin_conversation"
    )
    handlers.append(remove_admin_handler)
    
    # Обработчик списка пользователей с пагинацией
    list_users_handler = ConversationHandler(
        entry_points=[
            CommandHandler("list_users", admin_handler.list_users, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            BROWSING_USERS: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_users_pagination)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", admin_handler.cancel_editing)
        ],
        name="list_users_conversation"
    )
    handlers.append(list_users_handler)
    
    # Добавляем остальные обработчики
    handlers.extend([
        CommandHandler("list_questions", admin_handler.list_questions, 
                      filters=filters.User(user_id=admin_ids)),
        CommandHandler("list_admins", admin_handler.list_admins, 
                      filters=filters.User(user_id=admin_ids))
    ])
    
    return handlers

def create_edit_handlers(edit_handler: EditHandler, admin_ids: list) -> list:
    """Создает обработчики для редактирования вопросов"""
    logger.info("Создание обработчиков редактирования")
    
    handlers = []
    
    # Обработчик редактирования вопроса
    edit_question_handler = ConversationHandler(
        entry_points=[
            CommandHandler("edit_question", edit_handler.edit_question, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            CHOOSING_QUESTION: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_question_choice)
            ],
            EDITING_QUESTION: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_edit_menu_choice)
            ],
            EDITING_QUESTION_TEXT: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_question_text_edit)
            ],
            EDITING_OPTIONS: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_options_edit)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", edit_handler.cancel_editing)
        ],
        name="edit_question_conversation"
    )
    handlers.append(edit_question_handler)
    
    # Обработчик удаления вопроса
    delete_question_handler = ConversationHandler(
        entry_points=[
            CommandHandler("delete_question", edit_handler.delete_question, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            DELETING_QUESTION: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_question_delete)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", edit_handler.cancel_editing)
        ],
        name="delete_question_conversation"
    )
    handlers.append(delete_question_handler)
    
    return handlers

def create_message_handlers(message_handler: CustomMessageHandler, admin_ids: list) -> ConversationHandler:
    """Создает обработчик для редактирования системных сообщений"""
    logger.info("Создание обработчика сообщений")
    
    return ConversationHandler(
        entry_points=[
            CommandHandler("messages", message_handler.edit_messages, 
                          filters=filters.User(user_id=admin_ids))
        ],
        states={
            CHOOSING_MESSAGE_TYPE: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, message_handler.choose_message_type)
            ],
            ENTERING_NEW_MESSAGE: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, message_handler.save_new_message)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", message_handler.cancel_editing)
        ],
        name="message_editing_conversation"
    ) 