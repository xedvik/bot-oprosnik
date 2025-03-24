"""
Обработчики для создания и отправки постов
"""

import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters
import telegram
import telegram.error  # Добавляем импорт для обработки ошибок Telegram
from io import BytesIO
from telegram.constants import ParseMode, ChatAction

from models.states import *
from utils.sheets import GoogleSheets
from handlers.base_handler import BaseHandler
from config import MAX_IMAGE_SIZE
from utils.logger import get_logger

# Получаем логгер для модуля
logger = get_logger()

class PostHandler(BaseHandler):
    """Обработчики для создания и отправки постов"""
    
    def __init__(self, sheets: GoogleSheets, application=None):
        super().__init__(sheets)
        self.application = application
    
    async def create_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало создания поста"""
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Создание поста", "Начало создания")
        
        # Добавляем пустой словарь для хранения данных о посте
        if not context.user_data.get('post'):
            context.user_data['post'] = {
                'title': '',
                'text': '',
                'image_file_id': None,
                'button_text': '',
                'button_url': ''
            }
        
        await update.message.reply_text(
            "📋 Введите название поста (будет отображаться в списке постов):",
            reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
        )
        
        return CREATING_POST
    
    async def handle_post_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка названия поста"""
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Создание поста", "Ввод названия")
        
        # Сохраняем название поста
        context.user_data['post']['title'] = update.message.text
        
        # Запрашиваем текст поста
        await update.message.reply_text(
            "📝 Введите текст поста:",
            reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
        )
        
        return ENTERING_POST_TEXT
    
    async def handle_post_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка содержимого поста"""
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Создание поста", "Ввод текста")
        
        # Сохраняем текст поста
        context.user_data['post']['text'] = update.message.text
        
        # Предлагаем прикрепить изображение
        keyboard = [
            ["📷 Прикрепить изображение"],
            ["⏭️ Пропустить"],
            ["❌ Отмена"]
        ]
        
        await update.message.reply_text(
            "Хотите ли вы прикрепить изображение к посту?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        
        return ADDING_POST_IMAGE
    
    async def handle_image_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора прикрепления изображения"""
        user_id = update.effective_user.id
        user_choice = update.message.text
        
        if user_choice == "📷 Прикрепить изображение":
            logger.admin_action(user_id, "Создание поста", "Выбор прикрепления изображения")
            
            await update.message.reply_text(
                "Отправьте изображение (фото или файл изображения).\n"
                f"Максимальный размер: {MAX_IMAGE_SIZE / (1024 * 1024):.1f} МБ",
                reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
            )
            
            return ADDING_POST_IMAGE
            
        elif user_choice == "⏭️ Пропустить":
            logger.admin_action(user_id, "Создание поста", "Пропуск добавления изображения")
            
            # Переходим к добавлению кнопки
            return await self.ask_add_button(update, context)
            
        elif user_choice == "❌ Отмена":
            return await self.cancel_post(update, context)
        
        # Если получен неизвестный ответ
        await update.message.reply_text(
            "Выберите один из предложенных вариантов.",
            reply_markup=ReplyKeyboardMarkup([
                ["📷 Прикрепить изображение"],
                ["⏭️ Пропустить"],
                ["❌ Отмена"]
            ], resize_keyboard=True)
        )
        
        return ADDING_POST_IMAGE
    
    async def handle_image_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка загрузки изображения"""
        user_id = update.effective_user.id
        
        # Проверяем, есть ли изображение в сообщении
        if update.message.photo:
            # Берем последнее (самое качественное) изображение
            photo = update.message.photo[-1]
            file_id = photo.file_id
            logger.admin_action(user_id, "Создание поста", "Загрузка фото", details={"file_id": file_id})
            
            # Сохраняем file_id изображения
            context.user_data['post']['image_file_id'] = file_id
            
            # Переходим к добавлению кнопки
            return await self.ask_add_button(update, context)
            
        elif update.message.document:
            document = update.message.document
            mime_type = document.mime_type
            
            # Проверяем, что это изображение
            if mime_type and mime_type.startswith('image/'):
                file_id = document.file_id
                file_size = document.file_size
                
                # Проверяем размер файла
                if file_size and file_size > MAX_IMAGE_SIZE:
                    await update.message.reply_text(
                        f"⚠️ Размер файла ({file_size / (1024 * 1024):.1f} МБ) превышает максимально допустимый "
                        f"({MAX_IMAGE_SIZE / (1024 * 1024):.1f} МБ).\nПожалуйста, отправьте файл меньшего размера.",
                        reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
                    )
                    return ADDING_POST_IMAGE
                
                logger.user_action(user_id, "Создание поста", "Загрузка документа-изображения", details={"file_id": file_id})
                logger.admin_action(user_id, "Создание поста", "Загрузка документа-изображения", details={"file_id": file_id})
                
                # Сохраняем file_id изображения
                context.user_data['post']['image_file_id'] = file_id
                
                # Переходим к добавлению кнопки
                return await self.ask_add_button(update, context)
            else:
                await update.message.reply_text(
                    "❌ Отправленный файл не является изображением. Пожалуйста, отправьте изображение.",
                    reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
                )
                return ADDING_POST_IMAGE
        
        # Если получено текстовое сообщение
        if update.message.text == "❌ Отмена":
            return await self.cancel_post(update, context)
        
        # Если получено что-то другое
        await update.message.reply_text(
            "Пожалуйста, отправьте изображение (фото или файл изображения).",
            reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
        )
        
        return ADDING_POST_IMAGE
    
    async def ask_add_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Спрашиваем, хочет ли пользователь добавить кнопку с ссылкой"""
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Создание поста", "Вопрос о добавлении кнопки со ссылкой")
        
        keyboard = [
            ["🔗 Добавить кнопку со ссылкой"],
            ["⏭️ Пропустить"],
            ["❌ Отмена"]
        ]
        
        await update.message.reply_text(
            "Хотите ли вы добавить кнопку со ссылкой к посту?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        
        return ADDING_URL_BUTTON
    
    async def handle_button_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ответа о добавлении кнопки со ссылкой"""
        user_id = update.effective_user.id
        user_choice = update.message.text
        
        if user_choice == "🔗 Добавить кнопку со ссылкой":
            logger.user_action(user_id, "Создание поста", "Добавление кнопки со ссылкой")
            
            await update.message.reply_text(
                "Введите текст, который будет отображаться на кнопке:",
                reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
            )
            
            return ENTERING_BUTTON_TEXT
            
        elif user_choice == "⏭️ Пропустить":
            logger.user_action(user_id, "Создание поста", "Пропуск добавления кнопки")
            
            # Переходим к подтверждению поста
            return await self.show_post_preview(update, context)
            
        elif user_choice == "❌ Отмена":
            return await self.cancel_post(update, context)
        
        # Если получен неизвестный ответ
        await update.message.reply_text(
            "Выберите один из предложенных вариантов.",
            reply_markup=ReplyKeyboardMarkup([
                ["🔗 Добавить кнопку со ссылкой"],
                ["⏭️ Пропустить"],
                ["❌ Отмена"]
            ], resize_keyboard=True)
        )
        
        return ADDING_URL_BUTTON
    
    async def handle_button_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текста кнопки"""
        user_id = update.effective_user.id
        button_text = update.message.text
        
        if button_text == "❌ Отмена":
            return await self.cancel_post(update, context)
        
        # Сохраняем текст кнопки
        context.user_data['post']['button_text'] = button_text
        logger.user_action(user_id, "Создание поста", "Ввод текста кнопки", details={"button_text": button_text})
        
        # Запрашиваем URL для кнопки
        await update.message.reply_text(
            "Теперь введите URL для кнопки (например, https://example.com):",
            reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
        )
        
        return ENTERING_BUTTON_URL
    
    async def handle_button_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка URL для кнопки"""
        user_id = update.effective_user.id
        button_url = update.message.text
        
        if button_url == "❌ Отмена":
            return await self.cancel_post(update, context)
        
        # Проверяем, что URL начинается с http:// или https://
        if not (button_url.startswith('http://') or button_url.startswith('https://')):
            button_url = 'https://' + button_url
            logger.admin_action(user_id, "Редактирование URL", f"Добавлен https:// к URL: {button_url}")
        
        # Сохраняем URL кнопки
        context.user_data['post']['button_url'] = button_url
        logger.user_action(user_id, "Создание поста", "Ввод URL кнопки", details={"button_url": button_url})
        
        # Переходим к подтверждению поста
        return await self.show_post_preview(update, context)
    
    async def show_post_preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ предварительного просмотра поста"""
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Создание поста", "Предварительный просмотр")
        
        post = context.user_data.get('post', {})
        post_title = post.get('title', '')
        post_text = post.get('text', '')
        image_file_id = post.get('image_file_id')
        button_text = post.get('button_text', '')
        button_url = post.get('button_url', '')
        
        # Создаем клавиатуру для подтверждения
        keyboard = [
            ["✅ Подтвердить"],
            ["🔄 Начать заново"],
            ["❌ Отмена"]
        ]
        
        # Отправляем предварительный просмотр с изображением, если оно есть
        preview_message = "📝 <b>Предварительный просмотр поста:</b>\n\n"
        if post_title:
            preview_message += f"<b>{post_title}</b>\n\n"
        preview_message += post_text
        
        # Добавляем информацию о кнопке, если она есть
        if button_text and button_url:
            preview_message += f"\n\n<b>Кнопка:</b> {button_text} → {button_url}"
        
        # Создаем инлайн-клавиатуру для предпросмотра кнопки
        inline_keyboard = None
        if button_text and button_url:
            inline_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(text=button_text, url=button_url)]
            ])
        
        try:
            if image_file_id:
                # Отправляем изображение с подписью
                await update.message.reply_photo(
                    photo=image_file_id,
                    caption=preview_message,
                    parse_mode='HTML',
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
                
                # Если есть кнопка, показываем еще одно сообщение с предпросмотром кнопки
                if inline_keyboard:
                    await update.message.reply_text(
                        "Предпросмотр кнопки (вы можете нажать на нее):",
                        reply_markup=inline_keyboard
                    )
            else:
                # Отправляем только текст
                await update.message.reply_text(
                    preview_message,
                    parse_mode='HTML',
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
                
                # Если есть кнопка, показываем еще одно сообщение с предпросмотром кнопки
                if inline_keyboard:
                    await update.message.reply_text(
                        "Предпросмотр кнопки (вы можете нажать на нее):",
                        reply_markup=inline_keyboard
                    )
        except Exception as e:
            logger.error("ошибка_при_отправке_предварительного_просмотра", e)
            await update.message.reply_text(
                "❌ Произошла ошибка при создании предварительного просмотра. Пожалуйста, попробуйте снова.",
                reply_markup=ReplyKeyboardMarkup([["🔄 Начать заново"], ["❌ Отмена"]], resize_keyboard=True)
            )
        
        return CONFIRMING_POST
    
    async def handle_post_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка подтверждения поста"""
        user_id = update.effective_user.id
        user_choice = update.message.text
        
        if user_choice == "✅ Подтвердить":
            logger.user_action(user_id, "Создание поста", "Подтверждение создания поста")
            
            post = context.user_data.get('post', {})
            post_text = post.get('text', '')
            image_file_id = post.get('image_file_id')
            button_text = post.get('button_text', '')
            button_url = post.get('button_url', '')
            
            # Сохраняем пост в таблицу
            post_id = self.sheets.save_post(
                title=context.user_data['post'].get('title', 'Пост без названия'),
                text=context.user_data['post'].get('text', ''),
                image_url=image_file_id,
                button_text=context.user_data['post'].get('button_text', ''),
                button_url=context.user_data['post'].get('button_url', ''),
                admin_id=user_id
            )
            
            if post_id:
                # Предлагаем отправить пост всем пользователям
                keyboard = [
                    ["📨 Отправить всем пользователям"],
                    ["⏭️ Не отправлять"],
                    ["❌ Отмена"]
                ]
                
                await update.message.reply_text(
                    "✅ Пост успешно создан!\n\nХотите отправить этот пост всем пользователям?",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
                
                # Сохраняем ID поста для последующей отправки
                context.user_data['post_id'] = post_id
                
                return CONFIRMING_SEND_TO_ALL
            else:
                await update.message.reply_text(
                    "❌ Произошла ошибка при сохранении поста. Пожалуйста, попробуйте снова.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
                
        elif user_choice == "🔄 Начать заново":
            logger.user_action(user_id, "Создание поста", "Начать заново")
            
            # Очищаем данные о посте
            context.user_data['post'] = {
                'title': '',
                'text': '',
                'image_file_id': None,
                'button_text': '',
                'button_url': ''
            }
            
            # Начинаем создание поста заново
            await update.message.reply_text(
                "📋 Введите название поста (будет отображаться в списке постов):",
                reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
            )
            
            return CREATING_POST
            
        elif user_choice == "❌ Отмена":
            return await self.cancel_post(update, context)
        
        # Если получен неизвестный ответ
        await update.message.reply_text(
            "Выберите один из предложенных вариантов.",
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Подтвердить"],
                ["🔄 Начать заново"],
                ["❌ Отмена"]
            ], resize_keyboard=True)
        )
        
        return CONFIRMING_POST
    
    async def update_progress_message(self, message, users_count, success_count, fail_count, is_final=False):
        """Вспомогательный метод для обновления сообщения о прогрессе отправки"""
        if is_final:
            text = (
                f"✅ Отправка поста завершена!\n\n"
                f"📊 Статистика отправки:\n"
                f"👥 Всего пользователей: {users_count}\n"
                f"✅ Успешно отправлено: {success_count}\n"
                f"❌ Не удалось отправить: {fail_count}"
            )
        else:
            text = (
                f"🚀 Отправка поста...\n"
                f"✅ Успешно: {success_count}\n"
                f"❌ Не удалось: {fail_count}\n"
                f"📊 Прогресс: {success_count + fail_count}/{users_count}"
            )
        
        try:
            await message.edit_text(text)
        except telegram.error.BadRequest as e:
            # Если сообщение нельзя отредактировать, отправляем новое
            if "Message can't be edited" in str(e):
                try:
                    await message.reply_text(text)
                except Exception as e2:
                    logger.error("не_удалось_отправить_новое_сообщение_о_прогрессе", e2)
            else:
                logger.error("ошибка_при_обновлении_сообщения_о_прогрессе", e)
        except Exception as e:
            logger.error("ошибка_при_обновлении_сообщения_о_прогрессе", e)
    
    async def send_post_to_users(self, message, post, users_data):
        """Отправляет пост всем пользователям с обновлением прогресса"""
        # Счетчики для успешных и неуспешных отправок
        success_count = 0
        fail_count = 0
        
        # Создаем клавиатуру с кнопкой, если она есть
        inline_keyboard = None
        if post.get('button_text') and post.get('button_url'):
            inline_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text=post['button_text'], 
                    url=post['button_url']
                )]
            ])
        
        # Отправляем новое сообщение о прогрессе (вместо редактирования начального)
        progress_message = None
        try:
            progress_message = await message.reply_text(
                f"🚀 Отправка поста...\n"
                f"✅ Успешно: 0\n"
                f"❌ Не удалось: 0\n"
                f"📊 Прогресс: 0/{len(users_data)}"
            )
        except Exception as e:
            logger.error("ошибка_при_создании_сообщения_о_прогрессе", e)
            # Если не получилось создать сообщение о прогрессе, используем исходное
            progress_message = message
        
        # Отправляем пост каждому пользователю
        for user in users_data:
            try:
                telegram_id = int(user[1])  # Telegram ID пользователя
                username = user[0] if len(user) > 0 else "Неизвестный пользователь"
                
                # Пропускаем невалидные ID
                if telegram_id <= 0:
                    logger.warning("невалидный_id_пользователя", 
                                  details={"user_id": telegram_id, "username": username})
                    fail_count += 1
                    continue
                
                # Формируем текст сообщения с названием поста если оно есть
                post_title = post.get('title', '')
                post_text = post.get('text', '')
                
                # Если есть название, добавляем его в начало сообщения
                message_text = post_text
                if post_title:
                    message_text = f"<b>{post_title}</b>\n\n{post_text}"
                
                # Отправляем пост
                try:
                    if post.get('image_url'):
                        await self.application.bot.send_photo(
                            chat_id=telegram_id,
                            photo=post['image_url'],
                            caption=message_text,
                            parse_mode='HTML',
                            reply_markup=inline_keyboard
                        )
                    else:
                        await self.application.bot.send_message(
                            chat_id=telegram_id,
                            text=message_text,
                            parse_mode='HTML',
                            reply_markup=inline_keyboard
                        )
                    
                    success_count += 1
                    logger.info("отправка_поста_пользователю", 
                               details={"user_id": telegram_id, "username": username, "статус": "успех"})
                
                except telegram.error.BadRequest as e:
                    if "Chat not found" in str(e):
                        logger.warning("чат_не_найден", 
                                      details={"user_id": telegram_id, "username": username, "ошибка": str(e)})
                    else:
                        logger.error("ошибка_запроса_при_отправке", e, 
                                    details={"user_id": telegram_id, "username": username, "тип_ошибки": "BadRequest"})
                    fail_count += 1
                
                # Обрабатываем все остальные исключения Telegram API
                except Exception as telegram_error:
                    error_type = type(telegram_error).__name__
                    logger.warning("ошибка_отправки_сообщения", 
                                  details={"user_id": telegram_id, "username": username, 
                                          "ошибка": str(telegram_error), "тип_ошибки": error_type})
                    fail_count += 1
                
                # Обновляем сообщение о прогрессе каждые 10 пользователей
                if (success_count + fail_count) % 10 == 0 and progress_message:
                    await self.update_progress_message(
                        progress_message, 
                        len(users_data), 
                        success_count, 
                        fail_count
                    )
                
            except Exception as e:
                username = user[0] if len(user) > 0 else "Неизвестный пользователь"
                logger.error("ошибка_при_отправке_поста_пользователю", e, 
                            details={"user_id": telegram_id if 'telegram_id' in locals() else "неизвестный", 
                                    "username": username, 
                                    "error_type": type(e).__name__})
                fail_count += 1
        
        # Отправляем финальное сообщение о результатах
        if progress_message:
            await self.update_progress_message(
                progress_message,
                len(users_data),
                success_count,
                fail_count,
                is_final=True
            )
        else:
            # Если не удалось создать или использовать сообщение о прогрессе,
            # отправляем новое финальное сообщение
            try:
                await message.reply_text(
                    f"✅ Отправка поста завершена!\n\n"
                    f"📊 Статистика отправки:\n"
                    f"👥 Всего пользователей: {len(users_data)}\n"
                    f"✅ Успешно отправлено: {success_count}\n"
                    f"❌ Не удалось отправить: {fail_count}"
                )
            except Exception as e:
                logger.error("не_удалось_отправить_финальное_сообщение", e)
        
        return success_count, fail_count
    
    async def handle_send_to_all_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка подтверждения отправки поста всем пользователям"""
        user_id = update.effective_user.id
        user_choice = update.message.text
        
        if user_choice == "📨 Отправить всем пользователям":
            logger.user_action(user_id, "Отправка поста", "Рассылка всем пользователям")
            
            post_id = context.user_data.get('post_id')
            
            # Получаем информацию о посте
            post = self.sheets.get_post_by_id(post_id)
            
            if post:
                # Получаем список всех пользователей
                users_data = self.sheets.get_users_list(page=1, page_size=10000)[0]
                
                # Показываем сообщение о начале отправки
                message = await update.message.reply_text(
                    f"🚀 Начинаем отправку поста {len(users_data)} пользователям...",
                    reply_markup=ReplyKeyboardRemove()
                )
                
                # Отправляем пост пользователям
                await self.send_post_to_users(message, post, users_data)
                
                # Очищаем данные о посте
                if 'post' in context.user_data:
                    del context.user_data['post']
                if 'post_id' in context.user_data:
                    del context.user_data['post_id']
                
                return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "❌ Произошла ошибка при получении информации о посте.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
                
        elif user_choice == "⏭️ Не отправлять":
            logger.user_action(user_id, "Действие пользователя", "решил не отправлять пост пользователям")
            
            await update.message.reply_text(
                "✅ Пост создан, но не будет отправлен пользователям.\n"
                "Вы можете отправить его позже через список постов.",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Очищаем данные о посте
            if 'post' in context.user_data:
                del context.user_data['post']
            if 'post_id' in context.user_data:
                del context.user_data['post_id']
            
            return ConversationHandler.END
            
        elif user_choice == "❌ Отмена":
            return await self.cancel_post(update, context)
        
        # Если получен неизвестный ответ
        await update.message.reply_text(
            "Выберите один из предложенных вариантов.",
            reply_markup=ReplyKeyboardMarkup([
                ["📨 Отправить всем пользователям"],
                ["⏭️ Не отправлять"],
                ["❌ Отмена"]
            ], resize_keyboard=True)
        )
        
        return CONFIRMING_SEND_TO_ALL
    
    async def list_posts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список постов с возможностью отправки"""
        user_id = update.effective_user.id
        logger.user_action(user_id, "Управление постами", "Просмотр списка постов")
        
        # Получаем все посты
        posts = self.sheets.get_all_posts()
        
        if not posts:
            await update.message.reply_text(
                "📭 Пока нет созданных постов.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Получаем словарь админов для отображения имен
        admin_data = self.sheets.get_admins_info()
        admin_names = {}
        for admin in admin_data:
            if len(admin) >= 3:  # ID, имя, описание
                admin_names[admin[0]] = admin[1]  # ID -> имя
        
        logger.data_processing("админы", "Загружен словарь имён админов", details=admin_names)
        logger.data_processing("админы", "Полученные данные админов", details={"данные": admin_data})
        
        # Формируем сообщение со списком постов
        posts_text = "📋 <b>Список созданных постов:</b>\n\n"
        
        # Отображаем последние 10 постов (или меньше, если их меньше 10)
        for i, post in enumerate(posts[-10:], 1):
            created_at = post.get('created_at', 'Неизвестно')
            created_by = post.get('admin_id', '')  # Используем ключ admin_id
            
            # Получаем имя автора, если оно доступно
            author_name = admin_names.get(created_by, '')
            if not author_name:
                author_name = "Неизвестно"
            
            # Отображаем название поста вместо текста
            post_title = post.get('title', f"Пост #{post.get('id', '')}")
            
            # Логируем атрибуты поста для диагностики
            logger.data_processing("посты", f"Пост #{i}: ID={post.get('id')}, admin_id={created_by}, author_name={author_name}")
            
            posts_text += f"<b>#{i} | {created_at}</b>\n"
            posts_text += f"👤 Автор: {author_name}\n"
            posts_text += f"📄 <b>{post_title}</b>\n"
            
            # Добавляем информацию о наличии изображения и кнопки
            features = []
            if post.get('image_url'):
                features.append("🖼️ изображение")
            
            if post.get('button_text') and post.get('button_url'):
                features.append(f"🔗 кнопка \"{post.get('button_text')}\"")
            
            if features:
                posts_text += f"   📌 {' • '.join(features)}\n"
            
            posts_text += "\n"
        
        # Создаем инлайн-клавиатуру с возможностью отправки постов
        keyboard = []
        for i, post in enumerate(posts[-10:], 1):
            keyboard.append([
                InlineKeyboardButton(f"Отправить пост #{i}", callback_data=f"send_post:{post.get('id')}")
            ])
        
        keyboard.append([InlineKeyboardButton("Отмена", callback_data="cancel_posts")])
        
        await update.message.reply_text(
            posts_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return ConversationHandler.END
    
    async def cancel_post(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена создания поста"""
        user_id = update.effective_user.id
        logger.user_action(user_id, "Создание поста", "Отмена создания")
        
        # Очищаем данные о посте
        if 'post' in context.user_data:
            del context.user_data['post']
        if 'post_id' in context.user_data:
            del context.user_data['post_id']
        if 'edit_post_id' in context.user_data:
            del context.user_data['edit_post_id']
            logger.admin_action(user_id, "Отмена редактирования", "Удаление данных редактирования")
        
        await update.message.reply_text(
            "✅ Создание поста отменено.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ConversationHandler.END
    
    async def handle_post_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка колбеков от кнопок со списком постов"""
        query = update.callback_query
        user_id = query.from_user.id
        
        await query.answer()
        
        callback_data = query.data
        
        # Обработка запроса справки
        if callback_data == "post_help":
            help_text = (
                "📋 <b>Справка по работе с постами:</b>\n\n"
                "📩 <b>Отправить</b> - отправляет пост всем пользователям\n"
                "🗑️ <b>Удалить</b> - полностью удалить пост\n\n"
                "Нажмите на нужную кнопку с номером поста для выполнения действия."
            )
            
            # Создаем клавиатуру для возврата к списку постов
            keyboard = [[InlineKeyboardButton("◀️ Вернуться к постам", callback_data="manage_posts_back")]]
            
            await query.edit_message_text(
                help_text,
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return SELECTING_POST_ACTION
        
        # Обработка возврата из справки к списку постов
        if callback_data == "manage_posts_back":
            # Повторно вызываем метод manage_posts для обновления списка
            await self.manage_posts(update, context)
            return SELECTING_POST_ACTION
        
        if callback_data == "cancel_posts":
            # Отменяем просмотр постов
            await query.edit_message_text(
                "✅ Управление постами завершено.",
                reply_markup=None
            )
            return ConversationHandler.END
        
        # Если это отправка поста, извлекаем ID поста
        if callback_data.startswith("send_post:"):
            post_id = callback_data.split(":", 1)[1]
            logger.user_action(user_id, "Отправка поста", "Выбор поста для отправки", details={"post_id": post_id})
            
            # Получаем информацию о посте
            post = self.sheets.get_post_by_id(post_id)
            
            if not post:
                await query.edit_message_text(
                    "❌ Пост не найден или был удален.",
                    reply_markup=None
                )
                return ConversationHandler.END
            
            # Запрашиваем подтверждение отправки всем пользователям
            keyboard = []
            keyboard.append([
                InlineKeyboardButton("✅ Подтвердить отправку", callback_data=f"confirm_send:{post_id}")
            ])
            keyboard.append([
                InlineKeyboardButton("❌ Отмена", callback_data="cancel_posts")
            ])
            
            # Создаем превью поста с названием, если оно есть
            post_title = post.get('title', '')
            post_text = post.get('text', '')[:150] + ('...' if len(post.get('text', '')) > 150 else '')
            
            preview_text = post_text
            if post_title:
                preview_text = f"<b>{post_title}</b>\n\n{post_text}"
            
            await query.edit_message_text(
                f"⚠️ Вы уверены, что хотите отправить следующий пост всем пользователям?\n\n"
                f"<b>Превью поста:</b>\n{preview_text}",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            return ConversationHandler.END
        
        # Если это подтверждение отправки
        if callback_data.startswith("confirm_send:"):
            post_id = callback_data.split(":", 1)[1]
            logger.user_action(user_id, "Отправка поста", "Подтверждение отправки", details={"post_id": post_id})
            
            # Получаем информацию о посте
            post = self.sheets.get_post_by_id(post_id)
            
            if not post:
                await query.edit_message_text(
                    "❌ Пост не найден или был удален.",
                    reply_markup=None
                )
                return ConversationHandler.END
            
            # Сообщаем о начале отправки
            status_message = await query.edit_message_text(
                "🚀 Начинаем отправку поста...",
                reply_markup=None
            )
            
            # Получаем список всех пользователей
            users_data = self.sheets.get_users_list(page=1, page_size=10000)[0]
            
            # Отправляем пост пользователям
            await self.send_post_to_users(status_message, post, users_data)
            
            return ConversationHandler.END
        
        # Если это удаление поста
        if callback_data.startswith("delete_post:"):
            post_id = callback_data.split(":", 1)[1]
            logger.user_action(user_id, "Управление постами", "Выбор поста для удаления", details={"post_id": post_id})
            
            # Получаем информацию о посте
            post = self.sheets.get_post_by_id(post_id)
            
            if not post:
                await query.edit_message_text(
                    "❌ Пост не найден или был удален.",
                    reply_markup=None
                )
                return ConversationHandler.END
            
            # Сохраняем ID поста в контексте
            context.user_data['delete_post_id'] = post_id
            
            # Запрашиваем подтверждение удаления
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да, удалить", callback_data=f"confirm_delete:{post_id}")],
                [InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel_posts")]
            ])
            
            # Создаем превью поста с названием, если оно есть
            post_title = post.get('title', '')
            post_text = post.get('text', '')[:150] + ('...' if len(post.get('text', '')) > 150 else '')
            
            preview_text = post_text
            if post_title:
                preview_text = f"<b>{post_title}</b>\n\n{post_text}"
            
            await query.edit_message_text(
                f"⚠️ Вы уверены, что хотите удалить этот пост?\n\n"
                f"<b>Превью поста:</b>\n{preview_text}",
                parse_mode='HTML',
                reply_markup=keyboard
            )
            
            # Переходим в состояние подтверждения удаления
            return CONFIRMING_POST_DELETE
            
        # Если это подтверждение удаления
        if callback_data.startswith("confirm_delete:"):
            post_id = callback_data.split(":", 1)[1]
            logger.user_action(user_id, "Управление постами", "Подтверждение удаления", details={"post_id": post_id})
            
            # Удаляем пост
            if self.sheets.delete_post(post_id):
                await query.edit_message_text(
                    "✅ Пост успешно удален.",
                    reply_markup=None
                )
            else:
                await query.edit_message_text(
                    "❌ Не удалось удалить пост. Пожалуйста, попробуйте снова.",
                    reply_markup=None
                )
            
            # Очищаем данные о посте
            if 'delete_post_id' in context.user_data:
                del context.user_data['delete_post_id']
            
            return ConversationHandler.END
        
        # Если получен неизвестный колбек
        await query.edit_message_text(
            "❌ Неизвестное действие.",
            reply_markup=None
        )
        
        return ConversationHandler.END
    
    async def manage_posts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает список постов с возможностью управления (отправка, удаление)"""
        # Определяем, вызван ли метод из колбека или из команды
        if update.callback_query:
            # Если вызван из колбека, используем callback_query
            query = update.callback_query
            user_id = query.from_user.id
            send_message = query.edit_message_text
        else:
            # Если вызван из команды, используем message
            user_id = update.effective_user.id
            send_message = update.message.reply_text
        
        logger.user_action(user_id, "Администрирование", "Открытие меню управления постами")
        
        # Получаем все посты
        posts = self.sheets.get_all_posts()
        
        if not posts:
            await send_message(
                "📭 Пока нет созданных постов.\n\n"
                "Используйте /create_post, чтобы создать новый пост.",
                reply_markup=None
            )
            return ConversationHandler.END
        
        # Получаем словарь админов для отображения имен
        admin_data = self.sheets.get_admins_info()
        admin_names = {}
        for admin in admin_data:
            if len(admin) >= 3:  # ID, имя, описание
                admin_names[admin[0]] = admin[1]  # ID -> имя
        
        logger.data_processing("админы", "Загружен словарь имён админов", details=admin_names)
        logger.data_processing("админы", "Полученные данные админов", details={"данные": admin_data})
        
        # Формируем сообщение со списком постов
        posts_text = "📋 <b>Панель управления постами:</b>\n\n"
        
        # Отображаем последние 10 постов (или меньше, если их меньше 10)
        for i, post in enumerate(posts[-10:], 1):
            created_at = post.get('created_at', 'Неизвестно')
            created_by = post.get('admin_id', '')  # Используем ключ admin_id
            
            # Получаем имя автора, если оно доступно
            author_name = admin_names.get(created_by, '')
            if not author_name:
                author_name = "Неизвестно"
            
            # Отображаем название поста вместо текста
            post_title = post.get('title', f"Пост #{post.get('id', '')}")
            
            # Логируем атрибуты поста для диагностики
            logger.data_processing("посты", f"Пост #{i}: ID={post.get('id')}, admin_id={created_by}, author_name={author_name}")
            
            posts_text += f"<b>#{i} | {created_at}</b>\n"
            posts_text += f"👤 Автор: {author_name}\n"
            posts_text += f"📄 <b>{post_title}</b>\n"
            
            # Добавляем информацию о наличии изображения и кнопки
            features = []
            if post.get('image_url'):
                features.append("🖼️ изображение")
            
            if post.get('button_text') and post.get('button_url'):
                features.append(f"🔗 кнопка \"{post.get('button_text')}\"")
            
            if features:
                posts_text += f"   📌 {' • '.join(features)}\n"
            
            posts_text += "\n"
        
        # Создаем инлайн-клавиатуру с действиями для каждого поста
        keyboard = []
        
        for i, post in enumerate(posts[-10:], 1):
            # Кнопки для каждого поста: только отправка и удаление
            keyboard.append([
                InlineKeyboardButton(f"📩 #{i}", callback_data=f"send_post:{post.get('id')}"),
                InlineKeyboardButton(f"🗑️ #{i}", callback_data=f"delete_post:{post.get('id')}")
            ])
        
        # Добавляем разъяснение и кнопку закрытия
        keyboard.append([
            InlineKeyboardButton("❓ Справка по кнопкам", callback_data="post_help")
        ])
        keyboard.append([
            InlineKeyboardButton("❌ Закрыть", callback_data="cancel_posts")
        ])
        
        await send_message(
            posts_text,
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return SELECTING_POST_ACTION