"""
Обработчики для редактирования вопросов
"""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler

from models.states import *
from handlers.base_handler import BaseHandler
from utils.sheets import GoogleSheets
from utils.logger import get_logger

# Получаем логгер для модуля
logger = get_logger()

class EditHandler(BaseHandler):
    """Обработчики для редактирования вопросов"""
    
    def __init__(self, sheets: GoogleSheets, application=None):
        super().__init__(sheets)
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        self.application = application
    
    async def edit_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало редактирования вопроса"""
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Редактирование вопроса", "Начало процесса")
        
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
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Редактирование вопроса", "Выбор вопроса", details={"выбор": choice})
        
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
                logger.data_processing("вопросы", "Обработка выбора вопроса", details={"user_id": user_id})
                
                # Сохраняем выбранный вопрос
                selected_question = self.questions[question_num]
                context.user_data['editing_question'] = selected_question
                context.user_data['editing_question_num'] = question_num
                
                logger.admin_action(user_id, "Редактирование вопроса", "Выбран вопрос", 
                                  details={"вопрос": selected_question, "номер": question_num})
                
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
                logger.error("invalid_question_number", "Некорректный номер вопроса", 
                           details={"номер": question_num, "максимум": len(self.questions)-1}, 
                           user_id=user_id)
                await update.message.reply_text(
                    "❌ Некорректный номер вопроса. Пожалуйста, выберите из списка.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        except (ValueError, IndexError):
            logger.error("question_choice_processing_error", "Не удалось обработать выбор вопроса", 
                       details={"выбор": choice}, user_id=user_id)
            await update.message.reply_text(
                "❌ Пожалуйста, выберите вопрос из списка.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
    
    async def handle_edit_menu_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора действия в меню редактирования"""
        choice = update.message.text
        user_id = update.effective_user.id
        
        # Проверяем отмену
        if choice == "❌ Отмена":
            await update.message.reply_text(
                "❌ Редактирование отменено.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        logger.admin_action(user_id, "Выбор действия в меню редактирования", details={"выбор": choice})
        
        if 'editing_question' not in context.user_data:
            logger.error("editing_question_missing", "Вопрос не выбран в данных пользователя", 
                        user_id=user_id, details={"handler": "handle_edit_menu_choice"})
            await update.message.reply_text(
                "❌ Ошибка: вопрос не выбран",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        question = context.user_data['editing_question']
        logger.data_processing("Редактирование вопроса", details={"вопрос": question})
        
        # Получаем номер вопроса, если он есть
        question_num = context.user_data.get('editing_question_num')
        if question_num is None:
            # Если номера нет, находим его
            try:
                question_num = self.questions.index(question)
                context.user_data['editing_question_num'] = question_num
                logger.data_processing("вопросы", "Определение номера вопроса", details={"номер": question_num, "вопрос": question})
            except ValueError:
                logger.error("question_not_found", "Вопрос не найден в списке", 
                          user_id=user_id, details={"вопрос": question})
                question_num = -1
        
        # Проверяем наличие вариантов ответов
        has_options = bool(self.questions_with_options[question])
        logger.data_processing("Проверка вариантов ответов", details={"наличие_вариантов": has_options, "вопрос": question})
        
        if choice == "✏️ Изменить текст вопроса":
            logger.admin_action(user_id, "Выбор изменения текста вопроса", details={"вопрос": question})
            await update.message.reply_text(
                f"Текущий текст вопроса:\n{question}\n\n"
                "Введите новый текст вопроса:",
                reply_markup=ReplyKeyboardRemove()
            )
            return EDITING_QUESTION_TEXT
            
        elif choice == "🔄 Изменить варианты ответов":
            logger.admin_action(user_id, "Выбор изменения вариантов ответов", details={"вопрос": question})
            
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
                    if "sub_options" in opt:
                        if opt["sub_options"] == []:
                            options_text += " 📝 (свободный подответ)\n"
                        elif opt.get("sub_options"):
                            options_text += ":\n"
                            for sub_opt in opt["sub_options"]:
                                options_text += f"  ↳ {sub_opt}\n"
                        else:
                            options_text += "\n"
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
            logger.data_processing("вопросы", "Отображение меню редактирования вариантов", details={"вопрос": question})
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
        new_text = update.message.text.strip()
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Редактирование текста вопроса", details={"новый_текст": new_text})
        
        # Проверяем наличие необходимых данных
        if 'editing_question' not in context.user_data:
            logger.error("editing_question_missing", "Вопрос для редактирования не найден", 
                       user_id=user_id, details={"handler": "handle_question_text_edit"})
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
                logger.error("question_not_found", "Вопрос не найден в списке", 
                          user_id=user_id, details={"вопрос": old_question})
                await update.message.reply_text(
                    "❌ Ошибка: вопрос не найден в списке",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
                
        logger.data_processing("вопросы", "Редактирование текста вопроса", 
                          details={"старый_текст": old_question, "новый_текст": new_text, "user_id": user_id})
                
        # Редактируем текст вопроса
        success = self.sheets.edit_question_text(question_num, new_text)
        
        if success:
            # Обновляем список вопросов
            old_options = self.questions_with_options[old_question]
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            # Проверяем, что вопрос был обновлен
            if new_text in self.questions:
                logger.admin_action(user_id, "Обновление текста вопроса", 
                               details={"статус": "успешно", "старый": old_question, "новый": new_text})
                await update.message.reply_text(
                    f"✅ Текст вопроса успешно обновлен:\n"
                    f"Было: {old_question}\n"
                    f"Стало: {new_text}",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                logger.admin_action(user_id, "Обновление текста вопроса", 
                               details={"статус": "требуется перезагрузка", "старый": old_question, "новый": new_text})
                await update.message.reply_text(
                    "✅ Текст вопроса обновлен, но требуется перезагрузка бота для обновления списка вопросов.",
                    reply_markup=ReplyKeyboardRemove()
                )
        else:
            logger.error("question_update_failed", "Не удалось обновить текст вопроса", 
                      user_id=user_id, details={"вопрос": old_question, "новый_текст": new_text})
            await update.message.reply_text(
                "❌ Не удалось обновить текст вопроса",
                reply_markup=ReplyKeyboardRemove()
            )
        
        # Очищаем данные пользователя
        context.user_data.pop('editing_question', None)
        context.user_data.pop('editing_question_num', None)
        
        await self._update_handlers_questions(update)
        
        return ConversationHandler.END

    async def handle_options_edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка редактирования вариантов ответов"""
        choice = update.message.text
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Выбор действия с вариантами ответов", details={"действие": choice})
        
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
                logger.warning("question_not_found", "Вопрос не найден в актуальном списке вопросов", 
                            details={"вопрос": question, "user_id": update.effective_user.id})
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
            new_option = {"text": choice}
            
            # Получаем актуальные данные перед изменением
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            # Проверяем, что вопрос существует
            if question in self.questions_with_options:
                current_options = self.questions_with_options[question]
            else:
                logger.warning("question_not_found", "Вопрос не найден в списке", 
                            details={"вопрос": question, "user_id": update.effective_user.id})
                await update.message.reply_text(
                    "❌ Ошибка: вопрос не найден в актуальном списке",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем состояние
                context.user_data.pop('adding_option', None)
                return ConversationHandler.END
                
            # Добавляем новый вариант к существующим
            new_options = current_options + [new_option]
            
            logger.admin_action(update.effective_user.id, "Добавление варианта ответа", 
                             details={"вариант": choice, "текущие_варианты": str(current_options)})
            
            success = self.sheets.edit_question_options(question_num, new_options)
            
            if success:
                # Обновляем список вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                await update.message.reply_text(
                    f"✅ Вариант ответа добавлен: {choice}",
                    reply_markup=ReplyKeyboardRemove()
                )
                
                # Обновляем списки вопросов в других обработчиках
                await self._update_handlers_questions(update)
                
                # Очищаем состояние добавления обычного варианта
                context.user_data.pop('adding_option', None)
                return ConversationHandler.END
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
                logger.warning("question_not_found", "Вопрос не найден в списке", 
                            details={"вопрос": question, "user_id": update.effective_user.id})
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
                    if "sub_options" in opt:
                        if opt["sub_options"] == []:
                            options_text += " 📝 (свободный подответ)\n"
                        elif opt.get("sub_options"):
                            options_text += ":\n"
                            for sub_opt in opt["sub_options"]:
                                options_text += f"  ↳ {sub_opt}\n"
                        else:
                            options_text += "\n"
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
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Выбор действия для вложенных вариантов", details={"выбор": choice})
        
        if 'editing_question' not in context.user_data or 'editing_option' not in context.user_data:
            logger.error("editing_context_missing", "Отсутствует контекст редактирования", 
                       user_id=user_id, details={"context_keys": str(context.user_data.keys())})
            await update.message.reply_text(
                "❌ Ошибка: вопрос или вариант не выбраны",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        question = context.user_data['editing_question']
        parent_option_text = context.user_data['editing_option']
        
        # Получаем номер вопроса
        question_num = context.user_data.get('editing_question_num', -1)
        logger.data_processing("варианты", "Редактирование вложенных вариантов", 
                          details={"вопрос": question, "вариант": parent_option_text, 
                                 "индекс_вопроса": question_num, "user_id": user_id})
        
        # Получаем актуальные данные перед изменением
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        
        # Проверяем, что вопрос существует
        if question not in self.questions_with_options:
            logger.warning("question_not_found", "Вопрос не найден в актуальном списке вопросов", 
                        details={"вопрос": question, "user_id": update.effective_user.id})
            await update.message.reply_text(
                "❌ Ошибка: вопрос не найден в актуальном списке",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        current_options = self.questions_with_options[question]
        
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
        
        # Добавление вопроса для свободного ответа
        elif choice == "📝 Добавить вопрос для свободного ответа":
            parent_option_index = context.user_data.get('editing_option_index', -1)
            
            # Проверяем индекс или пытаемся найти родительский вариант по тексту
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
                    return ConversationHandler.END
            
            # Получаем родительский вариант
            parent_option = current_options[parent_option_index]
            
            # Проверяем, что это вариант со свободным ответом
            if not isinstance(parent_option.get("sub_options"), list) or parent_option.get("sub_options") != []:
                await update.message.reply_text(
                    f"❌ Ошибка: вариант '{parent_option_text}' не является свободным ответом",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
            
            # Получаем текущий вопрос для свободного ответа, если он есть
            current_prompt = parent_option.get("free_text_prompt", "")
            
            await update.message.reply_text(
                f"Введите вопрос, который будет показан пользователю при выборе варианта '{parent_option_text}':\n\n"
                f"Текущий вопрос: {current_prompt if current_prompt else 'Не задан'}",
                reply_markup=ReplyKeyboardRemove()
            )
            return ADDING_FREE_TEXT_PROMPT
        
        # Отмена редактирования
        elif choice == "❌ Отмена":
            await update.message.reply_text(
                "❌ Редактирование вложенных вариантов отменено",
                reply_markup=ReplyKeyboardRemove()
            )
            # Очищаем состояние
            context.user_data.pop('editing_option', None)
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
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Добавление вложенного варианта", details={"вариант": new_sub_option})
        
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
                    else:
                        sub_options_text = "Нет вложенных вариантов"
                
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
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Выбор вложенного варианта для удаления", details={"вариант": choice})
        
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
            logger.warning("question_not_found", "Вопрос не найден в актуальном списке вопросов", 
                         details={"вопрос": question, "user_id": update.effective_user.id,
                                 "действие": "Прерывание удаления вопроса"})
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
        
        logger.data_processing("варианты", "Анализ вариантов ответов", details={"user_id": user_id})
        
        
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

    async def handle_add_free_text_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка добавления вопроса для свободного ответа"""
        prompt = update.message.text
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Добавление вопроса для свободного ответа", details={"текст_вопроса": prompt})
        
        if 'editing_question' not in context.user_data or 'editing_option' not in context.user_data:
            logger.error("editing_context_missing", "Отсутствует контекст редактирования", 
                       user_id=user_id, details={"handler": "handle_add_free_text_prompt"})
            await update.message.reply_text(
                "❌ Ошибка: вопрос или вариант не выбраны",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        question = context.user_data['editing_question']
        parent_option_text = context.user_data['editing_option']
        parent_option_index = context.user_data.get('editing_option_index', -1)
        
        # Получаем номер вопроса
        question_num = context.user_data.get('editing_question_num', -1)
        logger.data_processing("вопросы", "Добавление вопроса для свободного ответа", details={"user_id": user_id})
        
        # Получаем актуальные данные перед изменением
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        
        # Проверяем, что вопрос существует
        if question not in self.questions_with_options:
            logger.warning("question_not_found", "Вопрос не найден в актуальном списке вопросов", details={"вопрос": question, "user_id": update.effective_user.id})
            await update.message.reply_text(
                "❌ Ошибка: вопрос не найден в актуальном списке",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        current_options = self.questions_with_options[question]
        
        # Проверяем, что вариант существует и находим его
        parent_found = False
        for i, opt in enumerate(current_options):
            if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                parent_option_index = i
                context.user_data['editing_option_index']
                parent_found = True
                break
                
        if not parent_found:
            await update.message.reply_text(
                f"❌ Ошибка: вариант '{parent_option_text}' не найден в актуальном списке",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Получаем родительский вариант
        parent_option = current_options[parent_option_index]
        
        # Проверяем, что это вариант со свободным ответом
        if not isinstance(parent_option.get("sub_options"), list) or parent_option.get("sub_options") != []:
            await update.message.reply_text(
                f"❌ Ошибка: вариант '{parent_option_text}' не является свободным ответом",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Добавляем поле free_text_prompt к родительскому варианту
        parent_option["free_text_prompt"] = prompt
        
        # Обновляем варианты ответов
        success = self.sheets.edit_question_options(question_num, current_options)
        
        if success:
            # Обновляем список вопросов
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            await update.message.reply_text(
                f"✅ Вопрос для свободного ответа добавлен: '{prompt}'",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Обновляем списки вопросов в других обработчиках
            await self._update_handlers_questions(update)
        else:
            await update.message.reply_text(
                "❌ Не удалось добавить вопрос для свободного ответа",
                reply_markup=ReplyKeyboardRemove()
            )
            
        # Очищаем состояние
        context.user_data.pop('editing_option', None)
        context.user_data.pop('editing_option_index', None)
        return ConversationHandler.END

    async def delete_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало удаления вопроса"""
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Удаление вопроса", "Начало процесса")
        
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
        user_id = update.effective_user.id
        logger.admin_action(user_id, "Удаление вопроса", "Выбор вопроса", details={"выбор": choice})
        
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
                
            logger.data_processing("вопросы", "Обработка выбора вопроса для удаления", details={"user_id": user_id})
            
            if 0 <= question_num < len(self.questions):
                question_to_delete = self.questions[question_num]
                
                # Запоминаем количество вопросов до удаления
                old_questions = self.questions.copy()
                logger.data_processing("вопросы", "Удаление вопроса", details={"начало": True, "вопрос": question_to_delete})
                
                # Удаляем вопрос
                success = self.sheets.delete_question(question_num)
                
                if success:
                    # Сразу обновляем локальные списки вопросов
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    logger.data_processing("вопросы", "Удаление вопроса", details={"успех": True, "вопрос": question_to_delete})
                    
                    # Обновляем списки вопросов во всех обработчиках через AdminHandler
                    await self._update_handlers_questions(update)
                    
                    # Принудительное обновление через application
                    if self.application:
                        # Обходим все группы обработчиков
                        for group_idx, group in enumerate(self.application.handlers):
                            # Проверяем, что group является итерируемым объектом
                            if not isinstance(group, (list, tuple)) or isinstance(group, (str, bytes, int)):
                                logger.warning("invalid_handler_group", "Группа обработчиков не является списком", 
                                          details={"индекс": group_idx, "тип": str(type(group))})
                                continue
                            
                            for handler in group:
                                if isinstance(handler, ConversationHandler) and hasattr(handler, 'name'):
                                    logger.data_processing("Обновление обработчиков", "Найден обработчик", 
                                                       details={"имя_обработчика": handler.name,
                                                              "user_id": update.effective_user.id})
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
                                                    
                                                    logger.data_processing("Обновление обработчиков", "Принудительное обновление", 
                                                                      details={"обработчик": handler_instance.__class__.__name__,
                                                                             "группа": group_idx,
                                                                             "вопросов_было": old_len,
                                                                             "вопросов_стало": new_len,
                                                                             "user_id": update.effective_user.id})
                    
                    await update.message.reply_text(
                        f"✅ Вопрос успешно удален:\n{question_to_delete}",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
                    # Дополнительная проверка, что список вопросов обновлен и во всех обработчиках
                    logger.data_processing("Обновление обработчиков", "Проверка синхронизации", 
                                        details={"операция": "Удаление вопроса", 
                                               "вопрос": question_to_delete,
                                               "user_id": update.effective_user.id})
                    for group_idx, group in enumerate(self.application.handlers):
                        # Проверяем, что group является итерируемым объектом
                        if not isinstance(group, (list, tuple)) or isinstance(group, (str, bytes, int)):
                            continue
                            
                        for handler in group:
                            if isinstance(handler, CommandHandler) and hasattr(handler.callback, '__name__') and handler.callback.__name__ == "list_questions":
                                list_questions_handler = handler.callback.__self__
                                if hasattr(list_questions_handler, 'questions'):
                                    logger.data_processing("Синхронизация обработчиков", "Состояние list_questions", 
                                                       details={"количество_вопросов": len(list_questions_handler.questions),
                                                              "обработчик": "list_questions_handler", 
                                                              "user_id": update.effective_user.id})
                    
                    logger.admin_action(update.effective_user.id, "Удаление вопроса", "Завершено", 
                                     details={"вопрос": question_to_delete, 
                                            "осталось_вопросов": len(self.questions)})
                else:
                    await update.message.reply_text(
                        "❌ Не удалось удалить вопрос. Пожалуйста, попробуйте позже.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    logger.error("question_delete_failed", "Не удалось удалить вопрос", 
                                details={"номер_вопроса": question_num, "user_id": update.effective_user.id})
                
                return ConversationHandler.END
            else:
                await update.message.reply_text(
                    "❌ Некорректный номер вопроса. Пожалуйста, выберите из списка.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.error("invalid_question_number", "Некорректный номер вопроса", 
                            details={"номер_вопроса": question_num, "user_id": update.effective_user.id})
                return ConversationHandler.END
        except ValueError as e:
            await update.message.reply_text(
                "❌ Не удалось распознать номер вопроса. Пожалуйста, выберите вопрос из списка.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.error("value_conversion_error", "Не удалось преобразовать выбор в число", 
                        details={"текст": choice, "ошибка": str(e), "user_id": update.effective_user.id})
            return ConversationHandler.END

    async def _update_handlers_questions(self, update: Update):
        """Вызывает обновление списков вопросов в других обработчиках через AdminHandler"""
        try:
            if not self.application:
                logger.error("application_missing", "Application не найден для обновления обработчиков", 
                            details={"причина": "Компонент не был передан при инициализации"})
                return

            # Обновляем свои списки вопросов
            old_questions_count = len(self.questions)
            logger.data_processing("Обновление обработчиков", "Начало обновления списков вопросов", 
                                details={"текущее_количество": old_questions_count,
                                       "user_id": update.effective_user.id if update else "system"})
            
            # Получаем обновленные списки вопросов
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            logger.data_processing("Обновление обработчиков", "Локальное обновление", 
                                details={"модуль": "EditHandler", 
                                       "вопросов_было": old_questions_count, 
                                       "вопросов_стало": len(self.questions),
                                       "user_id": update.effective_user.id if update else "system"})
            
            # Флаг для отслеживания обновления list_questions
            list_questions_handler_updated = False
            admin_handler = None
            
            # Перебираем все группы обработчиков в application
            for group in self.application.handlers.values():
                if not isinstance(group, list):
                    continue
                
                for handler in group:
                    # Ищем AdminHandler
                    if hasattr(handler, 'callback') and hasattr(handler.callback, '__self__'):
                        handler_instance = handler.callback.__self__
                        if handler_instance.__class__.__name__ == "AdminHandler":
                            admin_handler = handler_instance
                            logger.data_processing("Обновление обработчиков", "Найден AdminHandler", 
                                               details={"обработчик": str(handler),
                                                      "user_id": update.effective_user.id if update else "system"})
                            break
                    
                    # Ищем ConversationHandler с именем add_question_conversation
                    if isinstance(handler, ConversationHandler) and hasattr(handler, 'name') and handler.name == "add_question_conversation":
                        for entry_point in handler.entry_points:
                            if hasattr(entry_point.callback, '__self__'):
                                handler_instance = entry_point.callback.__self__
                                if handler_instance.__class__.__name__ == "AdminHandler":
                                    admin_handler = handler_instance
                                    logger.data_processing("Обновление обработчиков", "Найден AdminHandler", 
                                                       details={"через": "ConversationHandler",
                                                              "user_id": update.effective_user.id if update else "system"})
                                    break
                    
                    # Ищем CommandHandler для команды list_questions
                    if isinstance(handler, CommandHandler) and hasattr(handler.callback, '__name__') and handler.callback.__name__ == "list_questions":
                        list_questions_handler = handler.callback.__self__
                        if hasattr(list_questions_handler, 'questions'):
                            old_len = len(list_questions_handler.questions)
                            list_questions_handler.questions_with_options = self.sheets.get_questions_with_options()
                            list_questions_handler.questions = list(list_questions_handler.questions_with_options.keys())
                            
                            list_questions_handler_updated = True
                
                if admin_handler:
                    break
            
            # Вызываем обновление списков вопросов в обработчиках через AdminHandler
            if admin_handler and hasattr(admin_handler, '_update_handlers_questions'):
                logger.data_processing("Обновление обработчиков", "Делегирование AdminHandler", 
                                    details={"метод": "_update_handlers_questions",
                                           "user_id": update.effective_user.id if update else "system"})
                await admin_handler._update_handlers_questions(update)
                logger.data_processing("Обновление обработчиков", "Завершено через AdminHandler",
                                    details={"статус": "успешно",
                                           "user_id": update.effective_user.id if update else "system"})
                return
                
            # Если AdminHandler не найден, выполняем принудительное обновление
            logger.warning("admin_handler_missing", "AdminHandler не найден", 
                         details={"действие": "Выполняем принудительное обновление обработчиков",
                                 "причина": "Компонент недоступен"})
            
            # Обновляем все обработчики напрямую
            updated_handlers = 0
            for group in self.application.handlers.values():
                if not isinstance(group, list):
                    continue
                    
                for handler in group:
                    handler_updated = False
                    
                    # Обновляем CommandHandler для list_questions, если ещё не обновлён
                    if not list_questions_handler_updated and isinstance(handler, CommandHandler) and hasattr(handler.callback, '__name__') and handler.callback.__name__ == "list_questions":
                        list_questions_handler = handler.callback.__self__
                        if hasattr(list_questions_handler, 'questions'):
                            old_len = len(list_questions_handler.questions)
                            list_questions_handler.questions_with_options = self.sheets.get_questions_with_options()
                            list_questions_handler.questions = list(list_questions_handler.questions_with_options.keys())
                            logger.data_processing("Обновление обработчиков", "Обновление list_questions", 
                                                details={"вопросов_было": old_len, 
                                                       "вопросов_стало": len(list_questions_handler.questions),
                                                       "user_id": update.effective_user.id if update else "system"})
                            list_questions_handler_updated = True
                            handler_updated = True
                            updated_handlers += 1
                    
                    # Обновляем все обработчики с атрибутами questions и questions_with_options
                    if isinstance(handler, ConversationHandler) and hasattr(handler, 'entry_points'):
                        for entry_point in handler.entry_points:
                            if hasattr(entry_point.callback, '__self__'):
                                handler_instance = entry_point.callback.__self__
                                if hasattr(handler_instance, 'questions') and hasattr(handler_instance, 'questions_with_options'):
                                    old_len = len(handler_instance.questions) if hasattr(handler_instance, 'questions') else 0
                                    handler_instance.questions_with_options = self.sheets.get_questions_with_options()
                                    handler_instance.questions = list(handler_instance.questions_with_options.keys())
                                    new_len = len(handler_instance.questions)
                                    
                                    handler_updated = True
                                    updated_handlers += 1
                    
                    # Обновляем другие обработчики напрямую
                    if hasattr(handler, 'callback') and hasattr(handler.callback, '__self__'):
                        handler_instance = handler.callback.__self__
                        if hasattr(handler_instance, 'questions') and hasattr(handler_instance, 'questions_with_options'):
                            old_len = len(handler_instance.questions) if hasattr(handler_instance, 'questions') else 0
                            handler_instance.questions_with_options = self.sheets.get_questions_with_options()
                            handler_instance.questions = list(handler_instance.questions_with_options.keys())
                            new_len = len(handler_instance.questions)
                            if not handler_updated:  # Избегаем повторного логирования
                                logger.data_processing("Обновление обработчиков", "Обновление списков вопросов", 
                                                    details={"обработчик": handler_instance.__class__.__name__,
                                                           "вопросов_было": old_len,
                                                           "вопросов_стало": new_len,
                                                           "user_id": update.effective_user.id if update else "system"})
                                updated_handlers += 1
            
            if updated_handlers > 0:
                logger.admin_action(update.effective_user.id, "Обновление обработчиков", 
                                  details={"успешно_обновлено": updated_handlers})
            else:
                logger.warning("handlers_update_empty", "Не найдено обработчиков для обновления", 
                             details={"причина": "Обработчики не зарегистрированы или недоступны"})
                
            # Проверяем, был ли обновлен обработчик list_questions
            if not list_questions_handler_updated:
                logger.warning("list_questions_not_updated", "Обработчик команды list_questions не обновлен", 
                             details={"причина": "Обработчик не найден или не привязан к приложению"})
                
            logger.admin_action(update.effective_user.id, "Завершение обновления обработчиков", 
                              details={"успешно": True, "количество": updated_handlers})
        except Exception as e:
            logger.error("questions_update_error", "Ошибка при обновлении списков вопросов", 
                        details={"ошибка": str(e), "user_id": update.effective_user.id if update else "unknown"})
            logger.exception(e)