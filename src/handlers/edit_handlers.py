"""
Обработчики для редактирования вопросов
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

from models.states import *
from handlers.base_handler import BaseHandler

# Настройка логирования
logger = logging.getLogger(__name__)

class EditHandler(BaseHandler):
    """Обработчики для редактирования вопросов"""
    
    async def edit_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало редактирования вопроса"""
        logger.info(f"Пользователь {update.effective_user.id} начал редактирование вопроса")
        
        # Очищаем данные пользователя
        context.user_data.clear()
        
        # Проверяем, есть ли вопросы
        if not self.questions:
            await update.message.reply_text(
                "❌ В данный момент нет доступных вопросов для редактирования.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Создаем клавиатуру с вопросами
        keyboard = []
        for i, question in enumerate(self.questions):
            # Ограничиваем длину вопроса для кнопки
            short_question = question[:30] + "..." if len(question) > 30 else question
            keyboard.append([KeyboardButton(f"{i+1}. {short_question}")])
        
        keyboard.append([KeyboardButton("❌ Отмена")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Отправляем список вопросов для выбора
        await update.message.reply_text(
            "Выберите вопрос для редактирования:",
            reply_markup=reply_markup
        )
        
        return CHOOSING_QUESTION
    
    async def handle_question_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора вопроса для редактирования"""
        choice = update.message.text
        logger.info(f"Получен выбор вопроса: {choice}")
        
        if choice == "❌ Отмена":
            await update.message.reply_text(
                "❌ Редактирование отменено",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        try:
            # Извлекаем номер вопроса из выбора (формат: "1. Вопрос")
            question_num = int(choice.split('.')[0]) - 1
            
            # Проверяем, что номер вопроса в допустимом диапазоне
            if 0 <= question_num < len(self.questions):
                logger.info(f"Номер вопроса: {question_num}, всего вопросов: {len(self.questions)}")
                
                # Сохраняем выбранный вопрос
                selected_question = self.questions[question_num]
                context.user_data['editing_question'] = selected_question
                context.user_data['editing_question_num'] = question_num
                
                logger.info(f"Сохранен вопрос для редактирования: {selected_question}")
                
                # Показываем меню редактирования
                keyboard = [
                    [KeyboardButton("✏️ Изменить текст вопроса")],
                    [KeyboardButton("🔄 Изменить варианты ответов")],
                    [KeyboardButton("❌ Отмена")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                await update.message.reply_text(
                    f"Выбран вопрос: {selected_question}\n\n"
                    "Выберите действие:",
                    reply_markup=reply_markup
                )
                return EDITING_QUESTION
            else:
                logger.error(f"Некорректный номер вопроса: {question_num}")
                await update.message.reply_text(
                    "❌ Некорректный номер вопроса. Пожалуйста, выберите из списка.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        except (ValueError, IndexError):
            logger.error(f"Не удалось обработать выбор: {choice}")
            await update.message.reply_text(
                "❌ Пожалуйста, выберите вопрос из списка.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
    
    async def handle_edit_menu_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора действия в меню редактирования"""
        choice = update.message.text
        logger.info(f"Выбрано действие в меню редактирования: {choice}")
        
        if 'editing_question' not in context.user_data:
            logger.error("Ошибка: editing_question отсутствует в context.user_data")
            await update.message.reply_text(
                "❌ Ошибка: вопрос не выбран",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        question = context.user_data['editing_question']
        logger.info(f"Редактируемый вопрос: {question}")
        
        # Получаем номер вопроса, если он есть
        question_num = context.user_data.get('editing_question_num')
        if question_num is None:
            # Если номера нет, находим его
            try:
                question_num = self.questions.index(question)
                context.user_data['editing_question_num'] = question_num
                logger.info(f"Номер вопроса определен: {question_num}")
            except ValueError:
                logger.error(f"Не удалось найти вопрос '{question}' в списке вопросов")
                question_num = -1
        
        # Проверяем наличие вариантов ответов
        has_options = bool(self.questions_with_options[question])
        logger.info(f"Наличие вариантов ответов: {has_options}")
        
        if choice == "✏️ Изменить текст вопроса":
            logger.info("Выбрано изменение текста вопроса")
            await update.message.reply_text(
                f"Текущий текст вопроса:\n{question}\n\n"
                "Введите новый текст вопроса:",
                reply_markup=ReplyKeyboardRemove()
            )
            return EDITING_QUESTION_TEXT
            
        elif choice == "🔄 Изменить варианты ответов":
            logger.info("Выбрано изменение вариантов ответов")
            
            # Создаем клавиатуру для редактирования вариантов
            keyboard = [
                [KeyboardButton("➕ Добавить вариант")],
                [KeyboardButton("➖ Удалить вариант")],
                [KeyboardButton("✨ Сделать свободным")],
                [KeyboardButton("❌ Отмена")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            # Показываем текущие варианты ответов
            options = self.questions_with_options[question]
            options_text = "\n".join(f"• {opt}" for opt in options) if options else "Нет вариантов ответов (свободный ответ)"
            
            await update.message.reply_text(
                f"Варианты ответов для вопроса:\n{options_text}\n\n"
                "Выберите действие:",
                reply_markup=reply_markup
            )
            logger.info("Отправлено меню редактирования вариантов")
            return EDITING_OPTIONS
            
        elif choice == "❌ Отмена":
            await update.message.reply_text(
                "❌ Редактирование отменено",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        else:
            await update.message.reply_text(
                "❌ Неизвестное действие. Пожалуйста, выберите из меню.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END 

    async def handle_question_text_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка редактирования текста вопроса"""
        new_text = update.message.text
        logger.info(f"Получен новый текст вопроса: {new_text}")
        
        # Проверяем наличие необходимых данных
        if 'editing_question' not in context.user_data:
            await update.message.reply_text(
                "❌ Ошибка: вопрос не выбран",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        old_question = context.user_data['editing_question']
        question_num = context.user_data.get('editing_question_num', -1)
        
        # Если номер вопроса не сохранен, находим его
        if question_num == -1:
            try:
                question_num = self.questions.index(old_question)
                context.user_data['editing_question_num'] = question_num
            except ValueError:
                await update.message.reply_text(
                    "❌ Ошибка: вопрос не найден в списке",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        
        # Редактируем текст вопроса
        success = self.sheets.edit_question_text(question_num, new_text)
        
        if success:
            # Обновляем список вопросов
            old_options = self.questions_with_options[old_question]
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            # Проверяем, что вопрос был обновлен
            if new_text in self.questions:
                await update.message.reply_text(
                    f"✅ Текст вопроса успешно обновлен:\n"
                    f"Было: {old_question}\n"
                    f"Стало: {new_text}",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "✅ Текст вопроса обновлен, но требуется перезагрузка бота для обновления списка вопросов.",
                    reply_markup=ReplyKeyboardRemove()
                )
        else:
            await update.message.reply_text(
                "❌ Не удалось обновить текст вопроса",
                reply_markup=ReplyKeyboardRemove()
            )
        
        # Очищаем данные редактирования
        context.user_data.pop('editing_question', None)
        context.user_data.pop('editing_question_num', None)
        
        return ConversationHandler.END

    async def handle_options_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка редактирования вариантов ответов"""
        choice = update.message.text
        logger.info(f"Выбрано действие с вариантами: {choice}")
        
        # Проверяем наличие необходимых данных
        if 'editing_question' not in context.user_data:
            await update.message.reply_text(
                "❌ Ошибка: вопрос не выбран",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        question = context.user_data['editing_question']
        question_num = context.user_data.get('editing_question_num', -1)
        
        # Если номер вопроса не сохранен, находим его
        if question_num == -1:
            try:
                question_num = self.questions.index(question)
                context.user_data['editing_question_num'] = question_num
            except ValueError:
                await update.message.reply_text(
                    "❌ Ошибка: вопрос не найден в списке",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        
        # Получаем текущие варианты ответов
        current_options = self.questions_with_options[question]
        
        if choice == "➕ Добавить вариант":
            # Запрашиваем новый вариант ответа
            await update.message.reply_text(
                "Введите новый вариант ответа:",
                reply_markup=ReplyKeyboardRemove()
            )
            # Сохраняем состояние
            context.user_data['adding_option'] = True
            return EDITING_OPTIONS
        
        elif choice == "➖ Удалить вариант":
            if not current_options:
                await update.message.reply_text(
                    "❌ У этого вопроса нет вариантов ответов для удаления",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
            
            # Создаем клавиатуру с вариантами для удаления
            keyboard = [[KeyboardButton(opt)] for opt in current_options]
            keyboard.append([KeyboardButton("❌ Отмена")])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Выберите вариант для удаления:",
                reply_markup=reply_markup
            )
            # Сохраняем состояние
            context.user_data['removing_option'] = True
            return EDITING_OPTIONS
        
        elif choice == "✨ Сделать свободным":
            # Удаляем все варианты ответов
            success = self.sheets.edit_question_options(question_num, [])
            
            if success:
                # Обновляем список вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                await update.message.reply_text(
                    "✅ Вопрос теперь свободный (без вариантов ответов)",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "❌ Не удалось обновить варианты ответов",
                    reply_markup=ReplyKeyboardRemove()
                )
            return ConversationHandler.END
        
        elif choice == "❌ Отмена":
            await update.message.reply_text(
                "❌ Редактирование вариантов отменено",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        elif 'adding_option' in context.user_data:
            # Добавляем новый вариант ответа
            new_option = choice
            new_options = current_options + [new_option]
            
            success = self.sheets.edit_question_options(question_num, new_options)
            
            if success:
                # Обновляем список вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                await update.message.reply_text(
                    f"✅ Вариант ответа добавлен: {new_option}",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "❌ Не удалось добавить вариант ответа",
                    reply_markup=ReplyKeyboardRemove()
                )
            
            # Очищаем состояние
            context.user_data.pop('adding_option', None)
            return ConversationHandler.END
        
        elif 'removing_option' in context.user_data:
            if choice == "❌ Отмена":
                await update.message.reply_text(
                    "❌ Удаление варианта отменено",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('removing_option', None)
                return ConversationHandler.END
            
            # Удаляем выбранный вариант ответа
            if choice in current_options:
                new_options = [opt for opt in current_options if opt != choice]
                
                success = self.sheets.edit_question_options(question_num, new_options)
                
                if success:
                    # Обновляем список вопросов
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    
                    await update.message.reply_text(
                        f"✅ Вариант ответа удален: {choice}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                else:
                    await update.message.reply_text(
                        "❌ Не удалось удалить вариант ответа",
                        reply_markup=ReplyKeyboardRemove()
                    )
            else:
                await update.message.reply_text(
                    f"❌ Вариант '{choice}' не найден",
                    reply_markup=ReplyKeyboardRemove()
                )
            
            # Очищаем состояние
            context.user_data.pop('removing_option', None)
            return ConversationHandler.END
        
        else:
            await update.message.reply_text(
                "❌ Неизвестное действие. Пожалуйста, выберите из меню.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END

    async def delete_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало удаления вопроса"""
        logger.info(f"Пользователь {update.effective_user.id} начал удаление вопроса")
        
        # Очищаем данные пользователя
        context.user_data.clear()
        
        # Проверяем, есть ли вопросы
        if not self.questions:
            await update.message.reply_text(
                "❌ В данный момент нет доступных вопросов для удаления.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Создаем клавиатуру с вопросами
        keyboard = []
        for i, question in enumerate(self.questions):
            # Ограничиваем длину вопроса для кнопки
            short_question = question[:30] + "..." if len(question) > 30 else question
            keyboard.append([KeyboardButton(f"{i+1}. {short_question}")])
        
        keyboard.append([KeyboardButton("❌ Отмена")])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Отправляем список вопросов для выбора
        await update.message.reply_text(
            "Выберите вопрос для удаления:",
            reply_markup=reply_markup
        )
        
        return DELETING_QUESTION

    async def handle_question_delete(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка удаления вопроса"""
        choice = update.message.text
        logger.info(f"Получен выбор для удаления: {choice}")
        
        if choice == "❌ Отмена":
            await update.message.reply_text(
                "❌ Удаление отменено",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        try:
            # Проверяем, что выбор - это число
            question_num = int(choice.split('.')[0]) - 1  # -1 потому что нумерация с 1
            
            # Проверяем, что номер вопроса в допустимом диапазоне
            if 0 <= question_num < len(self.questions):
                # Получаем вопрос для удаления
                question_to_delete = self.questions[question_num]
                
                # Удаляем вопрос
                success = self.sheets.delete_question(question_num)
                
                if success:
                    # Обновляем список вопросов
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    
                    await update.message.reply_text(
                        f"✅ Вопрос успешно удален:\n{question_to_delete}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    logger.info(f"Вопрос удален: {question_to_delete}")
                else:
                    await update.message.reply_text(
                        "❌ Не удалось удалить вопрос. Пожалуйста, попробуйте позже.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    logger.error(f"Не удалось удалить вопрос с номером {question_num}")
                
                return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "❌ Некорректный номер вопроса. Пожалуйста, выберите из списка.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.error(f"Некорректный номер вопроса: {question_num}")
                return ConversationHandler.END
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите номер вопроса.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.error(f"Не удалось преобразовать выбор в число: {choice}")
            return ConversationHandler.END 