"""
Обработчики для редактирования системных сообщений
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from handlers.base_handler import BaseHandler
from config import MESSAGE_TYPES
from models.states import CHOOSING_MESSAGE_TYPE, ENTERING_NEW_MESSAGE

# Настройка логирования
logger = logging.getLogger(__name__)

class MessageHandler(BaseHandler):
    """Обработчики для редактирования системных сообщений"""
    
    async def edit_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса редактирования сообщений"""
        user_id = update.effective_user.id
        
        # Проверяем, является ли пользователь администратором
        if user_id not in self.sheets.get_admins():
            await update.message.reply_text(
                "❌ У вас нет прав для редактирования сообщений.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Создаем клавиатуру с типами сообщений
        keyboard = [[KeyboardButton(name)] for name in MESSAGE_TYPES.values()]
        keyboard.append([KeyboardButton("❌ Отмена")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Выберите тип сообщения для редактирования:",
            reply_markup=reply_markup
        )
        
        return CHOOSING_MESSAGE_TYPE
    
    async def choose_message_type(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора типа сообщения"""
        message_type = update.message.text
        
        # Проверяем отмену
        if message_type == "❌ Отмена":
            await update.message.reply_text(
                "Редактирование отменено.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Находим ключ типа сообщения
        message_key = None
        for key, value in MESSAGE_TYPES.items():
            if value == message_type:
                message_key = key
                break
        
        if not message_key:
            await update.message.reply_text(
                "❌ Неверный тип сообщения. Пожалуйста, выберите из предложенных вариантов.",
                reply_markup=ReplyKeyboardMarkup(
                    [[KeyboardButton(name)] for name in MESSAGE_TYPES.values()],
                    resize_keyboard=True
                )
            )
            return CHOOSING_MESSAGE_TYPE
        
        # Сохраняем выбранный тип
        context.user_data['editing_message_type'] = message_key
        
        # Получаем текущий текст сообщения
        current_message = self.sheets.get_message(message_key)
        
        # Создаем клавиатуру для отмены
        keyboard = [[KeyboardButton("❌ Отмена")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"Текущий текст сообщения:\n\n{current_message}\n\n"
            "Введите новый текст сообщения.\n"
            "Доступные переменные:\n"
            "{username} - имя пользователя\n\n"
            "Для отмены нажмите кнопку ниже.",
            reply_markup=reply_markup
        )
        
        return ENTERING_NEW_MESSAGE
    
    async def save_new_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сохранение нового текста сообщения"""
        new_text = update.message.text
        
        # Проверяем отмену
        if new_text == "❌ Отмена":
            await update.message.reply_text(
                "Редактирование отменено.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        message_type = context.user_data.get('editing_message_type')
        if not message_type:
            logger.error("Тип сообщения не найден в user_data")
            await update.message.reply_text(
                "❌ Произошла ошибка. Попробуйте начать редактирование заново.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Сохраняем новый текст
        if self.sheets.update_message(message_type, new_text):
            await update.message.reply_text(
                "✅ Сообщение успешно обновлено!",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при сохранении сообщения.",
                reply_markup=ReplyKeyboardRemove()
            )
        
        # Очищаем данные пользователя
        context.user_data.clear()
        return ConversationHandler.END