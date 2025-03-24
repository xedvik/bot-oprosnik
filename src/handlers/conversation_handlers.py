"""
Модуль для создания обработчиков диалогов
"""

from telegram.ext import (
    CommandHandler, MessageHandler as TelegramMessageHandler, 
    ConversationHandler, filters, CallbackQueryHandler
)

from models.states import *
from handlers.survey_handlers import SurveyHandler
from handlers.admin_handlers import AdminHandler
from handlers.edit_handlers import EditHandler
from handlers.message_handlers import MessageHandler as CustomMessageHandler
from handlers.post_handlers import PostHandler
from utils.logger import get_logger

# Настройка логирования
logger = get_logger()

def create_survey_handler(survey_handler: SurveyHandler) -> ConversationHandler:
    """Создает обработчик для проведения опроса"""
    logger.init("conversation_handlers", "Создание обработчика опроса")
    
    # Создаем базовые состояния
    survey_states = {}
    
    # Добавляем состояния для ожидания начала и подтверждения
    survey_states[WAITING_START] = [
        TelegramMessageHandler(filters.Regex(r"^▶️ Зарегистрироваться$"), survey_handler.begin_survey),
    ]
    
    survey_states[CONFIRMING] = [
        TelegramMessageHandler(filters.Regex(r"^✅ Подтвердить$"), survey_handler.handle_answer),
        TelegramMessageHandler(filters.Regex(r"^🔄 Начать заново$"), survey_handler.begin_survey)
    ]
    
    # Добавляем динамические состояния для каждого вопроса
    questions_count = len(survey_handler.questions)
    logger.data_processing("состояния_опроса", "Добавление состояний для вопросов", details={"количество": questions_count})
    
    for i in range(questions_count):
        # Основное состояние для выбора варианта ответа
        question_state = f"QUESTION_{i}"
        survey_states[question_state] = [
            TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, survey_handler.handle_answer)
        ]
        
        # Состояние для выбора вложенного варианта ответа
        sub_question_state = f"QUESTION_{i}_SUB"
        survey_states[sub_question_state] = [
            TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, survey_handler.handle_answer)
        ]
    
    # Добавляем состояние для вложенных вариантов ответов
    survey_states[SUB_OPTIONS] = [
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
    logger.init("conversation_handlers", "Создание обработчиков администрирования")
    
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
            ],
            ADDING_NESTED_OPTIONS: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_nested_options)
            ],
            ADDING_FREE_TEXT_PROMPT: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, admin_handler.handle_add_free_text_prompt)
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
    logger.init("conversation_handlers", "Создание обработчиков редактирования")
    
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
            ],
            EDITING_SUB_OPTIONS: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_sub_options_edit)
            ],
            ADDING_SUB_OPTION: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_add_sub_option)
            ],
            REMOVING_SUB_OPTION: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_remove_sub_option)
            ],
            ADDING_FREE_TEXT_PROMPT: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_add_free_text_prompt)
            ],
            SELECTING_OPTION_TO_EDIT: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_option_text_edit)
            ],
            EDITING_OPTION_TEXT: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, edit_handler.handle_option_text_update)
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
    """Создает обработчик для редактирования сообщений"""
    logger.init("conversation_handlers", "Создание обработчика сообщений")
    
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
            ],
            ASKING_ADD_IMAGE: [
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, message_handler.handle_image_option)
            ],
            UPLOADING_MESSAGE_IMAGE: [
                TelegramMessageHandler(filters.PHOTO, message_handler.handle_image_upload),
                TelegramMessageHandler(filters.TEXT & ~filters.COMMAND, message_handler.handle_image_upload)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", message_handler.cancel_editing)
        ],
        name="message_editing_conversation"
    )

