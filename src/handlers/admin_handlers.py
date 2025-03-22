"""
Обработчики для административных команд
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, filters, CommandHandler

from models.states import *
from utils.sheets import GoogleSheets
from handlers.base_handler import BaseHandler
from utils.helpers import setup_commands  # Импортируем функцию setup_commands
from config import QUESTIONS_SHEET  # Добавляем импорт QUESTIONS_SHEET

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
            
            # Добавляем номер и текст вопроса
            questions_text += f"{i+1}. {question}\n"
            
            # Формируем информацию о вариантах ответов
            if not options:
                questions_text += "   📝 Свободный ответ (без вариантов)\n\n"
                continue
                
            # Формируем читаемый список вариантов ответов
            options_list = []
            has_sub_options = False
            
            for opt in options:
                if isinstance(opt, dict) and "text" in opt:
                    option_text = opt["text"]
                    # Добавляем информацию о подвариантах
                    if "sub_options" in opt and opt["sub_options"]:
                        has_sub_options = True
                        sub_count = len(opt["sub_options"])
                        option_text += f" 📑 (+{sub_count} подвар.)"
                    options_list.append(option_text)
                else:
                    # Для обратной совместимости
                    options_list.append(str(opt))
            
            # Вывод типа вопроса в зависимости от наличия подвариантов
            if has_sub_options:
                questions_text += "   🔄 Вопрос с подвариантами\n"
            else:
                questions_text += "   ✅ Вопрос с вариантами ответов\n"
                
            # Выводим список вариантов
            options_text = ", ".join(options_list)
            questions_text += f"   Варианты: {options_text}\n\n"
        
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
            
        # Добавляем новый вариант без sub_options
        context.user_data['options'].append({"text": choice})
        
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
    
    async def handle_nested_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Обработка запроса на добавление вложенных вариантов ответа"""
        text = update.message.text
        
        # Логируем текущее состояние данных пользователя для отладки
        logger.info(f"Обработка выбора для вложенных вариантов: {text}")
        logger.info(f"Текущие состояния в context.user_data: {context.user_data.keys()}")
        
        # Если пользователь выбрал "Нет", завершаем добавление вложенных вариантов
        if text == "❌ Нет, завершить":
            # Очищаем временные данные
            for key in ['selecting_parent_option', 'parent_option', 'sub_options', 'adding_sub_option']:
                if key in context.user_data:
                    context.user_data.pop(key)
            
            await update.message.reply_text(
                "✅ Вопрос успешно добавлен!",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Обработка специальных кнопок
        if text == "✅ Да, к другому варианту" or text == "✅ Да, добавить вложенные варианты":
            logger.info(f"Получена специальная кнопка '{text}' в режиме добавления подвариантов")
            
            # Если мы находимся в состоянии выбора родительского варианта
            if 'selecting_parent_option' in context.user_data:
                # Очищаем предыдущие временные данные
                for key in ['selecting_parent_option', 'parent_option', 'sub_options', 'adding_sub_option']:
                    if key in context.user_data:
                        context.user_data.pop(key)
                
                # Отправляем запрос на выбор варианта для добавления вложенных вариантов
                # Получаем текущий вопрос и его варианты
                if 'current_question' in context.user_data:
                    question = context.user_data['current_question']
                    if question in self.questions_with_options:
                        options = self.questions_with_options[question]
                        
                        # Формируем клавиатуру из вариантов
                        keyboard = []
                        for option in options:
                            if isinstance(option, dict) and "text" in option:
                                keyboard.append([KeyboardButton(option["text"])])
                        
                        # Добавляем кнопку отмены
                        keyboard.append([KeyboardButton("❌ Отмена")])
                        
                        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                        
                        await update.message.reply_text(
                            "Выберите вариант, к которому нужно добавить вложенные варианты:",
                            reply_markup=reply_markup
                        )
                        
                        # Устанавливаем флаг выбора родительского варианта
                        context.user_data['selecting_parent_option'] = True
                        return ADDING_NESTED_OPTIONS
                
                # Если не удалось найти текущий вопрос, завершаем
                await update.message.reply_text(
                    "❌ Не удалось найти текущий вопрос",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
            
            # Если кнопка нажата в другом контексте, возможно первичный запрос на добавление вложенных
            else:
                # Получаем вопрос из контекста
                if 'new_question' in context.user_data:
                    question = context.user_data['new_question']
                    context.user_data['current_question'] = question
                    
                    # Получаем варианты для этого вопроса
                    if 'options' in context.user_data and context.user_data['options']:
                        options = context.user_data['options']
                        
                        # Формируем клавиатуру из вариантов
                        keyboard = []
                        for option in options:
                            if isinstance(option, dict) and "text" in option:
                                keyboard.append([KeyboardButton(option["text"])])
                        
                        # Добавляем кнопку отмены
                        keyboard.append([KeyboardButton("❌ Отмена")])
                        
                        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                        
                        await update.message.reply_text(
                            "Выберите вариант, к которому нужно добавить вложенные варианты:",
                            reply_markup=reply_markup
                        )
                        
                        # Устанавливаем флаг выбора родительского варианта
                        context.user_data['selecting_parent_option'] = True
                        return ADDING_NESTED_OPTIONS
                
                # Если не удалось найти варианты, завершаем
                await update.message.reply_text(
                    "❌ Не удалось найти варианты ответов",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
        
        # Если пользователь нажал "Отмена"
        if text == "❌ Отмена":
            for key in ['selecting_parent_option', 'parent_option', 'sub_options', 'adding_sub_option']:
                if key in context.user_data:
                    context.user_data.pop(key)
            
            await update.message.reply_text(
                "Операция отменена",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Если пользователь выбирает родительский вариант
        if 'selecting_parent_option' in context.user_data and context.user_data['selecting_parent_option']:
            # Очищаем флаг выбора родительского варианта
            context.user_data.pop('selecting_parent_option')
            
            # Сохраняем выбранный родительский вариант
            context.user_data['parent_option'] = text
            
            # Инициализируем список подвариантов
            context.user_data['sub_options'] = []
            
            # Запрос на выбор типа подвариантов
            keyboard = [
                [KeyboardButton("✨ Сделать свободным")],
                [KeyboardButton("📝 Добавить подварианты")],
                [KeyboardButton("❌ Отмена")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"Вы выбрали вариант '{text}'. Что вы хотите сделать?",
                reply_markup=reply_markup
            )
            
            return ADDING_NESTED_OPTIONS
        
        # Если пользователь выбрал "Сделать свободным"
        if text == "✨ Сделать свободным" and 'parent_option' in context.user_data:
            parent_option_text = context.user_data['parent_option']
            logger.info(f"Пользователь выбрал 'Сделать свободным' для варианта {parent_option_text}")
            
            question = None
            question_num = -1
            
            # Получаем текущий вопрос
            if 'current_question' in context.user_data:
                question = context.user_data['current_question']
                logger.info(f"Текущий вопрос: '{question}', родительский вариант: '{parent_option_text}'")
                
                # Находим номер вопроса
                for i, q in enumerate(self.questions):
                    if q == question:
                        question_num = i
                        context.user_data['editing_question_num'] = i
                        break
            
            # Получаем текущие варианты ответов для вопроса
            current_options = []
            if question in self.questions_with_options:
                current_options = self.questions_with_options[question]
                logger.info(f"Текущие варианты для вопроса '{question}': {current_options}")
                
                # Находим вариант, который нужно изменить
                for i, opt in enumerate(current_options):
                    if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                        # Устанавливаем пустой список подвариантов (свободный ответ)
                        current_options[i]["sub_options"] = []
                        logger.info(f"Установлен пустой список sub_options для '{parent_option_text}' - свободный ответ. Структура: {current_options[i]}")
                        break
            
            # Сохраняем изменения в таблицу
            logger.info(f"Отправка на сохранение для вопроса {question_num}, вариант '{parent_option_text}' с пустым списком sub_options: {current_options}")
            success = self.sheets.edit_question_options(question_index=question_num, options=current_options)
            
            if success:
                # Обновляем локальные списки вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                # Проверка после обновления
                if question in self.questions_with_options:
                    updated_options = self.questions_with_options[question]
                    found_option = None
                    for opt in updated_options:
                        if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                            found_option = opt
                            if "sub_options" in opt and isinstance(opt["sub_options"], list) and opt["sub_options"] == []:
                                logger.info(f"✅ Проверка после обновления: вариант '{parent_option_text}' сохранил пустой список sub_options=[] (свободный ответ)")
                            else:
                                logger.warning(f"⚠️ Проверка после обновления: вариант '{parent_option_text}' НЕ имеет пустого списка sub_options! Текущая структура: {opt}")
                            break
                    
                    # Детализируем структуру вопроса после обновления для диагностики
                    logger.info(f"Структура вопроса '{question}' после обновления:")
                    for i, opt in enumerate(updated_options, start=1):
                        if isinstance(opt, dict) and "text" in opt:
                            if "sub_options" in opt and isinstance(opt["sub_options"], list) and opt["sub_options"] == []:
                                logger.info(f"  Опция {i}: '{opt['text']}', sub_options: []")
                            elif "sub_options" in opt and opt["sub_options"]:
                                logger.info(f"  Опция {i}: '{opt['text']}', sub_options: {opt['sub_options']}")
                            else:
                                logger.info(f"  Опция {i}: '{opt['text']}', без sub_options")
                        else:
                            logger.info(f"  Опция {i}: {opt}, без sub_options")
                
                # Обновляем списки вопросов в других обработчиках
                await self._update_handlers_questions(update)
                
                # Запрос подсказки для свободного ввода
                await update.message.reply_text(
                    f"Введите текст вопроса для свободного ответа для варианта '{parent_option_text}':",
                    reply_markup=ReplyKeyboardRemove()
                )
                
                # Сохраняем контекст для следующего шага
                context.user_data['parent_option'] = parent_option_text
                context.user_data['editing_question'] = question
                
                # Переходим к добавлению вопроса для свободного ответа
                logger.info(f"Переход к состоянию ADDING_FREE_TEXT_PROMPT из handle_nested_options для варианта '{parent_option_text}'")
                return ADDING_FREE_TEXT_PROMPT
            else:
                await update.message.reply_text(
                    f"❌ Не удалось сделать вариант '{parent_option_text}' свободным. Попробуйте еще раз.",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем контекст
                for key in ['selecting_parent_option', 'parent_option', 'sub_options', 'adding_sub_option']:
                    if key in context.user_data:
                        context.user_data.pop(key)
                return ConversationHandler.END
        
        # Если пользователь выбрал "Добавить подварианты"
        if text == "📝 Добавить подварианты" and 'parent_option' in context.user_data:
            # Запрос на ввод подвариантов
            context.user_data['adding_sub_option'] = True
            
            await update.message.reply_text(
                f"Введите подвариант для '{context.user_data['parent_option']}' (каждый вариант в отдельном сообщении).\n"
                "Когда закончите, отправьте 'Готово'.",
                reply_markup=ReplyKeyboardMarkup([["Готово"], ["❌ Отмена"]], resize_keyboard=True)
            )
            
            return ADDING_NESTED_OPTIONS
        
        # Если пользователь добавляет подварианты и отправил "Готово"
        if text == "Готово" and 'adding_sub_option' in context.user_data and 'sub_options' in context.user_data:
            parent_option_text = context.user_data['parent_option']
            sub_options = context.user_data['sub_options']
            
            question = None
            question_num = -1
            
            # Получаем текущий вопрос
            if 'current_question' in context.user_data:
                question = context.user_data['current_question']
                
                # Находим номер вопроса
                for i, q in enumerate(self.questions):
                    if q == question:
                        question_num = i
                        context.user_data['editing_question_num'] = i
                        break
            
            # Проверяем, что у нас есть подварианты
            if not sub_options:
                await update.message.reply_text(
                    "❌ Вы не добавили ни одного подварианта. Операция отменена.",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем контекст
                for key in ['selecting_parent_option', 'parent_option', 'sub_options', 'adding_sub_option']:
                    if key in context.user_data:
                        context.user_data.pop(key)
                return ConversationHandler.END
            
            # Получаем текущие варианты ответов для вопроса
            current_options = []
            if question in self.questions_with_options:
                current_options = self.questions_with_options[question]
                
                # Находим вариант, который нужно изменить
                for i, opt in enumerate(current_options):
                    if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                        # Добавляем подварианты
                        current_options[i]["sub_options"] = sub_options
                        break
            
            # Сохраняем изменения в таблицу
            success = self.sheets.edit_question_options(question_index=question_num, options=current_options)
            
            if success:
                # Обновляем локальные списки вопросов
                self.questions_with_options = self.sheets.get_questions_with_options()
                self.questions = list(self.questions_with_options.keys())
                
                # Обновляем списки вопросов в других обработчиках
                await self._update_handlers_questions(update)
                
                # Формируем сообщение с добавленными подвариантами
                sub_options_text = "\n".join([f"- {sub_opt}" for sub_opt in sub_options])
                
                # Спрашиваем, нужно ли добавить вложенные варианты к другому варианту
                keyboard = [
                    [KeyboardButton("✅ Да, к другому варианту")],
                    [KeyboardButton("❌ Нет, завершить")]
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                await update.message.reply_text(
                    f"✅ Подварианты для '{parent_option_text}' добавлены:\n{sub_options_text}\n\n"
                    "Хотите добавить вложенные варианты к другому основному варианту?",
                    reply_markup=reply_markup
                )
                
                # Очищаем контекст
                context.user_data.pop('adding_sub_option', None)
                context.user_data.pop('sub_options', None)
                context.user_data.pop('parent_option', None)
                
                return ADDING_NESTED_OPTIONS
            else:
                await update.message.reply_text(
                    f"❌ Не удалось добавить подварианты для '{parent_option_text}'. Попробуйте еще раз.",
                    reply_markup=ReplyKeyboardRemove()
                )
                # Очищаем контекст
                for key in ['selecting_parent_option', 'parent_option', 'sub_options', 'adding_sub_option']:
                    if key in context.user_data:
                        context.user_data.pop(key)
                return ConversationHandler.END
        
        # Если пользователь добавляет подварианты
        if 'adding_sub_option' in context.user_data and 'sub_options' in context.user_data:
            # Добавляем подвариант в список
            # Проверка на специальные кнопки, которые не нужно добавлять как подварианты
            if text not in ["❌ Отмена", "✅ Да, к другому варианту", "✅ Да, добавить вложенные варианты", "❌ Нет, завершить"]:
                context.user_data['sub_options'].append(text)
                logger.info(f"Добавлен подвариант '{text}' для '{context.user_data['parent_option']}'")
                
                await update.message.reply_text(
                    f"✅ Подвариант '{text}' добавлен.\nВведите следующий или нажмите 'Готово'.",
                    reply_markup=ReplyKeyboardMarkup([["Готово"], ["❌ Отмена"]], resize_keyboard=True)
                )
            else:
                logger.info(f"Пропуск специальной кнопки '{text}', не добавляем как подвариант")
        
        return ADDING_NESTED_OPTIONS
    
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

    async def handle_add_free_text_prompt(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка добавления вопроса для свободного ответа"""
        prompt = update.message.text
        logger.info(f"Получен вопрос для свободного ответа: {prompt}")
        
        # Проверяем наличие необходимых данных в контексте
        if 'editing_question' not in context.user_data or 'editing_option' not in context.user_data:
            logger.error("Ошибка: editing_question или editing_option отсутствуют в context.user_data")
            logger.info(f"Доступные ключи в context.user_data: {context.user_data.keys()}")
            
            # Проверяем, есть ли альтернативные данные в контексте
            question = context.user_data.get('current_question')
            parent_option = context.user_data.get('parent_option')
            
            if not question or not parent_option:
                await update.message.reply_text(
                    "❌ Ошибка: вопрос или вариант не выбраны",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
                
            # Используем альтернативные данные, если они есть
            context.user_data['editing_question'] = question
            context.user_data['editing_option'] = parent_option
            logger.info(f"Использованы альтернативные данные: вопрос '{question}', вариант '{parent_option}'")
        
        question = context.user_data['editing_question']
        parent_option_text = context.user_data['editing_option']
        parent_option_index = context.user_data.get('editing_option_index', -1)
        
        # Получаем номер вопроса
        question_num = context.user_data.get('editing_question_num', -1)
        if question_num == -1:
            # Пробуем найти номер вопроса, если он не был сохранен
            for i, q in enumerate(self.questions):
                if q == question:
                    question_num = i
                    context.user_data['editing_question_num'] = i
                    break
                
        logger.info(f"Добавление вопроса для свободного ответа. Вопрос: '{question}', вариант: '{parent_option_text}', индекс вопроса: {question_num}")
        
        # Вместо многократного обновления вопросов из таблицы, вызываем метод однократно
        try:
            # Прямой вызов специализированного метода с минимальным количеством запросов
            logger.info(f"Вызываем edit_question_options_with_free_text с параметрами: question_index={question_num}, option_text='{parent_option_text}', free_text_prompt='{prompt}'")
            success = self.sheets.edit_question_options_with_free_text(
                question_index=question_num,
                option_text=parent_option_text,
                free_text_prompt=prompt
            )
            
            logger.info(f"Результат сохранения вопроса со свободным ответом: {success}")
        except AttributeError:
            # Если метод edit_question_options_with_free_text не существует
            logger.warning(f"Метод edit_question_options_with_free_text не найден, используем обычный метод")
            # Используем стандартный метод
            success = self.sheets.edit_question_options(
                question_index=question_num, 
                options=self.questions_with_options[question],
                free_text_prompt=prompt, 
                parent_option_text=parent_option_text
            )
        
        if success:
            # Обновляем локальные данные после успешного сохранения
            # Инвалидируем кэш в sheets и обновляем локальные данные
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            await update.message.reply_text(
                f"✅ Вопрос для свободного ответа добавлен: '{prompt}'",
                reply_markup=ReplyKeyboardRemove()
            )
            
            # Обновляем списки вопросов в других обработчиках
            await self._update_handlers_questions(update)
            
            # Спрашиваем, нужно ли добавить вложенные варианты к другому варианту
            keyboard = [
                [KeyboardButton("✅ Да, к другому варианту")],
                [KeyboardButton("❌ Нет, завершить")]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "Хотите добавить вложенные варианты к другому основному варианту?",
                reply_markup=reply_markup
            )
            
            # Очищаем состояние для возможного добавления к другому варианту
            context.user_data.pop('editing_option', None)
            context.user_data.pop('editing_option_index', None)
            
            # Для правильного перехода в состояние ADDING_NESTED_OPTIONS
            # нужно сохранить вопрос в правильном параметре
            if 'editing_question' in context.user_data:
                context.user_data['current_question'] = context.user_data['editing_question']
                
            # Переходим обратно к состоянию добавления вложенных вариантов
            logger.info(f"Возврат состояния ADDING_NESTED_OPTIONS из handle_add_free_text_prompt после успешного добавления вопроса")
            return ADDING_NESTED_OPTIONS
        else:
            logger.error(f"Не удалось добавить вопрос для свободного ответа для варианта '{parent_option_text}'")
            await update.message.reply_text(
                "❌ Не удалось добавить вопрос для свободного ответа. Повторите попытку позже.",
                reply_markup=ReplyKeyboardRemove()
            )
            
        # Очищаем состояние
        context.user_data.pop('editing_option', None)
        context.user_data.pop('editing_option_index', None)
        return ConversationHandler.END

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
            
            # Упрощенное логирование для снижения нагрузки
            logger.info(f"Обновление вопросов в обработчиках. Количество: {len(self.questions)}")
            
            # Обновляем списки вопросов в других обработчиках
            for handler in self.application.handlers[0]:
                # Обновление для SurveyHandler
                if isinstance(handler, ConversationHandler) and hasattr(handler, 'name') and handler.name == "survey_conversation":
                    # Находим SurveyHandler в entry_points
                    for entry_point in handler.entry_points:
                        if hasattr(entry_point.callback, '__self__'):
                            survey_handler = entry_point.callback.__self__
                            old_count = len(survey_handler.questions)
                            # Важно: передаем копию словаря questions_with_options, чтобы избежать изменений общих данных
                            survey_handler.questions_with_options = self.questions_with_options.copy()
                            survey_handler.questions = self.questions.copy()
                            
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
                            edit_handler.questions_with_options = self.questions_with_options.copy()
                            edit_handler.questions = self.questions.copy()
                            
                            logger.info(f"Обновлены списки вопросов в EditHandler. Было: {old_count}, стало: {len(self.questions)}")
                            break
                
                # Обновление для DeleteQuestionHandler
                if isinstance(handler, ConversationHandler) and hasattr(handler, 'name') and handler.name == "delete_question_conversation":
                    # Находим DeleteQuestionHandler в entry_points
                    for entry_point in handler.entry_points:
                        if hasattr(entry_point.callback, '__self__'):
                            delete_handler = entry_point.callback.__self__
                            old_count = len(delete_handler.questions)
                            delete_handler.questions_with_options = self.questions_with_options.copy()
                            delete_handler.questions = self.questions.copy()
                            
                            logger.info(f"Обновлены списки вопросов в DeleteQuestionHandler. Было: {old_count}, стало: {len(self.questions)}")
                            break
                
                # Обновление для ListQuestionsHandler
                if isinstance(handler, CommandHandler) and handler.callback.__name__ == "list_questions":
                    if hasattr(handler.callback, '__self__'):
                        list_questions_handler = handler.callback.__self__
                        if hasattr(list_questions_handler, 'questions'):
                            old_count = len(list_questions_handler.questions)
                            list_questions_handler.questions_with_options = self.questions_with_options.copy()
                            list_questions_handler.questions = self.questions.copy()
                            logger.info(f"Обновлены списки вопросов в ListQuestionsHandler. Было: {old_count}, стало: {len(self.questions)}")

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

    async def handle_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка списка пользователей"""
        logger.info(f"Получение списка пользователей")
        
        # Получаем список пользователей из таблицы
        users = self.sheets.get_users_list()
        
        if not users:
            await update.message.reply_text(
                "❌ Нет данных о пользователях",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Формируем текст с информацией о пользователях
        users_text = f"👥 *Список пользователей:* {len(users)}\n\n"
        
        for i, user in enumerate(users, start=1):
            user_id = user.get('user_id', 'Неизвестно')
            event_info = user.get('event_info', 'Не указано')
            name = user.get('name', 'Неизвестно')
            category = user.get('category', 'Не указана')
            survey_date = user.get('survey_date', 'Неизвестно')
            
            users_text += f"{i}. ID: `{user_id}`\n   Имя: {name}\n   Инфо: {event_info}\n   Категория: {category}\n   Дата опроса: {survey_date}\n\n"
        
        # Проверяем длину текста
        if len(users_text) > 4096:
            # Разбиваем на части
            chunks = []
            current_chunk = ""
            
            for line in users_text.split('\n'):
                if len(current_chunk) + len(line) + 1 > 4096:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    current_chunk += line + '\n'
            
            # Добавляем последний чанк
            if current_chunk:
                chunks.append(current_chunk)
            
            # Отправляем части
            for i, chunk in enumerate(chunks):
                # Для последней части отправляем с reply_markup
                if i == len(chunks) - 1:
                    reply_markup = ReplyKeyboardRemove()
                else:
                    reply_markup = None
                
                await update.message.reply_text(
                    chunk,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
        else:
            # Отправляем весь текст сразу
            reply_markup = ReplyKeyboardRemove()
            
            await update.message.reply_text(
                users_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        
        return ConversationHandler.END 