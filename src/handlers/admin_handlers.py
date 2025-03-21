"""
Обработчики для административных команд
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters

from models.states import *
from utils.sheets import GoogleSheets
from handlers.base_handler import BaseHandler
from utils.helpers import setup_commands  # Импортируем функцию setup_commands

# Настройка логирования
logger = logging.getLogger(__name__)

class AdminHandler(BaseHandler):
    """Обработчики для административных команд"""
    
    def __init__(self, sheets: GoogleSheets, application=None):
        super().__init__(sheets)
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        self.application = application  # Сохраняем application при инициализации

    async def list_questions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод списка вопросов"""
        logger.info(f"Пользователь {update.effective_user.id} запросил список вопросов")
        
        # Проверяем, есть ли вопросы
        if not self.questions:
            await update.message.reply_text(
                "❌ В данный момент нет доступных вопросов.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Формируем текст со списком вопросов
        questions_text = "📋 Список вопросов:\n\n"
        for i, question in enumerate(self.questions):
            options = self.questions_with_options[question]
            
            # Формируем читаемый список вариантов ответов
            if options:
                options_list = []
                for opt in options:
                    if isinstance(opt, dict) and "text" in opt:
                        option_text = opt["text"]
                        # Добавляем информацию о подвариантах
                        if "sub_options" in opt and opt["sub_options"]:
                            sub_count = len(opt["sub_options"])
                            option_text += f" (+{sub_count} подварианта)"
                        options_list.append(option_text)
                    else:
                        # Для обратной совместимости
                        options_list.append(str(opt))
                
                options_text = ", ".join(options_list)
            else:
                options_text = "Свободный ответ"
            
            questions_text += f"{i+1}. {question}\n   Варианты: {options_text}\n\n"
        
        # Отправляем список вопросов
        await update.message.reply_text(
            questions_text,
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ConversationHandler.END
    
    async def add_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало добавления нового вопроса"""
        logger.info(f"Пользователь {update.effective_user.id} начал добавление вопроса")
        
        # Очищаем данные пользователя
        context.user_data.clear()
        
        # Запрашиваем текст вопроса
        await update.message.reply_text(
            "Введите текст нового вопроса:",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ADDING_QUESTION
    
    async def handle_new_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текста нового вопроса"""
        question_text = update.message.text
        logger.info(f"Получен текст нового вопроса: {question_text}")
        
        # Сохраняем текст вопроса
        context.user_data['new_question'] = question_text
        
        # Спрашиваем о вариантах ответов
        keyboard = [
            [KeyboardButton("✨ Свободный ответ")],
            [KeyboardButton("📝 Добавить варианты ответов")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"Вопрос: {question_text}\n\n"
            "Выберите тип ответа:",
            reply_markup=reply_markup
        )
        
        return CHOOSING_OPTIONS_TYPE
    
    async def handle_options_choice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка выбора типа ответов"""
        choice = update.message.text
        logger.info(f"Выбран тип ответов: {choice}")
        
        if choice == "✨ Свободный ответ":
            # Добавляем вопрос без вариантов ответов
            question = context.user_data['new_question']
            success = self.sheets.add_question(question, [])
            
            if success:
                # Обновляем списки вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                # Обновляем списки вопросов в других обработчиках через application
                await self._update_handlers_questions(update)
                
                await update.message.reply_text(
                    f"✅ Вопрос успешно добавлен:\n{question}\n\nТип: Свободный ответ",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "❌ Не удалось добавить вопрос",
                    reply_markup=ReplyKeyboardRemove()
                )
            return ConversationHandler.END
            
        elif choice == "📝 Добавить варианты ответов":
            # Инициализируем пустой список вариантов
            context.user_data['options'] = []
            
            # Запрашиваем первый вариант
            keyboard = [[KeyboardButton("Готово")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Введите первый вариант ответа:",
                reply_markup=reply_markup
            )
            
            return ADDING_OPTIONS
            
        else:
            # Неизвестный выбор
            await update.message.reply_text(
                "❌ Пожалуйста, выберите один из вариантов.",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("✨ Свободный ответ")],
                    [KeyboardButton("📝 Добавить варианты ответов")]
                ], resize_keyboard=True)
            )
            
            return CHOOSING_OPTIONS_TYPE
    
    async def handle_option_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода вариантов ответов"""
        choice = update.message.text.strip()
        logger.info(f"Получены варианты ответов: {choice}")
        
        # Проверяем наличие необходимых данных
        if 'new_question' not in context.user_data:
            await update.message.reply_text(
                "❌ Ошибка: вопрос не найден",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        question = context.user_data['new_question']
        
        if choice == "❌ Отмена":
            await update.message.reply_text(
                "❌ Добавление вопроса отменено",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Если выбрано "Готово", переходим к сохранению вопроса с вариантами
        if choice == "Готово":
            # Проверяем, есть ли варианты ответов
            options = context.user_data.get('options', [])
            if not options:
                await update.message.reply_text(
                    "❌ Не указано ни одного варианта ответа. Введите хотя бы один вариант или отмените добавление.",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("❌ Отмена")]
                    ], resize_keyboard=True)
                )
                return ADDING_OPTIONS
            
            # Добавляем вопрос с вариантами ответов
            success = self.sheets.add_question(question, options)
            
            if success:
                # Обновляем списки вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                # Обновляем списки вопросов в других обработчиках
                await self._update_handlers_questions(update)
                
                # Спрашиваем, нужно ли добавить вложенные варианты
                keyboard = [
                    [KeyboardButton("✅ Да, добавить вложенные варианты")],
                    [KeyboardButton("❌ Нет, оставить как есть")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                # Формируем список вариантов ответов для отображения
                options_display = "\n".join(f"• {opt['text']}" for opt in options)
                
                await update.message.reply_text(
                    f"✅ Вопрос успешно добавлен:\n{question}\n\nВарианты ответов:\n{options_display}\n\n"
                    "Хотите добавить вложенные варианты ответов к каким-либо из основных вариантов?",
                    reply_markup=reply_markup
                )
                
                return ADDING_NESTED_OPTIONS
            else:
                await update.message.reply_text(
                    "❌ Не удалось добавить вопрос",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        
        # Если был выбран свободный ответ
        if context.user_data.get('free_form'):
            # Добавляем вопрос без вариантов ответов
            success = self.sheets.add_question(question)
            
            if success:
                # Обновляем списки вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                # Обновляем списки вопросов в других обработчиках
                await self._update_handlers_questions(update)
                
                await update.message.reply_text(
                    f"✅ Вопрос со свободным ответом успешно добавлен:\n{question}",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "❌ Не удалось добавить вопрос",
                    reply_markup=ReplyKeyboardRemove()
                )
            
            # Очищаем состояние
            context.user_data.clear()
            return ConversationHandler.END
        
        # Добавляем вариант ответа в список
        if 'options' not in context.user_data:
            context.user_data['options'] = []
            
        # Добавляем новый вариант
        context.user_data['options'].append({"text": choice, "sub_options": []})
        
        # Показываем текущие варианты и предлагаем добавить еще
        options_list = "\n".join([f"{i+1}. {opt['text']}" for i, opt in enumerate(context.user_data['options'])])
        
        keyboard = [
            [KeyboardButton("Готово")],
            [KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            f"✅ Вариант добавлен: {choice}\n\n"
            f"Текущие варианты ответов:\n{options_list}\n\n"
            "Введите следующий вариант или нажмите 'Готово', когда закончите:",
            reply_markup=reply_markup
        )
        
        return ADDING_OPTIONS
    
    async def handle_nested_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка добавления вложенных вариантов ответов"""
        choice = update.message.text
        
        if choice == "❌ Нет, оставить как есть":
            await update.message.reply_text(
                "✅ Вопрос успешно сохранен без вложенных вариантов.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        if choice == "✅ Да, добавить вложенные варианты":
            # Получим текущий вопрос и его варианты
            question = context.user_data['new_question']
            current_options = []
            
            # Получаем обновленные варианты из базы
            for q, opts in self.questions_with_options.items():
                if q == question:
                    current_options = opts
                    break
            
            # Если варианты найдены, предлагаем выбрать родительский вариант
            if current_options:
                keyboard = []
                for opt in current_options:
                    keyboard.append([KeyboardButton(opt["text"])])
                keyboard.append([KeyboardButton("❌ Отмена")])
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                # Сохраняем контекст
                context.user_data['current_question'] = question
                
                await update.message.reply_text(
                    "Выберите вариант, к которому нужно добавить вложенные варианты:",
                    reply_markup=reply_markup
                )
                
                context.user_data['selecting_parent_option'] = True
                return ADDING_NESTED_OPTIONS
            else:
                await update.message.reply_text(
                    "❌ Не удалось найти варианты ответов для этого вопроса.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        
        # Если выбран родительский вариант
        if 'selecting_parent_option' in context.user_data:
            if choice == "❌ Отмена":
                await update.message.reply_text(
                    "✅ Вопрос успешно сохранен без дополнительных вложенных вариантов.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
            
            # Сохраняем выбранный родительский вариант
            context.user_data['parent_option'] = choice
            context.user_data.pop('selecting_parent_option', None)
            
            # Запрашиваем ввод вложенного варианта
            keyboard = [
                [KeyboardButton("✨ Сделать свободным")],
                [KeyboardButton("❌ Отмена")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"Введите вложенный вариант для '{choice}' или выберите 'Сделать свободным':",
                reply_markup=reply_markup
            )
            
            # Инициализируем список вложенных вариантов
            context.user_data['sub_options'] = []
            context.user_data['adding_sub_option'] = True
            return ADDING_NESTED_OPTIONS
        
        # Если добавляем вложенный вариант
        if 'adding_sub_option' in context.user_data:
            if choice == "✅ Готово":
                # Сохраняем вложенные варианты
                question = context.user_data['current_question']
                parent_option = context.user_data['parent_option']
                sub_options = context.user_data.get('sub_options', [])
                
                # Получаем номер вопроса
                question_num = -1
                for i, q in enumerate(self.questions):
                    if q == question:
                        question_num = i
                        break
                
                if question_num == -1:
                    await update.message.reply_text(
                        "❌ Не удалось найти вопрос.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
                
                # Получаем текущие варианты
                current_options = self.questions_with_options[question]
                
                # Находим родительский вариант и добавляем вложенные
                for opt in current_options:
                    if opt["text"] == parent_option:
                        opt["sub_options"] = sub_options
                        break
                
                # Сохраняем обновленные варианты
                success = self.sheets.edit_question_options(question_num, current_options)
                
                if success:
                    # Обновляем список вопросов
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    
                    # Обновляем списки вопросов в других обработчиках через application
                    await self._update_handlers_questions(update)
                    
                    # Спрашиваем, нужно ли добавить вложенные варианты к другому варианту
                    keyboard = [
                        [KeyboardButton("✅ Да, к другому варианту")],
                        [KeyboardButton("❌ Нет, завершить")]
                    ]
                    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                    
                    await update.message.reply_text(
                        f"✅ Вложенные варианты для '{parent_option}' успешно добавлены!\n\n"
                        "Хотите добавить вложенные варианты к другому основному варианту?",
                        reply_markup=reply_markup
                    )
                    
                    # Очищаем состояние для возможного добавления к другому варианту
                    context.user_data.pop('parent_option', None)
                    context.user_data.pop('sub_options', None)
                    context.user_data.pop('adding_sub_option', None)
                    return ADDING_NESTED_OPTIONS
                else:
                    await update.message.reply_text(
                        "❌ Не удалось сохранить вложенные варианты.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
            
            # Если выбрана опция "Сделать свободным"
            if choice == "✨ Сделать свободным":
                # Сохраняем пустой список вложенных вариантов (свободный ответ)
                question = context.user_data['current_question']
                parent_option = context.user_data['parent_option']
                
                # Получаем номер вопроса
                question_num = -1
                for i, q in enumerate(self.questions):
                    if q == question:
                        question_num = i
                        break
                
                if question_num == -1:
                    await update.message.reply_text(
                        "❌ Не удалось найти вопрос.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
                
                # Получаем текущие варианты
                current_options = self.questions_with_options[question]
                
                # Находим родительский вариант и устанавливаем пустой список подвариантов
                for opt in current_options:
                    if opt["text"] == parent_option:
                        opt["sub_options"] = []
                        break
                
                # Сохраняем обновленные варианты
                success = self.sheets.edit_question_options(question_num, current_options)
                
                if success:
                    # Обновляем список вопросов
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    
                    # Обновляем списки вопросов в других обработчиках через application
                    await self._update_handlers_questions(update)
                    
                    # Спрашиваем, нужно ли добавить вложенные варианты к другому варианту
                    keyboard = [
                        [KeyboardButton("✅ Да, к другому варианту")],
                        [KeyboardButton("❌ Нет, завершить")]
                    ]
                    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                    
                    await update.message.reply_text(
                        f"✅ Вариант '{parent_option}' настроен как свободный ответ!\n\n"
                        "Хотите добавить вложенные варианты к другому основному варианту?",
                        reply_markup=reply_markup
                    )
                    
                    # Очищаем состояние для возможного добавления к другому варианту
                    context.user_data.pop('parent_option', None)
                    context.user_data.pop('sub_options', None)
                    context.user_data.pop('adding_sub_option', None)
                    return ADDING_NESTED_OPTIONS
                else:
                    await update.message.reply_text(
                        "❌ Не удалось настроить свободный ответ.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
            
            # Если вводим новый вложенный вариант
            if 'sub_options' not in context.user_data:
                context.user_data['sub_options'] = []
            
            context.user_data['sub_options'].append(choice)
            
            # Запрашиваем следующий вложенный вариант
            keyboard = [
                [KeyboardButton("✅ Готово")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            parent_option = context.user_data['parent_option']
            
            await update.message.reply_text(
                f"✅ Вложенный вариант добавлен: {choice}\n\n"
                f"Текущие вложенные варианты для '{parent_option}':\n" +
                "\n".join(f"• {opt}" for opt in context.user_data['sub_options']) +
                "\n\nВведите следующий вложенный вариант или нажмите 'Готово':",
                reply_markup=reply_markup
            )
            
            return ADDING_NESTED_OPTIONS
        
        # Обрабатываем выбор добавления к другому варианту
        if choice == "✅ Да, к другому варианту":
            # Получаем текущий вопрос и его варианты
            question = context.user_data['current_question']
            current_options = self.questions_with_options[question]
            
            # Формируем клавиатуру только с вариантами без вложенных
            keyboard = []
            for opt in current_options:
                # Если у варианта еще нет вложенных вариантов или они пусты
                if not opt.get("sub_options"):
                    keyboard.append([KeyboardButton(opt["text"])])
            
            # Если нет вариантов без вложенных, сообщаем об этом
            if not keyboard:
                await update.message.reply_text(
                    "У всех вариантов уже есть вложенные варианты. Вопрос успешно сохранен.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
            
            keyboard.append([KeyboardButton("❌ Отмена")])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Выберите еще один вариант для добавления вложенных вариантов:",
                reply_markup=reply_markup
            )
            
            context.user_data['selecting_parent_option'] = True
            return ADDING_NESTED_OPTIONS
        
        if choice == "❌ Нет, завершить":
            await update.message.reply_text(
                "✅ Вопрос с вложенными вариантами успешно сохранен!",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Неизвестный выбор
        await update.message.reply_text(
            "❌ Пожалуйста, выберите один из предложенных вариантов.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    async def clear_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса очистки данных"""
        logger.info(f"Пользователь {update.effective_user.id} запросил очистку данных")
        
        # Создаем клавиатуру для подтверждения
        keyboard = [
            [KeyboardButton("✅ Подтвердить очистку")],
            [KeyboardButton("❌ Отмена")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "⚠️ ВНИМАНИЕ! Вы собираетесь удалить все ответы и статистику.\n"
            "Это действие необратимо!\n\n"
            "Вы уверены, что хотите продолжить?",
            reply_markup=reply_markup
        )
        
        return CONFIRMING_CLEAR

    async def handle_clear_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка подтверждения очистки данных"""
        choice = update.message.text
        user_id = update.effective_user.id
        
        if choice == "✅ Подтвердить очистку":
            logger.info(f"[{user_id}] Подтверждена очистка данных")
            
            # Выполняем очистку
            success = self.sheets.clear_answers_and_stats()
            
            if success:
                await update.message.reply_text(
                    "✅ Все ответы и статистика успешно очищены.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.info(f"[{user_id}] Данные успешно очищены")
            else:
                await update.message.reply_text(
                    "❌ Произошла ошибка при очистке данных. Пожалуйста, попробуйте позже.",
                    reply_markup=ReplyKeyboardRemove()
                )
                logger.error(f"[{user_id}] Ошибка при очистке данных")
        
        elif choice == "❌ Отмена":
            await update.message.reply_text(
                "Очистка данных отменена.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"[{user_id}] Очистка данных отменена")
        
        else:
            await update.message.reply_text(
                "❌ Пожалуйста, используйте кнопки для ответа.",
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("✅ Подтвердить очистку")],
                    [KeyboardButton("❌ Отмена")]
                ], resize_keyboard=True)
            )
            return CONFIRMING_CLEAR
        
        return ConversationHandler.END 

    async def add_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса добавления администратора"""
        logger.info(f"Пользователь {update.effective_user.id} начал добавление администратора")
        
        await update.message.reply_text(
            "Пожалуйста, отправьте ID пользователя, которого хотите сделать администратором.\n\n"
            "ID можно узнать, например, у бота @userinfobot\n\n"
            "Для отмены используйте /cancel",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return ADDING_ADMIN

    async def handle_new_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка добавления нового администратора - шаг 1: ID"""
        try:
            message = update.message
            
            # Проверяем наличие текста
            if not message.text:
                await message.reply_text(
                    "❌ Пожалуйста, отправьте ID пользователя числом."
                )
                return ADDING_ADMIN
            
            # Пытаемся преобразовать текст в число
            try:
                new_admin_id = int(message.text)
            except ValueError:
                await message.reply_text(
                    "❌ ID пользователя должен быть числом.\n"
                    "Пожалуйста, отправьте корректный ID пользователя."
                )
                return ADDING_ADMIN

            # Сохраняем ID в context
            context.user_data['new_admin_id'] = new_admin_id
            
            # Запрашиваем имя администратора
            await message.reply_text(
                "Введите имя администратора:",
                reply_markup=ReplyKeyboardRemove()
            )
            return ADDING_ADMIN_NAME

        except Exception as e:
            logger.error(f"Ошибка при добавлении администратора: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при добавлении администратора."
            )
            return ConversationHandler.END

    async def handle_admin_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка добавления нового администратора - шаг 2: имя"""
        try:
            message = update.message
            admin_name = message.text

            # Сохраняем имя в context
            context.user_data['admin_name'] = admin_name

            # Запрашиваем описание
            await message.reply_text(
                "Введите описание администратора:",
                reply_markup=ReplyKeyboardRemove()
            )
            return ADDING_ADMIN_DESCRIPTION

        except Exception as e:
            logger.error(f"Ошибка при сохранении имени администратора: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при сохранении имени администратора."
            )
            return ConversationHandler.END

    async def handle_admin_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка добавления нового администратора - шаг 3: описание"""
        try:
            message = update.message
            admin_description = message.text
            new_admin_id = context.user_data.get('new_admin_id')
            admin_name = context.user_data.get('admin_name')

            # Добавляем администратора со всеми данными
            success = self.sheets.add_admin(new_admin_id, admin_name, admin_description)

            if success:
                # Обновляем список админов в памяти
                admin_ids = self.sheets.get_admins()
                # Обновляем команды для нового админа
                await setup_commands(self.application, admin_ids)
                
                admin_info = await self.sheets.get_admin_info(new_admin_id)
                await message.reply_text(
                    f"✅ Администратор успешно добавлен:\n"
                    f"ID: {new_admin_id}\n"
                    f"Имя: {admin_name}\n"
                    f"Описание: {admin_description}\n"
                    f"Информация: {admin_info}"
                )
            else:
                await message.reply_text(
                    "❌ Не удалось добавить администратора. Возможно, он уже существует."
                )

            # Очищаем данные
            context.user_data.clear()
            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Ошибка при сохранении описания администратора: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при сохранении описания администратора."
            )
            return ConversationHandler.END

    async def remove_admin(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса удаления администратора"""
        logger.info(f"Пользователь {update.effective_user.id} начал удаление администратора")
        
        # Получаем список админов
        admins = await self.sheets.get_admins_list()
        
        if not admins:
            await update.message.reply_text(
                "❌ Список администраторов пуст.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Создаем клавиатуру с админами
        keyboard = []
        for admin_id, admin_info in admins:
            keyboard.append([KeyboardButton(f"{admin_id} - {admin_info}")])
        keyboard.append([KeyboardButton("❌ Отмена")])
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Выберите администратора для удаления:",
            reply_markup=reply_markup
        )
        
        return REMOVING_ADMIN

    async def handle_admin_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка удаления администратора"""
        choice = update.message.text
        
        if choice == "❌ Отмена":
            await update.message.reply_text(
                "Удаление отменено.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        try:
            admin_id = int(choice.split(" - ")[0])
            success = self.sheets.remove_admin(admin_id)
            
            if success:
                # Обновляем список админов в памяти
                admin_ids = self.sheets.get_admins()
                # Обновляем команды после удаления админа
                await setup_commands(self.application, admin_ids)
                
                await update.message.reply_text(
                    f"✅ Администратор {admin_id} успешно удален.",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "❌ Не удалось удалить администратора.",
                    reply_markup=ReplyKeyboardRemove()
                )
        except Exception as e:
            logger.error(f"Ошибка при удалении администратора: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при удалении администратора.",
                reply_markup=ReplyKeyboardRemove()
            )
        
        return ConversationHandler.END

    async def list_admins(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ списка администраторов"""
        logger.info(f"Пользователь {update.effective_user.id} запросил список администраторов")
        
        admins = await self.sheets.get_admins_list()
        
        if not admins:
            await update.message.reply_text(
                "📝 Список администраторов пуст.",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Формируем текст со списком админов
        admins_text = "📝 Список администраторов:\n\n"
        for admin_id, admin_info in admins:
            admins_text += f"• {admin_id} - {admin_info}\n"
        
        await update.message.reply_text(
            admins_text,
            reply_markup=ReplyKeyboardRemove()
        ) 

    async def _update_handlers_questions(self, update: Update):
        """Обновление списков вопросов в других обработчиках"""
        try:
            if not self.application:
                logger.error("Application не найден")
                return

            # Обновляем собственные списки вопросов перед обновлением других обработчиков
            old_questions_count = len(self.questions)
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            logger.info(f"Обновлены локальные списки вопросов в AdminHandler. Было: {old_questions_count}, стало: {len(self.questions)}")

            # Обновляем списки вопросов в других обработчиках
            for handler in self.application.handlers[0]:
                # Обновление для SurveyHandler
                if isinstance(handler, ConversationHandler) and hasattr(handler, 'name') and handler.name == "survey_conversation":
                    # Находим SurveyHandler в entry_points
                    for entry_point in handler.entry_points:
                        if hasattr(entry_point.callback, '__self__'):
                            survey_handler = entry_point.callback.__self__
                            old_count = len(survey_handler.questions)
                            survey_handler.questions_with_options = self.questions_with_options
                            survey_handler.questions = self.questions
                            
                            # Полностью перестраиваем состояния для вопросов
                            new_states = {}
                            
                            # Сначала копируем стандартные состояния, не связанные с конкретными вопросами
                            for state, handlers_list in handler.states.items():
                                if not state.startswith("QUESTION_") or state in ["WAITING_START", "WAITING_EVENT_INFO", "CONFIRMING", "SUB_OPTIONS"]:
                                    new_states[state] = handlers_list
                            
                            # Затем добавляем состояния для текущих вопросов
                            for i in range(len(self.questions)):
                                question_state = f"QUESTION_{i}"
                                new_states[question_state] = [MessageHandler(filters.TEXT & ~filters.COMMAND, survey_handler.handle_answer)]
                                # Добавляем состояние для вложенных вариантов
                                sub_question_state = f"QUESTION_{i}_SUB"
                                new_states[sub_question_state] = [MessageHandler(filters.TEXT & ~filters.COMMAND, survey_handler.handle_answer)]
                            
                            # Заменяем старые состояния новыми
                            handler.states.clear()
                            handler.states.update(new_states)
                            
                            logger.info(f"Полностью обновлены состояния в SurveyHandler. Было вопросов: {old_count}, стало: {len(self.questions)}")
                            break
                
                # Обновление для EditHandler
                if isinstance(handler, ConversationHandler) and hasattr(handler, 'name') and handler.name == "edit_question_conversation":
                    # Находим EditHandler в entry_points
                    for entry_point in handler.entry_points:
                        if hasattr(entry_point.callback, '__self__'):
                            edit_handler = entry_point.callback.__self__
                            old_count = len(edit_handler.questions)
                            edit_handler.questions_with_options = self.questions_with_options
                            edit_handler.questions = self.questions
                            
                            logger.info(f"Обновлены списки вопросов в EditHandler. Было: {old_count}, стало: {len(self.questions)}")
                            break
                
                # Обновление для DeleteQuestionHandler
                if isinstance(handler, ConversationHandler) and hasattr(handler, 'name') and handler.name == "delete_question_conversation":
                    # Находим DeleteQuestionHandler в entry_points
                    for entry_point in handler.entry_points:
                        if hasattr(entry_point.callback, '__self__'):
                            delete_handler = entry_point.callback.__self__
                            old_count = len(delete_handler.questions)
                            delete_handler.questions_with_options = self.questions_with_options
                            delete_handler.questions = self.questions
                            
                            logger.info(f"Обновлены списки вопросов в DeleteQuestionHandler. Было: {old_count}, стало: {len(self.questions)}")
                            break
                
                # Обновление для ListQuestionsHandler
                if isinstance(handler, CommandHandler) and handler.callback.__name__ == "list_questions":
                    if hasattr(handler.callback, '__self__'):
                        list_questions_handler = handler.callback.__self__
                        if hasattr(list_questions_handler, 'questions'):
                            old_count = len(list_questions_handler.questions)
                            list_questions_handler.questions_with_options = self.questions_with_options
                            list_questions_handler.questions = self.questions
                            logger.info(f"Обновлены списки вопросов в ListQuestionsHandler. Было: {old_count}, стало: {len(self.questions)}")

            # Проверяем все группы обработчиков для обновления
            for group_idx, group in enumerate(self.application.handlers):
                if group_idx > 0:  # Пропускаем первую группу, которую уже обработали выше
                    for handler in group:
                        if isinstance(handler, ConversationHandler) or isinstance(handler, CommandHandler):
                            if hasattr(handler, 'callback') and hasattr(handler.callback, '__self__'):
                                handler_instance = handler.callback.__self__
                            elif hasattr(handler, 'entry_points') and handler.entry_points:
                                for entry_point in handler.entry_points:
                                    if hasattr(entry_point.callback, '__self__'):
                                        handler_instance = entry_point.callback.__self__
                                        break
                            else:
                                continue
                                
                            if hasattr(handler_instance, 'questions') and hasattr(handler_instance, 'questions_with_options'):
                                old_count = len(handler_instance.questions)
                                handler_instance.questions_with_options = self.questions_with_options
                                handler_instance.questions = self.questions
                                logger.info(f"Обновлены списки вопросов в {handler_instance.__class__.__name__} (группа {group_idx}). Было: {old_count}, стало: {len(self.questions)}")

            logger.info(f"Списки вопросов успешно обновлены во всех обработчиках. Итоговое количество вопросов: {len(self.questions)}")

        except Exception as e:
            logger.error(f"Ошибка при обновлении списков вопросов: {e}")
            logger.exception(e)

    async def reset_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сброс прохождения опроса для пользователя"""
        logger.info(f"Админ {update.effective_user.id} запросил сброс опроса для пользователя")
        
        await update.message.reply_text(
            "Отправьте ID пользователя, для которого нужно сбросить прохождение опроса.\n\n"
            "Для отмены используйте /cancel",
            reply_markup=ReplyKeyboardRemove()
        )
        
        return RESETTING_USER

    async def handle_reset_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сброса опроса для пользователя"""
        try:
            user_id = int(update.message.text)
            success = self.sheets.reset_user_survey(user_id)
            
            if success:
                await update.message.reply_text(
                    f"✅ Прохождение опроса для пользователя {user_id} успешно сброшено",
                    reply_markup=ReplyKeyboardRemove()
                )
            else:
                await update.message.reply_text(
                    "❌ Произошла ошибка при сбросе опроса",
                    reply_markup=ReplyKeyboardRemove()
                )
                
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, отправьте корректный ID пользователя (число)",
                reply_markup=ReplyKeyboardRemove()
            )
            return RESETTING_USER
            
        return ConversationHandler.END

    async def list_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вывод списка зарегистрированных пользователей с пагинацией"""
        logger.info(f"Пользователь {update.effective_user.id} запросил список пользователей")
        
        # Инициализируем страницу и сохраняем в context
        context.user_data['users_page'] = 1
        context.user_data['users_page_size'] = 10  # количество пользователей на странице
        
        # Получаем данные для первой страницы
        await self._show_users_page(update, context)
        
        return BROWSING_USERS

    async def handle_users_pagination(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка пагинации при просмотре списка пользователей"""
        query = update.message.text
        
        if query == "❌ Закрыть":
            await update.message.reply_text(
                "Просмотр списка пользователей завершен.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        elif query == "⬅️ Предыдущая":
            # Переход на предыдущую страницу
            if context.user_data.get('users_page', 1) > 1:
                context.user_data['users_page'] -= 1
                
        elif query == "➡️ Следующая":
            # Переход на следующую страницу
            current_page = context.user_data.get('users_page', 1)
            total_pages = context.user_data.get('users_total_pages', 1)
            
            if current_page < total_pages:
                context.user_data['users_page'] += 1
                
        # Показываем текущую страницу
        await self._show_users_page(update, context)
        return BROWSING_USERS
        
    async def _show_users_page(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Вспомогательный метод для отображения страницы со списком пользователей"""
        page = context.user_data.get('users_page', 1)
        page_size = context.user_data.get('users_page_size', 10)
        
        # Получаем список пользователей для текущей страницы
        users, total_users, total_pages = self.sheets.get_users_list(page, page_size)
        
        # Сохраняем общее количество страниц
        context.user_data['users_total_pages'] = total_pages
        
        if not users:
            await update.message.reply_text(
                "👥 Список пользователей пуст.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        # Формируем текст со списком пользователей
        users_text = f"👥 Список пользователей (страница {page}/{total_pages}):\n\n"
        for user_id, telegram_id, username, reg_date in users:
            users_text += f"🆔 {user_id} | Telegram: {telegram_id}\n"
            users_text += f"👤 @{username}\n"
            users_text += f"📅 Зарегистрирован: {reg_date}\n"
            users_text += f"{'─' * 30}\n"
            
        # Добавляем информацию о пагинации
        users_text += f"\nВсего пользователей: {total_users}"
        
        # Создаем клавиатуру для навигации
        keyboard = []
        
        # Добавляем кнопки пагинации
        pagination_buttons = []
        if page > 1:
            pagination_buttons.append(KeyboardButton("⬅️ Предыдущая"))
        if page < total_pages:
            pagination_buttons.append(KeyboardButton("➡️ Следующая"))
            
        if pagination_buttons:
            keyboard.append(pagination_buttons)
            
        # Добавляем кнопку закрытия
        keyboard.append([KeyboardButton("❌ Закрыть")])
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Отправляем сообщение с пагинацией
        await update.message.reply_text(
            users_text,
            reply_markup=reply_markup
        ) 