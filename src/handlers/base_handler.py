"""
Базовый класс для обработчиков сообщений
"""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, Application

from utils.sheets import GoogleSheets
from utils.logger import get_logger

# Настройка логирования
logger = get_logger()

class BaseHandler:
    """Базовый класс для обработчиков сообщений"""
    
    def __init__(self, sheets: GoogleSheets, application: Application = None):
        """Инициализация обработчика"""
        self.sheets = sheets
        # Загружаем вопросы только один раз при инициализации
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        self.application = application
        logger.init("base_handler", f"Инициализация обработчика", details={"вопросов": len(self.questions)})
    
    def refresh_questions(self):
        """Обновляет вопросы из источника данных"""
        # Перезагружаем вопросы
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        logger.data_processing("вопросы", "Обновление списка вопросов", details={"количество": len(self.questions)})
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user
        logger.user_action(user.id, "Запуск бота", "Начало взаимодействия")
        
        # Очищаем данные пользователя
        context.user_data.clear()
        
        # Проверяем, существует ли пользователь, и регистрируем его при необходимости
        is_new_user = not await self.sheets.async_is_user_exists(user.id)
        if is_new_user:
            username = user.username if user.username else "Не указан"
            if await self.sheets.async_add_user(user.id, username):
                logger.user_action(user.id, "Регистрация нового пользователя", details={"username": username})
            else:
                logger.error("регистрация_пользователя", details={"user_id": user.id, "username": username})
        else:
            logger.user_action(user.id, "Повторный запуск бота", details={"is_new_user": False})
        
        # Создаем клавиатуру с двумя кнопками
        keyboard = [
            [KeyboardButton("▶️ Зарегистрироваться")],
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Получаем приветственное сообщение и форматируем его
        message_data = await self.sheets.async_get_message('start')
        formatted_message = message_data["text"].format(username=user.first_name)
        
        # Проверяем, есть ли изображение для отправки
        image_url = message_data.get("image", "")
        if image_url and image_url.strip():
            try:
                # Отправляем изображение с подписью и клавиатурой
                await update.message.reply_photo(
                    photo=image_url,
                    caption=formatted_message,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error("отправка_изображения", e, details={"message_type": "start"})
                # В случае ошибки отправляем просто текст
                await update.message.reply_text(
                    formatted_message,
                    reply_markup=reply_markup
                )
        else:
            # Если изображения нет, отправляем только текст
            await update.message.reply_text(
                formatted_message,
                reply_markup=reply_markup
            )
        
        return "WAITING_START"
    
    async def restart(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /restart"""
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Перезапуск бота", "Обновление данных")
        
        # Обновляем список вопросов принудительно сбрасывая кэш
        self.sheets.invalidate_questions_cache()
        self.refresh_questions()
        
        # Перезапускаем бота
        return await self.start(update, context)
    
    async def cancel_editing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена редактирования"""
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Отмена редактирования")
        
        await update.message.reply_text(
            "❌ Действие отменено",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    async def finish_survey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершение опроса и благодарность пользователю"""
        user = update.effective_user
        logger.user_action(user.id, "Завершение опроса", details={"тип": "Регистрация завершена"})
        
        # Получаем сообщение о завершении из таблицы
        message_data = self.sheets.get_message("finish")
        
        # Форматируем сообщение (замена плейсхолдеров и обработка Markdown)
        message_text = message_data.get("text", "Спасибо за регистрацию!")
        
        # Заменяем плейсхолдеры для имени пользователя в разных форматах
        username = user.first_name or user.username or ""
        formatted_message = message_text.replace("{{username}}", username)
        formatted_message = formatted_message.replace("{username}", username)
        
        # Определяем клавиатуру для завершения
        reply_markup = ReplyKeyboardRemove()
        
        # Проверяем, есть ли изображение для отправки
        image_url = message_data.get("image", "")
        if image_url and image_url.strip():
            try:
                # Отправляем изображение с подписью и клавиатурой
                await update.message.reply_photo(
                    photo=image_url,
                    caption=formatted_message,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error("отправка_изображения", e, user_id=user.id, 
                            details={"message_type": "finish"})
                # В случае ошибки отправляем только текст с клавиатурой
                await update.message.reply_text(
                    formatted_message,
                    reply_markup=reply_markup
                )
        else:
            # Если изображения нет, отправляем только текст с клавиатурой
            await update.message.reply_text(
                formatted_message,
                reply_markup=reply_markup
            )
        return ConversationHandler.END
        
    async def back_to_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возвращает пользователя к начальному экрану"""
        user = update.effective_user
        logger.user_action(user.id, "Возврат к начальному экрану")
        
        # Просто перенаправляем на метод start
        return await self.start(update, context) 