def create_post_handlers(post_handler: PostHandler, admin_ids: list) -> list:
    """Создает обработчики для работы с постами"""
    logger.init("conversation_handlers", "Создание обработчиков постов")
    
    return [
        ConversationHandler(
            entry_points=[
                CommandHandler("create_post", post_handler.create_post, 
                            filters=filters.User(user_id=admin_ids))
            ],
            states={
                CREATING_POST: [
                    TelegramMessageHandler(
                        filters.TEXT & ~filters.COMMAND & ~filters.Text(["❌ Отмена"]),
                        post_handler.handle_post_text
                    ),
                    TelegramMessageHandler(
                        filters.Text(["❌ Отмена"]),
                        post_handler.cancel_post
                    ),
                ],
                ENTERING_POST_TEXT: [
                    TelegramMessageHandler(
                        filters.TEXT & ~filters.COMMAND & ~filters.Text(["❌ Отмена"]),
                        post_handler.handle_post_content
                    ),
                    TelegramMessageHandler(
                        filters.Text(["❌ Отмена"]),
                        post_handler.cancel_post
                    ),
                ],
                ADDING_POST_IMAGE: [
                    TelegramMessageHandler(
                        filters.TEXT & filters.Text(["📷 Прикрепить изображение", "⏭️ Пропустить", "❌ Отмена"]),
                        post_handler.handle_image_option
                    ),
                    TelegramMessageHandler(
                        (filters.PHOTO | (filters.Document.IMAGE)) & ~filters.COMMAND,
                        post_handler.handle_image_upload
                    ),
                    TelegramMessageHandler(
                        filters.Text(["❌ Отмена"]),
                        post_handler.cancel_post
                    ),
                ],
                ADDING_URL_BUTTON: [
                    TelegramMessageHandler(
                        filters.TEXT & filters.Text(["🔗 Добавить кнопку со ссылкой", "⏭️ Пропустить", "❌ Отмена"]),
                        post_handler.handle_button_option
                    ),
                    TelegramMessageHandler(
                        filters.Text(["❌ Отмена"]),
                        post_handler.cancel_post
                    ),
                ],
                ENTERING_BUTTON_TEXT: [
                    TelegramMessageHandler(
                        filters.TEXT & ~filters.COMMAND & ~filters.Text(["❌ Отмена"]),
                        post_handler.handle_button_text
                    ),
                    TelegramMessageHandler(
                        filters.Text(["❌ Отмена"]),
                        post_handler.cancel_post
                    ),
                ],
                ENTERING_BUTTON_URL: [
                    # Для обычного создания поста
                    TelegramMessageHandler(
                        ~filters.Text(["❌ Отмена"]) & ~filters.COMMAND & filters.TEXT,
                        post_handler.handle_button_url,
                        filters.ChatType.PRIVATE & ~filters.UpdateType.EDITED_MESSAGE
                    ),
                    # Для отмены создания поста
                    TelegramMessageHandler(
                        filters.Text(["❌ Отмена"]),
                        post_handler.cancel_post
                    ),
                ],
                CONFIRMING_POST: [
                    TelegramMessageHandler(
                        filters.TEXT & filters.Text(["✅ Подтвердить", "🔄 Начать заново", "❌ Отмена"]),
                        post_handler.handle_post_confirmation
                    ),
                    TelegramMessageHandler(
                        filters.Text(["❌ Отмена"]),
                        post_handler.cancel_post
                    ),
                ],
                CONFIRMING_SEND_TO_ALL: [
                    TelegramMessageHandler(
                        filters.TEXT & filters.Text(["📨 Отправить всем пользователям", "⏭️ Не отправлять", "❌ Отмена"]),
                        post_handler.handle_send_to_all_confirmation
                    ),
                    TelegramMessageHandler(
                        filters.Text(["❌ Отмена"]),
                        post_handler.cancel_post
                    ),
                ],
                # Новые состояния для редактирования постов
                SELECTING_POST_ACTION: [
                    CallbackQueryHandler(post_handler.handle_post_callback)
                ],
                CONFIRMING_POST_DELETE: [
                    CallbackQueryHandler(post_handler.handle_post_callback)
                ],
            },
            fallbacks=[
                CommandHandler('cancel', post_handler.cancel_post),
                TelegramMessageHandler(filters.Text(["❌ Отмена"]), post_handler.cancel_post),
            ],
            allow_reentry=True,
            name="post_conversation"
        ),
        # Обработчик для просмотра списка постов
        CommandHandler('list_posts', post_handler.list_posts, 
                      filters=filters.User(user_id=admin_ids)),
        # Обработчик для управления постами (новый)
        CommandHandler('manage_posts', post_handler.manage_posts,
                      filters=filters.User(user_id=admin_ids)),
    ] 