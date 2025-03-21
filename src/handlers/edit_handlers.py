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
        if 'editing_option' in context.user_data:
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
            new_options = current_options + [new_option]
            
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
                
                await update.message.reply_text(
                    f"✅ Вариант ответа добавлен: {choice}\n\n"
                    "Хотите добавить к нему вложенные варианты ответов?",
                    reply_markup=reply_markup
                )
                
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
        current_options = self.questions_with_options[question]
        
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
            
            # Сохраняем выбранный родительский вариант
            context.user_data['editing_option'] = choice
            context.user_data.pop('selecting_parent_option', None)
            
            # Отображаем существующие вложенные варианты или предлагаем добавить новые
            parent_option = None
            for opt in current_options:
                if isinstance(opt, dict) and "text" in opt and opt["text"] == choice:
                    parent_option = opt
                    break
            
            if parent_option:
                sub_options = parent_option.get("sub_options", [])
                
                # Формируем сообщение с текущими вложенными вариантами
                sub_options_text = ""
                if sub_options:
                    for i, sub_opt in enumerate(sub_options):
                        sub_options_text += f"{i+1}. {sub_opt}\n"
                    sub_options_text = f"Текущие вложенные варианты для '{choice}':\n\n{sub_options_text}\n"
                else:
                    sub_options_text = f"У варианта '{choice}' пока нет вложенных вариантов.\n\n"
                
                # Клавиатура с действиями для вложенных вариантов
                keyboard = [
                    [KeyboardButton("➕ Добавить вложенный вариант")]
                ]
                
                # Показываем кнопку удаления только если есть что удалять
                if sub_options:
                    keyboard.append([KeyboardButton("➖ Удалить вложенный вариант")])
                
                keyboard.append([KeyboardButton("❌ Отмена")])
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                await update.message.reply_text(
                    f"{sub_options_text}Выберите действие:",
                    reply_markup=reply_markup
                )
                return EDITING_SUB_OPTIONS
            else:
                await update.message.reply_text(
                    f"❌ Вариант '{choice}' не найден",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        
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
        
        if 'editing_option' not in context.user_data:
            await update.message.reply_text(
                "❌ Ошибка: родительский вариант не выбран",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        parent_option_text = context.user_data['editing_option']
        question = context.user_data['editing_question']
        question_num = context.user_data.get('editing_question_num', -1)
        current_options = self.questions_with_options[question]
        
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
            
            # Формируем сообщение с текущими вложенными вариантами
            parent_option = None
            for opt in self.questions_with_options[question]:
                if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                    parent_option = opt
                    break
            
            # Отображаем все вложенные варианты с нумерацией
            sub_options_text = ""
            if parent_option and parent_option.get("sub_options"):
                for i, sub_opt in enumerate(parent_option["sub_options"]):
                    sub_options_text += f"{i+1}. {sub_opt}\n"
            
            await update.message.reply_text(
                f"✅ Вложенный вариант добавлен: {new_sub_option}\n\n"
                f"Текущие вложенные варианты для '{parent_option_text}':\n"
                f"{sub_options_text}\n"
                "Хотите добавить еще вложенный вариант?",
                reply_markup=reply_markup
            )
            
            return EDITING_SUB_OPTIONS
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
        
        if 'editing_option' not in context.user_data:
            await update.message.reply_text(
                "❌ Ошибка: родительский вариант не выбран",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        parent_option_text = context.user_data['editing_option']
        question = context.user_data['editing_question']
        question_num = context.user_data.get('editing_question_num', -1)
        current_options = self.questions_with_options[question]
        
        # Находим родительский вариант
        parent_option = None
        for i, opt in enumerate(current_options):
            if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                parent_option = opt
                break
        
        if parent_option is None:
            await update.message.reply_text(
                f"❌ Вариант '{parent_option_text}' не найден",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('editing_option', None)
            context.user_data.pop('removing_sub_option', None)
            return ConversationHandler.END
        
        # Удаляем выбранный вложенный вариант
        if "sub_options" in parent_option and choice in parent_option["sub_options"]:
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
                    f"✅ Вложенный вариант удален: {choice}"
                )
                
                # Возвращаемся к редактированию подвариантов
                return await self.handle_sub_options_edit(update, context)
            else:
                await update.message.reply_text(
                    "❌ Не удалось удалить вложенный вариант",
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