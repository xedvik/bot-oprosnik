"""
Вспомогательные функции для бота
"""

from utils.logger import get_logger
from telegram import BotCommand, BotCommandScopeChat
from telegram.ext import Application
from telegram.error import BadRequest
import asyncio

# Инициализация логгера
logger = get_logger()

async def _async_setup_commands(application: Application, admin_ids: list):
    """Асинхронная реализация настройки команд бота"""
    logger.init("bot_commands", f"Настройка команд для админов: {admin_ids}")
    if not admin_ids:
        logger.warning("empty_admins_list", "Список администраторов пуст", 
                     details={"причина": "Не найдены записи администраторов", "действие": "Продолжаем настройку базовых команд"})
    
    # Базовые команды для всех пользователей
    basic_commands = [
        BotCommand("start", "Зарегистрироваться"),
    ]
    
    # Команды для управления вопросами
    question_commands = [
        BotCommand("add_question", "Добавить новый вопрос"),
        BotCommand("edit_question", "Редактировать вопрос"),
        BotCommand("delete_question", "Удалить вопрос"),
        BotCommand("list_questions", "Показать список вопросов"),
    ]
    
    # Команды для управления администраторами
    admin_management_commands = [
        BotCommand("add_admin", "Добавить администратора"),
        BotCommand("remove_admin", "Удалить администратора"),
        BotCommand("list_admins", "Показать список администраторов"),
    ]
    
    # Команды для управления данными и статистикой
    data_commands = [
        BotCommand("stats", "Показать статистику опроса"),
        BotCommand("clear_data", "Очистить все ответы и статистику"),
        BotCommand("reset_user", "Сбросить прохождение опроса для пользователя"),
        BotCommand("list_users", "Показать список пользователей"),
    ]
    
    # Команды для редактирования системных сообщений
    message_commands = [
        BotCommand("messages", "Редактировать системные сообщения"),
    ]
    
    # Команды для работы с постами
    post_commands = [
        BotCommand("create_post", "Создать новый пост"),
        BotCommand("list_posts", "Показать список постов"),
        BotCommand("manage_posts", "Управление постами (редактирование, удаление)"),
        BotCommand("edit_sent_post", "Редактировать текст отправленного поста"),
        BotCommand("edit_caption", "Редактировать подпись к изображению"),
    ]
    
    # Системные команды
    system_commands = [
        BotCommand("start", "Зарегистрироваться"),
        BotCommand("restart", "Перезапустить бота"),
    ]
    
    # Объединяем все админские команды в правильном порядке
    admin_commands = (
        system_commands +
        question_commands +
        admin_management_commands +
        message_commands +
        post_commands +
        data_commands
    )

    try:
        # Сначала удалим все существующие команды
        await application.bot.delete_my_commands()
        
        # Устанавливаем базовые команды для всех пользователей
        await application.bot.set_my_commands(
            commands=basic_commands
        )
        logger.init("bot_commands", "Установлены базовые команды")
        
        # Устанавливаем расширенный список команд для каждого админа
        for admin_id in admin_ids:
            try:
                # Проверяем, существует ли чат с админом
                try:
                    chat = await application.bot.get_chat(int(admin_id))
                    if chat:
                        # Создаем scope для конкретного чата
                        chat_scope = BotCommandScopeChat(chat_id=int(admin_id))
                        
                        # Устанавливаем команды для админа
                        await application.bot.set_my_commands(
                            commands=admin_commands,
                            scope=chat_scope
                        )
                        logger.admin_action(int(admin_id), "Установка команд", "Установлены админские команды")
                except BadRequest as e:
                    if "Chat not found" in str(e):
                        logger.warning("admin_chat_not_found", f"Чат с админом не найден", details={"admin_id": admin_id, "message": "Команды будут установлены после первого взаимодействия с ботом"})
                    else:
                        raise
                        
            except Exception as e:
                logger.error("setup_commands_admin", exception=e, details={"admin_id": admin_id})
                
    except Exception as e:
        logger.error("setup_commands", exception=e, details={"admin_ids": admin_ids})

def setup_commands(application: Application, admin_ids: list):
    """
    Настройка команд бота с разделением на админские и обычные.
    Эта функция может быть вызвана как в синхронном, так и в асинхронном коде.
    """
    try:
        # Получаем текущий цикл событий, если он существует
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Если цикл уже работает (мы в асинхронном контексте), создаем задачу
            asyncio.create_task(_async_setup_commands(application, admin_ids))
        else:
            # Иначе запускаем новый цикл для выполнения функции
            asyncio.run(_async_setup_commands(application, admin_ids))
    except RuntimeError:
        # Если не можем получить цикл событий, запускаем новый
        asyncio.run(_async_setup_commands(application, admin_ids))

# Оригинальная асинхронная функция сохранена для обратной совместимости
async def setup_commands_async(application: Application, admin_ids: list):
    """Настройка команд бота с разделением на админские и обычные (асинхронная версия)"""
    await _async_setup_commands(application, admin_ids)

def is_admin(user_id: int, admin_ids: list) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in admin_ids 

def get_admin_commands_description() -> str:
    """Получение списка доступных команд для администраторов"""
    commands = [
        "/start - Перезапустить бота",
        "/stats - Показать статистику опроса",
        "/questions - Показать список вопросов",
        "/edit_questions - Редактировать вопросы",
        "/add_question - Добавить вопрос",
        "/delete_question - Удалить вопрос",
        "/edit_message - Редактировать системные сообщения",
        "/view_users - Просмотр списка пользователей",
        "/reset_user - Сбросить прогресс пользователя",
        "/clear_data - Очистить все данные опроса",
        "/add_admin - Добавить администратора",
        "/remove_admin - Удалить администратора",
        "/create_post - Создать новый пост",
        "/list_posts - Просмотреть список постов",
        "/manage_posts - Управление постами (отправка, редактирование, удаление)",
        "/edit_sent_post - Редактировать текст отправленного поста",
        "/edit_caption - Редактировать подпись к изображению",
    ]
    
    return "\n".join(commands) 