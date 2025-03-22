"""
Базовый класс для обработчиков сообщений
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, Application

from utils.sheets import GoogleSheets

# Настройка логирования
logger = logging.getLogger(__name__)

class BaseHandler:
    """Базовый класс для обработчиков сообщений"""
    
    def __init__(self, sheets: GoogleSheets, application: Application = None):
        """Инициализация обработчика"""
        self.sheets = sheets
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        self.application = application
        logger.info(f"Инициализирован обработчик с {len(self.questions)} вопросами")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка команды /start"""
        user = update.effective_user
        logger.info(f"Пользователь {user.id} запустил бота")
        
        # Очищаем данные пользователя
        context.user_data.clear()
        
        # Регистрируем пользователя, если он еще не зарегистрирован
        if not self.sheets.is_user_exists(user.id):
            username = user.username if user.username else "Не указан"
            if not self.sheets.add_user(user.id, username):
                logger.error(f"Не удалось зарегистрировать пользователя {user.id}")
        
        # Создаем клавиатуру с двумя кнопками
        keyboard = [
            [KeyboardButton("▶️ Зарегистрироваться")],
            [KeyboardButton("ℹ️ Узнать о мероприятии")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Получаем приветственное сообщение и форматируем его
        message_data = self.sheets.get_message('start')
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
                logger.error(f"Ошибка при отправке изображения: {e}")
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
        logger.info(f"Пользователь {update.effective_user.id} перезапустил бота")
        
        # Обновляем список вопросов
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        logger.info(f"Обновлен список вопросов: {len(self.questions)} вопросов")
        
        # Перезапускаем бота
        return await self.start(update, context)
    
    async def cancel_editing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена редактирования"""
        logger.info(f"Пользователь {update.effective_user.id} отменил редактирование")
        
        await update.message.reply_text(
            "❌ Действие отменено",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    async def finish_survey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершение опроса"""
        user = update.effective_user
        logger.info(f"Пользователь {user.id} завершил опрос")
        
        # Получаем сообщение о завершении
        message_data = self.sheets.get_message('finish')
        formatted_message = message_data["text"].format(username=user.first_name)
        
        # Проверяем, есть ли изображение для отправки
        image_url = message_data.get("image", "")
        if image_url and image_url.strip():
            try:
                # Отправляем изображение с подписью
                await update.message.reply_photo(
                    photo=image_url,
                    caption=formatted_message,
                    reply_markup=ReplyKeyboardRemove()
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке изображения: {e}")
                # В случае ошибки отправляем только текст
                await update.message.reply_text(
                    formatted_message,
                    reply_markup=ReplyKeyboardRemove()
                )
        else:
            # Если изображения нет, отправляем только текст
            await update.message.reply_text(
                formatted_message,
                reply_markup=ReplyKeyboardRemove()
            )
        return ConversationHandler.END
        
    async def show_event_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает информацию о мероприятии"""
        user = update.effective_user
        logger.info(f"Пользователь {user.id} запросил информацию о мероприятии")
        
        # Создаем клавиатуру для возврата
        keyboard = [
            [KeyboardButton("▶️ Зарегистрироваться")],
            [KeyboardButton("🔙 Вернуться")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Получаем информацию о мероприятии
        message_data = self.sheets.get_message('event_info')
        event_info = message_data["text"].format(username=user.first_name)
        
        # Проверяем, есть ли изображение для отправки
        image_url = message_data.get("image", "")
        if image_url and image_url.strip():
            try:
                # Отправляем изображение с подписью
                await update.message.reply_photo(
                    photo=image_url,
                    caption=event_info,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке изображения: {e}")
                # В случае ошибки отправляем только текст
                await update.message.reply_text(
                    event_info,
                    reply_markup=reply_markup
                )
        else:
            # Если изображения нет, отправляем только текст
            await update.message.reply_text(
                event_info,
                reply_markup=reply_markup
            )
        
        return "WAITING_EVENT_INFO"
        
    async def back_to_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Возвращает пользователя к начальному экрану"""
        user = update.effective_user
        logger.info(f"Пользователь {user.id} вернулся к начальному экрану")
        
        # Просто перенаправляем на метод start
        return await self.start(update, context) 