"""
Обработчики для редактирования системных сообщений
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from handlers.base_handler import BaseHandler
from config import MESSAGE_TYPES
from models.states import CHOOSING_MESSAGE_TYPE, ENTERING_NEW_MESSAGE, ASKING_ADD_IMAGE, UPLOADING_MESSAGE_IMAGE

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
        
        # Получаем текущий текст сообщения и изображение
        message_data = self.sheets.get_message(message_key)
        current_message = message_data["text"]
        current_image = message_data.get("image", "")
        
        # Сохраняем текущее изображение в контексте
        context.user_data['current_image'] = current_image
        
        # Создаем клавиатуру для отмены
        keyboard = [[KeyboardButton("❌ Отмена")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Показываем текущее изображение, если оно есть
        if current_image and current_image.strip():
            try:
                await update.message.reply_photo(
                    photo=current_image,
                    caption="Текущее изображение для сообщения"
                )
            except Exception as e:
                logger.error(f"Ошибка при отображении текущего изображения: {e}")
                await update.message.reply_text(
                    "⚠️ Не удалось отобразить текущее изображение. URL изображения может быть неверным."
                )
        
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
        
        # Сохраняем новый текст в контексте
        context.user_data['new_text'] = new_text
        
        # Спрашиваем, хочет ли пользователь добавить/изменить изображение
        keyboard = [
            [KeyboardButton("📷 Добавить/изменить изображение")],
            [KeyboardButton("🗑️ Удалить существующее изображение")],
            [KeyboardButton("⏭️ Пропустить (оставить как есть)")],
            [KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Хотите добавить или изменить изображение для сообщения?",
            reply_markup=reply_markup
        )
        
        return ASKING_ADD_IMAGE
    
    async def handle_image_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора для изображения"""
        choice = update.message.text
        message_type = context.user_data.get('editing_message_type')
        new_text = context.user_data.get('new_text')
        
        if choice == "❌ Отмена":
            await update.message.reply_text(
                "Редактирование отменено.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        elif choice == "⏭️ Пропустить (оставить как есть)":
            # Сохраняем текст, но оставляем прежнее изображение
            current_image = context.user_data.get('current_image', '')
            
            if self.sheets.update_message(message_type, new_text, current_image):
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
        
        elif choice == "🗑️ Удалить существующее изображение":
            # Сохраняем текст и удаляем изображение
            if self.sheets.update_message(message_type, new_text, ""):
                await update.message.reply_text(
                    "✅ Сообщение успешно обновлено, изображение удалено!",
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
        
        elif choice == "📷 Добавить/изменить изображение":
            # Просим пользователя отправить изображение
            keyboard = [[KeyboardButton("❌ Отмена")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Отправьте изображение или URL изображения.\n"
                "Поддерживаются форматы JPG, PNG, GIF.\n\n"
                "Для отмены нажмите кнопку ниже.",
                reply_markup=reply_markup
            )
            
            return UPLOADING_MESSAGE_IMAGE
        
        # Если получен неизвестный выбор
        await update.message.reply_text(
            "❌ Неверный выбор. Пожалуйста, используйте кнопки.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    async def handle_image_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка загрузки изображения"""
        message_type = context.user_data.get('editing_message_type')
        new_text = context.user_data.get('new_text')
        
        # Проверяем, отправлено ли изображение
        if update.message.photo:
            # Получаем файл с максимальным размером
            photo = update.message.photo[-1]
            file_id = photo.file_id
            
            # Сохраняем текст и новое изображение
            if self.sheets.update_message(message_type, new_text, file_id):
                await update.message.reply_text(
                    "✅ Сообщение и изображение успешно обновлены!",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "❌ Произошла ошибка при сохранении сообщения.",
                    reply_markup=ReplyKeyboardRemove()
                )
            
        # Проверяем, отправлен ли URL изображения (обычный текст)
        elif update.message.text and update.message.text != "❌ Отмена":
            image_url = update.message.text.strip()
            
            # Простая проверка на URL изображения
            if (image_url.startswith('http') and 
                any(ext in image_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])):
                
                # Сохраняем текст и новый URL изображения
                if self.sheets.update_message(message_type, new_text, image_url):
                    await update.message.reply_text(
                        "✅ Сообщение и изображение успешно обновлены!",
                        reply_markup=ReplyKeyboardRemove()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Произошла ошибка при сохранении сообщения.",
                        reply_markup=ReplyKeyboardRemove()
                    )
            else:
                await update.message.reply_text(
                    "❌ Неверный формат URL изображения. URL должен содержать расширение изображения (.jpg, .png и т.д.).",
                    reply_markup=ReplyKeyboardRemove()
                )
                return UPLOADING_MESSAGE_IMAGE
        
        # Проверяем отмену
        elif update.message.text == "❌ Отмена":
            await update.message.reply_text(
                "Редактирование отменено.",
                reply_markup=ReplyKeyboardRemove()
            )
        
        # Если отправлено что-то другое
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте изображение или URL изображения.",
                reply_markup=ReplyKeyboardRemove()
            )
            return UPLOADING_MESSAGE_IMAGE
        
        # Очищаем данные пользователя
        context.user_data.clear()
        return ConversationHandler.END
    
    async def cancel_editing(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена редактирования"""
        # Очищаем данные пользователя
        context.user_data.clear()
        
        await update.message.reply_text(
            "Редактирование отменено.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ConversationHandler.END