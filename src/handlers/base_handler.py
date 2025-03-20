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
        
        # Создаем клавиатуру
        keyboard = [
            [KeyboardButton("▶️ Начать опрос")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Получаем приветственное сообщение и форматируем его
        start_message = self.sheets.get_message('start')
        formatted_message = start_message.format(username=user.first_name)
        
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
        finish_message = self.sheets.get_message('finish')
        formatted_message = finish_message.format(username=user.first_name)
        
        # Отправляем сообщение с благодарностью
        await update.message.reply_text(
            formatted_message,
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END 