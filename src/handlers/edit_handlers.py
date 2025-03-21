"""
Обработчики для редактирования вопросов
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler

from models.states import *
from handlers.base_handler import BaseHandler
from utils.sheets import GoogleSheets

# Настройка логирования
logger = logging.getLogger(__name__)

class EditHandler(BaseHandler):
    """Обработчики для редактирования вопросов"""
    
    def __init__(self, sheets: GoogleSheets, application=None):
        super().__init__(sheets)
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        self.application = application
    
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
            
            # Создаем улучшенную клавиатуру для редактирования вариантов
            keyboard = [
                [KeyboardButton("➕ Добавить вариант")],
                [KeyboardButton("➕ Добавить вложенные варианты")],
                [KeyboardButton("➖ Удалить вариант")],
                [KeyboardButton("✨ Сделать свободным")],
                [KeyboardButton("❌ Отмена")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            # Получаем текущие варианты ответов
            current_options = self.questions_with_options[question]
            
            # Показываем текущие варианты ответов с вложенными вариантами
            options_text = ""
            for opt in current_options:
                if isinstance(opt, dict) and "text" in opt:
                    options_text += f"• {opt['text']}"
                    if opt.get("sub_options"):
                        options_text += ":\n"
                        for sub_opt in opt["sub_options"]:
                            options_text += f"  ↳ {sub_opt}\n"
                    else:
                        options_text += "\n"
                else:
                    options_text += f"• {opt}\n"
            
            if not options_text:
                options_text = "Нет вариантов ответов (свободный ответ)"
            
            await update.message.reply_text(
                f"Варианты ответов для вопроса:\n{options_text}\n"
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
        
        await self._update_handlers_questions(update)
        
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
        
        # Проверяем, редактируем ли мы подварианты
        if 'editing_option_index' in context.user_data:
            return await self.handle_sub_options_edit(update, context)
        
        if choice == "➕ Добавить вариант":
            # Запрашиваем новый вариант ответа
            await update.message.reply_text(
                "Введите новый вариант ответа:",
                reply_markup=ReplyKeyboardRemove()
            )
            # Сохраняем состояние
            context.user_data['adding_option'] = True
            return EDITING_OPTIONS
            
        elif choice == "➕ Добавить вложенные варианты":
            # Проверяем, есть ли основные варианты ответов
            if not current_options:
                await update.message.reply_text(
                    "❌ Сначала нужно добавить основные варианты ответов",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
            
            # Создаем клавиатуру с вариантами для выбора родительского варианта
            keyboard = []
            for opt in current_options:
                # Используем только текст варианта
                if isinstance(opt, dict) and "text" in opt:
                    keyboard.append([KeyboardButton(opt["text"])])
                else:
                    keyboard.append([KeyboardButton(str(opt))])
            keyboard.append([KeyboardButton("❌ Отмена")])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Выберите вариант, к которому нужно добавить вложенные варианты:",
                reply_markup=reply_markup
            )
            # Сохраняем состояние
            context.user_data['selecting_parent_option'] = True
            return EDITING_SUB_OPTIONS
        
        elif choice == "➖ Удалить вариант":
            if not current_options:
                await update.message.reply_text(
                    "❌ У этого вопроса нет вариантов ответов для удаления",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
            
            # Создаем клавиатуру с вариантами для удаления
            keyboard = []
            for opt in current_options:
                if isinstance(opt, dict) and "text" in opt:
                    keyboard.append([KeyboardButton(opt["text"])])
                else:
                    keyboard.append([KeyboardButton(str(opt))])
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
            # Получаем актуальные данные перед изменением
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            # Проверяем, что вопрос существует в актуальном списке
            if question not in self.questions_with_options:
                logger.warning(f"Вопрос '{question}' не найден в актуальном списке вопросов")
                await update.message.reply_text(
                    "❌ Ошибка: вопрос не найден в актуальном списке",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
            
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
            new_option = {"text": choice, "sub_options": []}
            
            # Получаем актуальные данные перед изменением
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            # Проверяем, что вопрос существует
            if question in self.questions_with_options:
                current_options = self.questions_with_options[question]
            else:
                logger.warning(f"Вопрос '{question}' не найден в актуальном списке вопросов")
                await update.message.reply_text(
                    "❌ Ошибка: вопрос не найден в актуальном списке",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('adding_option', None)
                return ConversationHandler.END
                
            # Добавляем новый вариант к существующим
            new_options = current_options + [new_option]
            
            logger.info(f"Добавление варианта '{choice}' к существующим вариантам: {current_options}")
            
            success = self.sheets.edit_question_options(question_num, new_options)
            
            if success:
                # Обновляем список вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                # Спрашиваем, нужно ли добавить вложенные варианты
                keyboard = [
                    [KeyboardButton("✅ Да, добавить вложенные варианты")],
                    [KeyboardButton("❌ Нет, оставить как есть")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                # Сохраняем новый вариант для возможного добавления вложенных вариантов
                context.user_data['editing_option'] = choice
                # Также сохраняем индекс варианта (последний в списке)
                context.user_data['editing_option_index'] = len(new_options) - 1
                # Сохраняем текущий вопрос для последующего добавления вложенных вариантов
                context.user_data['current_question'] = question
                
                await update.message.reply_text(
                    f"✅ Вариант ответа добавлен: {choice}\n\n"
                    "Хотите добавить к нему вложенные варианты ответов?",
                    reply_markup=reply_markup
                )
                
                # Обновляем списки вопросов в других обработчиках
                await self._update_handlers_questions(update)
                
                # Очищаем состояние добавления обычного варианта
                context.user_data.pop('adding_option', None)
                return EDITING_SUB_OPTIONS
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
            
            # Получаем актуальные данные перед изменением
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            # Проверяем, что вопрос существует
            if question in self.questions_with_options:
                current_options = self.questions_with_options[question]
            else:
                logger.warning(f"Вопрос '{question}' не найден в актуальном списке вопросов")
                await update.message.reply_text(
                    "❌ Ошибка: вопрос не найден в актуальном списке",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('removing_option', None)
                return ConversationHandler.END
            
            # Удаляем выбранный вариант ответа
            option_to_remove = None
            new_options = []
            
            for opt in current_options:
                if isinstance(opt, dict) and "text" in opt and opt["text"] == choice:
                    option_to_remove = opt
                else:
                    new_options.append(opt)
            
            if option_to_remove:
                success = self.sheets.edit_question_options(question_num, new_options)
                
                if success:
                    # Обновляем список вопросов
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    
                    # Если у варианта были вложенные варианты, сообщаем об этом
                    sub_options_message = ""
                    if option_to_remove.get("sub_options"):
                        sub_options_message = f"\nВместе с ним удалены {len(option_to_remove['sub_options'])} вложенных вариантов."
                    
                    await update.message.reply_text(
                        f"✅ Вариант ответа удален: {choice}{sub_options_message}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
                    # Обновляем списки вопросов в других обработчиках
                    await self._update_handlers_questions(update)
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
            # Создаем обновленную клавиатуру для редактирования вариантов с новыми возможностями
            keyboard = [
                [KeyboardButton("➕ Добавить вариант")],
                [KeyboardButton("➕ Добавить вложенные варианты")],
                [KeyboardButton("➖ Удалить вариант")],
                [KeyboardButton("✨ Сделать свободным")],
                [KeyboardButton("❌ Отмена")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            # Показываем текущие варианты ответов с вложенными вариантами
            options_text = ""
            for opt in current_options:
                if isinstance(opt, dict) and "text" in opt:
                    options_text += f"• {opt['text']}"
                    if opt.get("sub_options"):
                        options_text += ":\n"
                        for sub_opt in opt["sub_options"]:
                            options_text += f"  ↳ {sub_opt}\n"
                    else:
                        options_text += "\n"
                else:
                    options_text += f"• {opt}\n"
            
            if not options_text:
                options_text = "Нет вариантов ответов (свободный ответ)"
            
            await update.message.reply_text(
                f"Варианты ответов для вопроса:\n{options_text}\n"
                "Выберите действие:",
                reply_markup=reply_markup
            )
            return EDITING_OPTIONS
    
    async def handle_sub_options_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка редактирования вложенных вариантов ответов"""
        choice = update.message.text
        logger.info(f"Выбрано действие с вложенными вариантами: {choice}")
        
        question = context.user_data['editing_question']
        question_num = context.user_data.get('editing_question_num', -1)
        
        # Если установлен current_question, используем его вместо editing_question
        if 'current_question' in context.user_data:
            question = context.user_data['current_question']
            # Обновляем editing_question для совместимости
            context.user_data['editing_question'] = question
            
            # Обновляем номер вопроса
            try:
                question_num = self.questions.index(question)
                context.user_data['editing_question_num'] = question_num
            except ValueError:
                logger.error(f"Вопрос '{question}' не найден в списке вопросов")
        
        # Обновляем список вариантов из базы данных перед обработкой
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        
        # Проверяем, что вопрос все еще существует
        if question not in self.questions_with_options:
            await update.message.reply_text(
                f"❌ Ошибка: вопрос '{question}' не найден в базе данных",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('editing_option', None)
            context.user_data.pop('editing_option_index', None)
            return ConversationHandler.END
                
        current_options = self.questions_with_options[question]
        
        # Вывод информации для отладки
        logger.info(f"Текущий вопрос: {question}")
        logger.info(f"Номер вопроса: {question_num}")
        logger.info(f"Текущие варианты: {current_options}")
        logger.info(f"Текущий выбор: {choice}")
        
        # Обработка кнопки "Добавить еще вложенный вариант"
        if choice == "➕ Добавить еще вложенный вариант" and 'editing_option' in context.user_data:
            parent_option_text = context.user_data['editing_option']
            await update.message.reply_text(
                f"Введите новый вложенный вариант для '{parent_option_text}':",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data['adding_sub_option'] = True
            return ADDING_SUB_OPTION
        
        # Обработка прямого ввода вложенного варианта
        if 'adding_sub_option' in context.user_data and choice not in ["✨ Сделать свободным", "❌ Отмена", "➕ Добавить вложенный вариант", "➕ Добавить еще вложенный вариант", "✅ Готово", "➖ Удалить вложенный вариант"]:
            # Передаем управление в обработчик добавления вложенного варианта
            logger.info(f"Перенаправление ввода вложенного варианта '{choice}' в handle_add_sub_option")
            return await self.handle_add_sub_option(update, context)
        
        # Специальная обработка для варианта после добавления нового варианта в вопрос
        if choice == "✅ Да, добавить вложенные варианты" and 'editing_option_index' in context.user_data:
            option_text = context.user_data['editing_option']
            option_index = context.user_data['editing_option_index']
            
            logger.info(f"Обработка добавления вложенных вариантов к новому варианту: {option_text} с индексом {option_index}")
            
            # Обновляем список вариантов для гарантии
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            # Получаем актуальные варианты
            if question in self.questions_with_options:
                current_options = self.questions_with_options[question]
                logger.info(f"Актуальные варианты после обновления: {current_options}")
            
            # Проверяем, что вариант есть в списке вариантов
            parent_found = False
            parent_option = None
            for i, opt in enumerate(current_options):
                if isinstance(opt, dict) and "text" in opt and opt["text"] == option_text:
                    parent_option = opt
                    parent_found = True
                    # Обновляем индекс на случай, если он изменился
                    context.user_data['editing_option_index'] = i
                    logger.info(f"Найден родительский вариант: {opt}")
                    break
                    
            if not parent_found:
                await update.message.reply_text(
                    f"❌ Ошибка: вариант '{option_text}' не найден в актуальном списке вариантов.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.error(f"Вариант '{option_text}' не найден в актуальном списке: {current_options}")
                return ConversationHandler.END
                
            # Запрашиваем ввод вложенного варианта сразу для найденного варианта
            keyboard = [
                [KeyboardButton("✨ Сделать свободным")],
                [KeyboardButton("❌ Отмена")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"Введите вложенный вариант для '{option_text}' или выберите 'Сделать свободным':",
                reply_markup=reply_markup
            )
            
            # Инициализируем список вложенных вариантов
            context.user_data['sub_options'] = []
            context.user_data['adding_sub_option'] = True
            # Устанавливаем parent_option для совместимости
            context.user_data['parent_option'] = option_text
            return ADDING_SUB_OPTION
        
        # Если выбран родительский вариант для добавления вложенных вариантов
        if 'selecting_parent_option' in context.user_data:
            if choice == "❌ Отмена":
                await update.message.reply_text(
                    "❌ Добавление вложенных вариантов отменено",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('selecting_parent_option', None)
                return ConversationHandler.END
            
            # Находим индекс выбранного родительского варианта
            parent_option_index = -1
            for i, opt in enumerate(current_options):
                if isinstance(opt, dict) and "text" in opt and opt["text"] == choice:
                    parent_option_index = i
                    logger.info(f"Найден родительский вариант с индексом {i}: {opt}")
                    break
                    
            if parent_option_index == -1:
                await update.message.reply_text(
                    f"❌ Вариант '{choice}' не найден. Пожалуйста, обновите список вопросов и попробуйте снова.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.error(f"Вариант '{choice}' не найден среди вариантов: {current_options}")
                return ConversationHandler.END
                
            # Сохраняем выбранный родительский вариант и его индекс
            context.user_data['editing_option'] = choice
            context.user_data['editing_option_index'] = parent_option_index
            context.user_data.pop('selecting_parent_option', None)
            
            # Получаем родительский вариант по индексу
            parent_option = current_options[parent_option_index]
            
            # Проверяем, что это словарь с полем text
            if not isinstance(parent_option, dict) or "text" not in parent_option:
                await update.message.reply_text(
                    f"❌ Ошибка: некорректный формат варианта",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('editing_option', None)
                context.user_data.pop('editing_option_index', None)
                context.user_data.pop('adding_sub_option', None)
                return ConversationHandler.END
            
            # Формируем сообщение с текущими вложенными вариантами
            sub_options_text = ""
            if parent_option.get("sub_options"):
                for i, sub_opt in enumerate(parent_option["sub_options"]):
                    sub_options_text += f"{i+1}. {sub_opt}\n"
            
            # Клавиатура с действиями для вложенных вариантов
            keyboard = [
                [KeyboardButton("➕ Добавить вложенный вариант")]
            ]
            
            # Показываем кнопку удаления только если есть что удалять
            if parent_option.get("sub_options"):
                keyboard.append([KeyboardButton("➖ Удалить вложенный вариант")])
                # Добавляем возможность сделать вложенные варианты свободными
                keyboard.append([KeyboardButton("✨ Сделать свободным")])
            # Если вложенных вариантов нет, также показываем кнопку "Сделать свободным"
            else:
                keyboard.append([KeyboardButton("✨ Сделать свободным")])
            
            keyboard.append([KeyboardButton("❌ Отмена")])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"Текущие вложенные варианты для '{choice}':\n\n{sub_options_text}\n"
                "Выберите действие:",
                reply_markup=reply_markup
            )
            return EDITING_SUB_OPTIONS
        
        # Обработка действий с вложенными вариантами
        if 'editing_option' in context.user_data:
            parent_option_text = context.user_data['editing_option']
            
            # Находим родительский вариант
            parent_option = None
            parent_index = -1
            for i, opt in enumerate(current_options):
                if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                    parent_option = opt
                    parent_index = i
                    break
            
            if parent_option is None:
                await update.message.reply_text(
                    f"❌ Вариант '{parent_option_text}' не найден",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('editing_option', None)
                return ConversationHandler.END
            
            # Добавление нового вложенного варианта
            if choice == "➕ Добавить вложенный вариант" or choice == "✅ Да, добавить вложенные варианты" or choice == "➕ Добавить еще вложенный вариант":
                await update.message.reply_text(
                    f"Введите новый вложенный вариант для '{parent_option_text}':",
                    reply_markup=ReplyKeyboardRemove()
                )
                context.user_data['adding_sub_option'] = True
                return ADDING_SUB_OPTION
            
            # Продолжение после добавления вложенного варианта
            elif choice == "✅ Готово":
                await update.message.reply_text(
                    "✅ Редактирование вложенных вариантов завершено",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('editing_option', None)
                return ConversationHandler.END
            
            # Очистка вложенных вариантов (сделать свободным)
            elif choice == "✨ Сделать свободным":
                # Получаем родительский вариант по индексу
                parent_option_index = context.user_data['editing_option_index']
                
                # Проверяем, что индекс в допустимом диапазоне
                if parent_option_index < 0 or parent_option_index >= len(current_options):
                    await update.message.reply_text(
                        f"❌ Ошибка: некорректный индекс варианта {parent_option_index}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    # Очищаем состояние
                    context.user_data.pop('editing_option', None)
                    context.user_data.pop('editing_option_index', None)
                    return ConversationHandler.END
                
                # Получаем родительский вариант по индексу
                parent_option = current_options[parent_option_index]
                parent_option_text = parent_option["text"]
                
                # Очищаем список вложенных вариантов
                parent_option["sub_options"] = []
                
                # Обновляем варианты ответов
                success = self.sheets.edit_question_options(question_num, current_options)
                
                if success:
                    # Обновляем список вопросов
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    
                    await update.message.reply_text(
                        f"✅ Вложенные варианты для '{parent_option_text}' удалены. Теперь это свободный ответ.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
                    # Обновляем списки вопросов в других обработчиках
                    await self._update_handlers_questions(update)
                    
                    # Очищаем состояние
                    context.user_data.pop('editing_option', None)
                    context.user_data.pop('editing_option_index', None)
                    context.user_data.pop('adding_sub_option', None)
                    return ConversationHandler.END
                else:
                    await update.message.reply_text(
                        "❌ Не удалось обновить вложенные варианты ответов",
                        reply_markup=ReplyKeyboardRemove()
                    )
                
                # Очищаем состояние
                context.user_data.pop('editing_option', None)
                context.user_data.pop('editing_option_index', None)
                return ConversationHandler.END
            
            # Удаление вложенного варианта
            elif choice == "➖ Удалить вложенный вариант":
                sub_options = parent_option.get("sub_options", [])
                
                if not sub_options:
                    await update.message.reply_text(
                        f"❌ У варианта '{parent_option_text}' нет вложенных вариантов для удаления",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
                
                # Создаем клавиатуру с вложенными вариантами для удаления
                keyboard = [[KeyboardButton(sub_opt)] for sub_opt in sub_options]
                keyboard.append([KeyboardButton("❌ Отмена")])
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                await update.message.reply_text(
                    f"Выберите вложенный вариант для удаления из '{parent_option_text}':",
                    reply_markup=reply_markup
                )
                context.user_data['removing_sub_option'] = True
                return REMOVING_SUB_OPTION
            
            # Отмена редактирования вложенных вариантов
            elif choice == "❌ Отмена" or choice == "❌ Нет, оставить как есть":
                await update.message.reply_text(
                    "❌ Редактирование вложенных вариантов отменено",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('editing_option', None)
                return ConversationHandler.END
            
            else:
                # Неизвестное действие
                await update.message.reply_text(
                    "❌ Неизвестное действие. Пожалуйста, выберите из меню.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        
        return ConversationHandler.END
    
    async def handle_add_sub_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка добавления вложенного варианта ответа"""
        new_sub_option = update.message.text
        logger.info(f"Получен новый вложенный вариант: {new_sub_option}")
        
        # Обработка кнопки "Готово"
        if new_sub_option == "✅ Готово":
            await update.message.reply_text(
                "✅ Редактирование вложенных вариантов завершено",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('editing_option', None)
            context.user_data.pop('editing_option_index', None)
            context.user_data.pop('adding_sub_option', None)
            return ConversationHandler.END
            
        # Обработка кнопки "Сделать свободным"
        if new_sub_option == "✨ Сделать свободным":
            if 'editing_option_index' not in context.user_data:
                await update.message.reply_text(
                    "❌ Ошибка: родительский вариант не выбран",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
                
            parent_option_text = context.user_data['editing_option']
            parent_option_index = context.user_data['editing_option_index']
            question = context.user_data['editing_question']
            question_num = context.user_data.get('editing_question_num', -1)
            
            # Обновляем список вариантов из базы данных перед обработкой
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            if question not in self.questions_with_options:
                await update.message.reply_text(
                    f"❌ Ошибка: вопрос '{question}' не найден в базе данных",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('editing_option', None)
                context.user_data.pop('editing_option_index', None)
                context.user_data.pop('adding_sub_option', None)
                return ConversationHandler.END
                
            current_options = self.questions_with_options[question]
            
            # Проверяем индекс и пытаемся найти родительский вариант
            if parent_option_index < 0 or parent_option_index >= len(current_options):
                # Пытаемся найти вариант по тексту
                parent_found = False
                for i, opt in enumerate(current_options):
                    if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                        parent_option_index = i
                        context.user_data['editing_option_index'] = i
                        parent_found = True
                        break
                        
                if not parent_found:
                    await update.message.reply_text(
                        f"❌ Ошибка: вариант '{parent_option_text}' не найден в актуальном списке",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    # Очищаем состояние
                    context.user_data.pop('editing_option', None)
                    context.user_data.pop('editing_option_index', None)
                    context.user_data.pop('adding_sub_option', None)
                    return ConversationHandler.END
            
            # Получаем родительский вариант по индексу
            parent_option = current_options[parent_option_index]
            
            # Очищаем список вложенных вариантов
            parent_option["sub_options"] = []
            
            # Обновляем варианты ответов
            success = self.sheets.edit_question_options(question_num, current_options)
            
            if success:
                # Обновляем список вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                await update.message.reply_text(
                    f"✅ Вложенный вариант добавлен: {new_sub_option}\n\n"
                    f"Текущие вложенные варианты для '{parent_option['text']}':\n"
                    f"{sub_options_text}\n"
                    "Хотите добавить еще вложенный вариант?",
                    reply_markup=reply_markup
                )
                
                # Обновляем списки вопросов в других обработчиках
                await self._update_handlers_questions(update)
            else:
                await update.message.reply_text(
                    "❌ Не удалось добавить вложенный вариант",
                    reply_markup=ReplyKeyboardRemove()
                )
                
            # Очищаем состояние
            context.user_data.pop('adding_sub_option', None)
            return ConversationHandler.END
            
        # Обработка кнопки "Добавить еще вложенный вариант"
        if new_sub_option == "➕ Добавить еще вложенный вариант":
            await update.message.reply_text(
                f"Введите новый вложенный вариант для '{context.user_data['editing_option']}':",
                reply_markup=ReplyKeyboardRemove()
            )
            return ADDING_SUB_OPTION
        
        if 'editing_option_index' not in context.user_data:
            await update.message.reply_text(
                "❌ Ошибка: родительский вариант не выбран",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        parent_option_text = context.user_data['editing_option']
        parent_option_index = context.user_data['editing_option_index']
        question = context.user_data['editing_question']
        question_num = context.user_data.get('editing_question_num', -1)
        
        # Обновляем список вариантов из базы данных перед обработкой
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        
        # Проверяем, что вопрос все еще существует
        if question not in self.questions_with_options:
            await update.message.reply_text(
                f"❌ Ошибка: вопрос '{question}' не найден в базе данных",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('editing_option', None)
            context.user_data.pop('editing_option_index', None)
            context.user_data.pop('adding_sub_option', None)
            return ConversationHandler.END
            
        current_options = self.questions_with_options[question]
        
        logger.info(f"Текущие варианты в handle_add_sub_option: {current_options}")
        logger.info(f"Поиск родительского варианта по индексу: {parent_option_index}")
        
        # Проверяем, что индекс в допустимом диапазоне
        if parent_option_index < 0 or parent_option_index >= len(current_options):
            logger.warning(f"Индекс {parent_option_index} выходит за пределы списка вариантов (размер: {len(current_options)})")
            
            # Пытаемся найти вариант по тексту
            parent_found = False
            for i, opt in enumerate(current_options):
                if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                    parent_option_index = i
                    context.user_data['editing_option_index'] = i
                    parent_found = True
                    logger.info(f"Найден родительский вариант по тексту: {opt}")
                    break
                    
            if not parent_found:
                await update.message.reply_text(
                    f"❌ Ошибка: вариант '{parent_option_text}' не найден в актуальном списке",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('editing_option', None)
                context.user_data.pop('editing_option_index', None)
                context.user_data.pop('adding_sub_option', None)
                return ConversationHandler.END
        
        # Получаем родительский вариант по индексу
        parent_option = current_options[parent_option_index]
        
        # Проверяем, что это словарь с полем text
        if not isinstance(parent_option, dict) or "text" not in parent_option:
            await update.message.reply_text(
                f"❌ Ошибка: некорректный формат варианта",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('editing_option', None)
            context.user_data.pop('editing_option_index', None)
            context.user_data.pop('adding_sub_option', None)
            return ConversationHandler.END
        
        # Добавляем новый вложенный вариант
        if "sub_options" not in parent_option:
            parent_option["sub_options"] = []
        
        # Проверяем, что такого варианта еще нет
        if new_sub_option in parent_option["sub_options"]:
            await update.message.reply_text(
                f"❌ Вложенный вариант '{new_sub_option}' уже существует",
                reply_markup=ReplyKeyboardRemove()
            )
            # Возвращаемся к редактированию вложенных вариантов
            return await self.handle_sub_options_edit(update, context)
        
        # Добавляем новый подвариант
        parent_option["sub_options"].append(new_sub_option)
        
        # Обновляем варианты ответов
        success = self.sheets.edit_question_options(question_num, current_options)
        
        if success:
            # Обновляем список вопросов
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            # Спрашиваем, нужно ли добавить еще вложенные варианты
            keyboard = [
                [KeyboardButton("➕ Добавить еще вложенный вариант")],
                [KeyboardButton("✅ Готово")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            # Получаем обновленные варианты
            current_options = self.questions_with_options[question]
            
            # Убеждаемся, что индекс все еще валиден
            if parent_option_index < len(current_options):
                parent_option = current_options[parent_option_index]
                
                # Отображаем все вложенные варианты с нумерацией
                sub_options_text = ""
                if parent_option.get("sub_options"):
                    for i, sub_opt in enumerate(parent_option["sub_options"]):
                        sub_options_text += f"{i+1}. {sub_opt}\n"
                
                await update.message.reply_text(
                    f"✅ Вложенный вариант добавлен: {new_sub_option}\n\n"
                    f"Текущие вложенные варианты для '{parent_option['text']}':\n"
                    f"{sub_options_text}\n"
                    "Хотите добавить еще вложенный вариант?",
                    reply_markup=reply_markup
                )
                
                # Обновляем списки вопросов в других обработчиках
                await self._update_handlers_questions(update)
            else:
                await update.message.reply_text(
                    "❌ Ошибка: индекс родительского варианта стал недействительным",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('adding_sub_option', None)
                return ConversationHandler.END
        else:
            await update.message.reply_text(
                "❌ Не удалось добавить вложенный вариант",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('adding_sub_option', None)
            return ConversationHandler.END
    
    async def handle_remove_sub_option(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка удаления вложенного варианта ответа"""
        choice = update.message.text
        logger.info(f"Выбран вложенный вариант для удаления: {choice}")
        
        if choice == "❌ Отмена":
            await update.message.reply_text(
                "❌ Удаление вложенного варианта отменено",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('removing_sub_option', None)
            return ConversationHandler.END
        
        if 'editing_option_index' not in context.user_data:
            await update.message.reply_text(
                "❌ Ошибка: родительский вариант не выбран",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        parent_option_index = context.user_data['editing_option_index']
        question = context.user_data['editing_question']
        question_num = context.user_data.get('editing_question_num', -1)
        
        # Обновляем список вариантов из базы данных перед обработкой
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        
        # Проверяем, что вопрос все еще существует
        if question not in self.questions_with_options:
            await update.message.reply_text(
                f"❌ Ошибка: вопрос '{question}' не найден в базе данных",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('editing_option', None)
            context.user_data.pop('editing_option_index', None)
            context.user_data.pop('removing_sub_option', None)
            return ConversationHandler.END
            
        current_options = self.questions_with_options[question]
        
        logger.info(f"Текущие варианты в handle_remove_sub_option: {current_options}")
        logger.info(f"Индекс родительского варианта: {parent_option_index}")
        
        # Проверяем, что индекс в допустимом диапазоне
        if parent_option_index < 0 or parent_option_index >= len(current_options):
            await update.message.reply_text(
                f"❌ Ошибка: некорректный индекс варианта {parent_option_index}",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('editing_option', None)
            context.user_data.pop('editing_option_index', None)
            context.user_data.pop('removing_sub_option', None)
            return ConversationHandler.END
        
        # Получаем родительский вариант по индексу
        parent_option = current_options[parent_option_index]
        
        # Проверяем, что это словарь с полем text и sub_options
        if not isinstance(parent_option, dict) or "text" not in parent_option or "sub_options" not in parent_option:
            await update.message.reply_text(
                f"❌ Ошибка: некорректный формат варианта",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('editing_option', None)
            context.user_data.pop('editing_option_index', None)
            context.user_data.pop('removing_sub_option', None)
            return ConversationHandler.END
        
        # Удаляем выбранный вложенный вариант
        if choice in parent_option["sub_options"]:
            parent_option["sub_options"].remove(choice)
            
            # Обновляем варианты ответов
            success = self.sheets.edit_question_options(question_num, current_options)
            
            if success:
                # Обновляем список вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                # Очищаем состояние удаления
                context.user_data.pop('removing_sub_option', None)
                
                # Показываем сообщение об успешном удалении
                await update.message.reply_text(
                    f"✅ Подвариант '{choice}' успешно удален.",
                    reply_markup=ReplyKeyboardRemove()
                )
                
                # Обновляем списки вопросов в других обработчиках
                await self._update_handlers_questions(update)
            else:
                await update.message.reply_text(
                    "❌ Не удалось удалить подвариант.",
                    reply_markup=ReplyKeyboardRemove()
                )
        else:
            await update.message.reply_text(
                f"❌ Вложенный вариант '{choice}' не найден",
                reply_markup=ReplyKeyboardRemove()
            )
        
        # Очищаем состояние
        context.user_data.pop('removing_sub_option', None)
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
                "Удаление вопроса отменено.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        try:
            # Извлекаем номер вопроса из строки формата "5. тест"
            import re
            match = re.match(r'^(\d+)\.', choice)
            if match:
                question_num = int(match.group(1)) - 1  # Преобразуем выбор в индекс массива (начинающийся с 0)
            else:
                # Если формат не соответствует ожидаемому, попробуем преобразовать всё как число
                question_num = int(choice) - 1
                
            logger.info(f"Полученный номер вопроса: {question_num}")
            
            if 0 <= question_num < len(self.questions):
                question_to_delete = self.questions[question_num]
                
                # Запоминаем количество вопросов до удаления
                old_questions = self.questions.copy()
                logger.info(f"Вопросов до удаления: {len(old_questions)}")
                
                # Удаляем вопрос
                success = self.sheets.delete_question(question_num)
                
                if success:
                    # Сразу обновляем локальные списки вопросов
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    logger.info(f"Вопросов после удаления: {len(self.questions)}")
                    
                    # Обновляем списки вопросов во всех обработчиках через AdminHandler
                    await self._update_handlers_questions(update)
                    
                    # Принудительное обновление через application
                    if self.application:
                        # Обходим все группы обработчиков
                        for group_idx, group in enumerate(self.application.handlers):
                            # Проверяем, что group является итерируемым объектом
                            if not isinstance(group, (list, tuple)) or isinstance(group, (str, bytes, int)):
                                logger.warning(f"Группа с индексом {group_idx} не является списком: {type(group)}")
                                continue
                            
                            for handler in group:
                                if isinstance(handler, ConversationHandler) and hasattr(handler, 'name'):
                                    logger.info(f"Найден обработчик: {handler.name}")
                                    if hasattr(handler, 'entry_points'):
                                        for entry_point in handler.entry_points:
                                            if hasattr(entry_point.callback, '__self__'):
                                                handler_instance = entry_point.callback.__self__
                                                if hasattr(handler_instance, 'questions') and hasattr(handler_instance, 'questions_with_options'):
                                                    # Обновляем списки вопросов
                                                    old_len = len(handler_instance.questions) if hasattr(handler_instance, 'questions') else 0
                                                    handler_instance.questions_with_options = self.sheets.get_questions_with_options()
                                                    handler_instance.questions = list(handler_instance.questions_with_options.keys())
                                                    new_len = len(handler_instance.questions)
                                                    logger.info(f"Принудительно обновлены списки вопросов в {handler_instance.__class__.__name__} (группа {group_idx}). Было: {old_len}, стало: {new_len}")
                    
                    await update.message.reply_text(
                        f"✅ Вопрос успешно удален:\n{question_to_delete}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
                    # Дополнительная проверка, что список вопросов обновлен и во всех обработчиках
                    logger.info(f"Проверка успешного обновления списков вопросов после удаления")
                    for group_idx, group in enumerate(self.application.handlers):
                        # Проверяем, что group является итерируемым объектом
                        if not isinstance(group, (list, tuple)) or isinstance(group, (str, bytes, int)):
                            continue
                            
                        for handler in group:
                            if isinstance(handler, CommandHandler) and hasattr(handler.callback, '__name__') and handler.callback.__name__ == "list_questions":
                                list_questions_handler = handler.callback.__self__
                                if hasattr(list_questions_handler, 'questions'):
                                    logger.info(f"После удаления в list_questions: {len(list_questions_handler.questions)} вопросов")
                    
                    logger.info(f"Удаление вопроса успешно завершено. Осталось вопросов: {len(self.questions)}")
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
        except ValueError as e:
            await update.message.reply_text(
                "❌ Не удалось распознать номер вопроса. Пожалуйста, выберите вопрос из списка.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.error(f"Не удалось преобразовать выбор в число: {choice}. Ошибка: {e}")
            return ConversationHandler.END

    async def _update_handlers_questions(self, update: Update):
        """Вызывает обновление списков вопросов в других обработчиках через AdminHandler"""
        try:
            if not self.application:
                logger.error("Application не найден для обновления обработчиков")
                return

            # Обновляем свои списки вопросов
            old_questions_count = len(self.questions)
            logger.info(f"Начинаем обновление списков вопросов в обработчиках. Текущее количество: {old_questions_count}")
            
            # Получаем обновленные списки вопросов
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            logger.info(f"Локальный список вопросов обновлен в EditHandler. Было: {old_questions_count}, стало: {len(self.questions)}")
            
            # Флаг для отслеживания обновления list_questions
            list_questions_handler_updated = False
            
            # Поиск AdminHandler для вызова его метода _update_handlers_questions
            admin_handler = None
            for group_idx, group in enumerate(self.application.handlers):
                # Проверяем, что group является итерируемым объектом
                if not isinstance(group, (list, tuple)) or isinstance(group, (str, bytes, int)):
                    logger.warning(f"Группа с индексом {group_idx} не является списком: {type(group)}")
                    continue
                    
                for handler in group:
                    # Проверяем, не является ли это CommandHandler для команды list_questions
                    if isinstance(handler, CommandHandler) and hasattr(handler.callback, '__name__') and handler.callback.__name__ == "list_questions":
                        logger.info(f"Найден обработчик для команды list_questions в группе {group_idx}")
                        list_questions_handler = handler.callback.__self__
                        if hasattr(list_questions_handler, 'questions'):
                            old_len = len(list_questions_handler.questions)
                            list_questions_handler.questions_with_options = self.sheets.get_questions_with_options()
                            list_questions_handler.questions = list(list_questions_handler.questions_with_options.keys())
                            logger.info(f"Обновлен список вопросов для команды list_questions. Было: {old_len}, стало: {len(list_questions_handler.questions)}")
                            list_questions_handler_updated = True
                    
                    if isinstance(handler, ConversationHandler) and hasattr(handler, 'name') and handler.name == "add_question_conversation":
                        for entry_point in handler.entry_points:
                            if hasattr(entry_point.callback, '__self__'):
                                handler_instance = entry_point.callback.__self__
                                if handler_instance.__class__.__name__ == "AdminHandler":
                                    admin_handler = handler_instance
                                    logger.info(f"Найден AdminHandler для обновления списков вопросов")
                                    break
                        if admin_handler:
                            break
                if admin_handler:
                    break
            
            # Вызываем обновление списков вопросов в обработчиках через AdminHandler
            if admin_handler and hasattr(admin_handler, '_update_handlers_questions'):
                logger.info(f"Вызываем _update_handlers_questions в AdminHandler")
                await admin_handler._update_handlers_questions(update)
                logger.info(f"Списки вопросов успешно обновлены через AdminHandler")
            else:
                logger.warning(f"AdminHandler не найден, выполняем принудительное обновление обработчиков")
                # Принудительное обновление всех обработчиков
                for group_idx, group in enumerate(self.application.handlers):
                    # Проверяем, что group является итерируемым объектом
                    if not isinstance(group, (list, tuple)) or isinstance(group, (str, bytes, int)):
                        logger.warning(f"Группа с индексом {group_idx} не является списком: {type(group)}")
                        continue
                        
                    for handler in group:
                        # Проверяем, не является ли это CommandHandler для команды list_questions, если его ещё не обновили
                        if not list_questions_handler_updated and isinstance(handler, CommandHandler) and hasattr(handler.callback, '__name__') and handler.callback.__name__ == "list_questions":
                            logger.info(f"Найден обработчик для команды list_questions в группе {group_idx} при принудительном обновлении")
                            list_questions_handler = handler.callback.__self__
                            if hasattr(list_questions_handler, 'questions'):
                                old_len = len(list_questions_handler.questions)
                                list_questions_handler.questions_with_options = self.sheets.get_questions_with_options()
                                list_questions_handler.questions = list(list_questions_handler.questions_with_options.keys())
                                logger.info(f"Обновлен список вопросов для команды list_questions. Было: {old_len}, стало: {len(list_questions_handler.questions)}")
                                list_questions_handler_updated = True
                        
                        if isinstance(handler, ConversationHandler) and hasattr(handler, 'entry_points'):
                            for entry_point in handler.entry_points:
                                if hasattr(entry_point.callback, '__self__'):
                                    handler_instance = entry_point.callback.__self__
                                    if hasattr(handler_instance, 'questions') and hasattr(handler_instance, 'questions_with_options'):
                                        old_len = len(handler_instance.questions) if hasattr(handler_instance, 'questions') else 0
                                        handler_instance.questions_with_options = self.sheets.get_questions_with_options()
                                        handler_instance.questions = list(handler_instance.questions_with_options.keys())
                                        new_len = len(handler_instance.questions)
                                        logger.info(f"Принудительно обновлены списки вопросов в {handler_instance.__class__.__name__} (группа {group_idx}). Было: {old_len}, стало: {new_len}")
            
            # Проверяем, был ли обновлен обработчик list_questions
            if not list_questions_handler_updated:
                logger.warning("Обработчик команды list_questions не был найден или не обновлен")
                
            logger.info(f"Процесс обновления списков вопросов в обработчиках завершен успешно")
        except Exception as e:
            logger.error(f"Ошибка при обновлении списков вопросов: {e}")
            logger.exception(e) 