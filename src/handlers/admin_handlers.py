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
    
    async def handle_nested_options(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка добавления вложенных вариантов ответов"""
        choice = update.message.text
        logger.info(f"Обработка выбора для вложенных вариантов: {choice}")
        
        # Диагностический лог для отладки
        logger.info(f"Текущие состояния в context.user_data: {context.user_data.keys()}")
        
        # Добавляем общую проверку для кнопки "Нет, завершить" в начале функции
        if choice == "❌ Нет, завершить":
            logger.info("Пользователь выбрал 'Нет, завершить'. Завершаем диалог.")
            await update.message.reply_text(
                "✅ Вопрос успешно сохранен! Добавление завершено.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        if choice == "❌ Нет, оставить как есть":
            await update.message.reply_text(
                "✅ Вопрос успешно сохранен без вложенных вариантов.",
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info("Пользователь выбрал 'Оставить как есть'. Завершаем обработку диалога.")
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
            
            # Проверяем, есть ли выбранный вариант в текущих вариантах ответов
            question = context.user_data['current_question']
            current_options = self.questions_with_options.get(question, [])
            parent_option_exists = False
            
            for opt in current_options:
                if isinstance(opt, dict) and "text" in opt and opt["text"] == choice:
                    parent_option_exists = True
                    break
            
            if not parent_option_exists:
                logger.warning(f"Выбранный родительский вариант '{choice}' не найден в вопросе '{question}'")
                await update.message.reply_text(
                    f"❌ Ошибка: вариант '{choice}' не найден в текущем вопросе.",
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
                    if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option:
                        # Проверяем, что подварианты не пусты
                        if sub_options:
                            opt["sub_options"] = sub_options
                            logger.info(f"Устанавливаем подварианты для '{parent_option}': {sub_options}")
                        else:
                            # Если нет подвариантов, удаляем свойство sub_options для обычных вариантов
                            if "sub_options" in opt:
                                # Удаляем свойство sub_options полностью, так как это обычный вариант без подвариантов
                                del opt["sub_options"] 
                                logger.info(f"Удаляем свойство sub_options у '{parent_option}' - обычный вариант")
                        break
                
                # Сохраняем обновленные варианты
                success = self.sheets.edit_question_options(question_num, current_options)
                
                if success:
                    # Обновляем список вопросов
                    old_questions_with_options = self.questions_with_options.copy()
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    
                    # Проверка сохранения sub_options после обновления
                    found = False
                    updated_options = self.questions_with_options.get(question, [])
                    for opt in updated_options:
                        if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option:
                            found = True
                            # Проверяем наличие sub_options в обновленном варианте
                            old_opt = next((o for o in old_questions_with_options[question] if o.get("text") == parent_option), None)
                            if old_opt and "sub_options" in old_opt and old_opt["sub_options"]:
                                if "sub_options" in opt and opt["sub_options"]:
                                    logger.info(f"✅ Проверка после обновления: вариант '{parent_option}' сохранил подварианты: {opt['sub_options']}")
                                else:
                                    logger.warning(f"⚠️ Проверка после обновления: у варианта '{parent_option}' были утеряны подварианты!")
                            elif old_opt and "sub_options" not in old_opt:
                                if "sub_options" not in opt:
                                    logger.info(f"✅ Проверка после обновления: вариант '{parent_option}' остался обычным вариантом без подвариантов")
                                else:
                                    logger.warning(f"⚠️ Проверка после обновления: у варианта '{parent_option}' неожиданно появились подварианты: {opt.get('sub_options')}")
                    
                    if not found:
                        logger.warning(f"⚠️ Проверка после обновления: вариант '{parent_option}' не найден в вопросе '{question}'")
                    
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
                    
                    # Не очищаем состояние при возврате в ADDING_NESTED_OPTIONS
                    # Переносим текущие данные в правильные ключи, необходимые для ADDING_NESTED_OPTIONS
                    context.user_data['current_question'] = question
                    
                    # Логируем для отладки
                    logger.info(f"Возврат состояния ADDING_NESTED_OPTIONS из handle_nested_options после успешного добавления вопроса")
                    return ADDING_NESTED_OPTIONS
                else:
                    await update.message.reply_text(
                        "❌ Не удалось сохранить вложенные варианты.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
            
            # Если выбрана опция "Сделать свободным"
            if choice == "✨ Сделать свободным":
                logger.info(f"Пользователь выбрал 'Сделать свободным' для варианта {context.user_data.get('parent_option')}")
                
                # Сохраняем пустой список вложенных вариантов (свободный ответ)
                question = context.user_data['current_question']
                parent_option = context.user_data['parent_option']
                
                logger.info(f"Текущий вопрос: '{question}', родительский вариант: '{parent_option}'")
                
                # Получаем номер вопроса
                question_num = -1
                for i, q in enumerate(self.questions):
                    if q == question:
                        question_num = i
                        break
                
                if question_num == -1:
                    logger.error(f"Не удалось найти вопрос '{question}' в списке вопросов")
                    await update.message.reply_text(
                        "❌ Не удалось найти вопрос.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
                
                # Получаем текущие варианты и проверяем наличие родительского варианта
                current_options = self.questions_with_options.get(question, [])
                
                if not current_options:
                    logger.error(f"Для вопроса '{question}' не найдены варианты ответов")
                    await update.message.reply_text(
                        "❌ Ошибка: для этого вопроса не найдены варианты ответов.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
                
                logger.info(f"Текущие варианты для вопроса '{question}': {current_options}")
                
                # Находим родительский вариант и устанавливаем пустой список подвариантов
                parent_option_found = False
                parent_option_index = -1
                
                for i, opt in enumerate(current_options):
                    if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option:
                        parent_option_found = True
                        parent_option_index = i
                        # Явно указываем пустой список для свободного ответа
                        opt["sub_options"] = []
                        logger.info(f"Установлен пустой список sub_options для '{parent_option}' - свободный ответ. Структура: {opt}")
                        break
                
                if not parent_option_found:
                    logger.error(f"Родительский вариант '{parent_option}' не найден в вопросе '{question}'")
                    await update.message.reply_text(
                        f"❌ Ошибка: вариант '{parent_option}' не найден в вопросе.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
                
                # Сохраняем обновленные варианты и логируем подробно каждый шаг
                logger.info(f"Отправка на сохранение для вопроса {question_num}, вариант '{parent_option}' с пустым списком sub_options: {current_options}")
                success = self.sheets.edit_question_options(question_num, current_options)
                
                if success:
                    logger.info(f"Успешно сохранен вариант '{parent_option}' с пустым списком sub_options, обновляем списки вопросов")
                    # Обновляем список вопросов
                    self.questions_with_options = self.sheets.get_questions_with_options()
                    self.questions = list(self.questions_with_options.keys())
                    
                    # Проверка сохранения пустого списка sub_options после обновления
                    found = False
                    updated_options = self.questions_with_options.get(question, [])
                    for opt in updated_options:
                        if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option:
                            found = True
                            if "sub_options" in opt and isinstance(opt["sub_options"], list) and opt["sub_options"] == []:
                                logger.info(f"✅ Проверка после обновления: вариант '{parent_option}' сохранил пустой список sub_options=[] (свободный ответ)")
                            else:
                                logger.warning(f"⚠️ Проверка после обновления: вариант '{parent_option}' НЕ имеет пустого списка sub_options! Текущая структура: {opt}")
                    
                    if not found:
                        logger.warning(f"⚠️ Проверка после обновления: вариант '{parent_option}' не найден в вопросе '{question}'")
                    
                    # Повторно проверяем структуру опций после обновления, чтобы видеть проблемы в логе
                    logger.info(f"Структура вопроса '{question}' после обновления:")
                    for i, opt in enumerate(updated_options):
                        if isinstance(opt, dict):
                            if "sub_options" in opt:
                                logger.info(f"  Опция {i+1}: '{opt['text']}', sub_options: {opt['sub_options']}")
                            else:
                                logger.info(f"  Опция {i+1}: '{opt['text']}', без sub_options")
                        else:
                            logger.info(f"  Опция {i+1}: '{opt}' (не dict)")
                    
                    # Обновляем списки вопросов в других обработчиках через application
                    await self._update_handlers_questions(update)
                    
                    # Сохраняем данные для последующего добавления подсказки свободного ответа
                    context.user_data['current_question'] = question
                    context.user_data['parent_option'] = parent_option
                    context.user_data['editing_option'] = parent_option
                    context.user_data['editing_question'] = question 
                    context.user_data['editing_question_num'] = question_num
                    
                    # Найдем индекс родительского варианта и сохраним его
                    for i, opt in enumerate(current_options):
                        if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option:
                            context.user_data['editing_option_index'] = i
                            break
                    
                    # Запрашиваем вопрос для свободного ответа
                    await update.message.reply_text(
                        f"✅ Вариант '{parent_option}' настроен как свободный ответ!\n\n"
                        f"Теперь введите вопрос, который будет показан пользователю при выборе этого варианта:",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    
                    # Проверяем, существует ли состояние ADDING_FREE_TEXT_PROMPT в обработчике разговоров
                    # Если состояние вызывает ошибку, возвращаем вместо него END
                    try:
                        # Переходим к состоянию добавления вопроса для свободного ответа
                        logger.info(f"Переход к состоянию ADDING_FREE_TEXT_PROMPT из handle_nested_options для варианта '{parent_option}'")
                        
                        # Вместо прямого возврата состояния, сделаем промежуточный шаг
                        # Сохраним требуемое состояние в контексте
                        context.user_data['next_state'] = ADDING_FREE_TEXT_PROMPT
                        
                        # Вызываем обработчик свободного ответа напрямую
                        # Эта логика должна быть согласована с логикой в handlers/admin_handlers.py
                        # и в conversation_handlers.py
                        await update.message.reply_text(
                            "Введите вопрос для свободного ответа:",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        
                        # Возвращаем состояние прямо из этого метода,
                        # чтобы избежать ошибки с неизвестным состоянием
                        logger.info(f"Возвращаем состояние ADDING_FREE_TEXT_PROMPT из handle_nested_options")
                        return ADDING_FREE_TEXT_PROMPT
                        
                    except Exception as e:
                        logger.error(f"Ошибка при переходе к состоянию ADDING_FREE_TEXT_PROMPT: {e}", exc_info=True)
                        # В случае ошибки возвращаем END, чтобы избежать ошибки в ConversationHandler
                        await update.message.reply_text(
                            f"✅ Вариант '{parent_option}' настроен как свободный ответ!\n\n"
                            f"Пожалуйста, используйте команду /edit_question для добавления текста вопроса.",
                            reply_markup=ReplyKeyboardRemove()
                        )
                        return ConversationHandler.END
                    
                else:
                    await update.message.reply_text(
                        "❌ Не удалось настроить свободный ответ.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                    return ConversationHandler.END
            
            # Если отмена
            if choice == "❌ Отмена":
                await update.message.reply_text(
                    "✅ Вопрос сохранен без вложенных вариантов.",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
                
            # Проверяем, не выбрано ли "Нет, завершить"
            if choice == "❌ Нет, завершить":
                logger.info(f"Пользователь выбрал '❌ Нет, завершить' при добавлении вложенных вариантов")
                await update.message.reply_text(
                    "✅ Вопрос с вложенными вариантами успешно сохранен!",
                    reply_markup=ReplyKeyboardRemove()
                )
                return ConversationHandler.END
                
            # Проверяем, не совпадает ли выбор с кнопками навигации или другими специальными кнопками
            special_buttons = [
                "✅ Да, к другому варианту", 
                "✅ Да, добавить вложенные варианты", 
                "❌ Нет, оставить как есть"
            ]
            if choice in special_buttons:
                logger.info(f"Получена специальная кнопка '{choice}' в режиме добавления подвариантов")
                # Обрабатываем как специальную кнопку навигации
                if choice == "✅ Да, к другому варианту":
                    # Код для обработки перехода к другому варианту
                    # Переход к обработчику "✅ Да, к другому варианту" ниже
                    context.user_data.pop('adding_sub_option', None)
                    # Продолжаем выполнение для перехода к блоку обработки "Да, к другому варианту"
                else:
                    # Для других специальных кнопок показываем сообщение о неверном выборе
                    await update.message.reply_text(
                        f"❌ Кнопка '{choice}' не подходит для текущего этапа. Пожалуйста, введите вложенный вариант или выберите одно из действий:",
                        reply_markup=ReplyKeyboardMarkup([
                            [KeyboardButton("✅ Готово")],
                            [KeyboardButton("❌ Отмена")]
                        ], resize_keyboard=True)
                    )
                    return ADDING_NESTED_OPTIONS
            
            # Добавляем новый вложенный вариант только если это не специальная кнопка
            if 'sub_options' not in context.user_data:
                context.user_data['sub_options'] = []
            
            context.user_data['sub_options'].append(choice)
            logger.info(f"Добавлен подвариант '{choice}' для '{context.user_data.get('parent_option', '')}'")

            # Запрашиваем следующий вложенный вариант
            keyboard = [
                [KeyboardButton("✅ Готово")],
                [KeyboardButton("❌ Отмена")]
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
        
        # Неизвестный выбор - эта часть будет выполняться, только если выбор не совпал
        # ни с одним из обрабатываемых вариантов выше
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
        
        # Получаем актуальные данные перед изменением
        self.questions_with_options = self.sheets.get_questions_with_options()
        self.questions = list(self.questions_with_options.keys())
        
        # Проверяем, что вопрос существует
        if question not in self.questions_with_options:
            logger.warning(f"Вопрос '{question}' не найден в актуальном списке вопросов")
            logger.info(f"Доступные вопросы: {self.questions}")
            await update.message.reply_text(
                "❌ Ошибка: вопрос не найден в актуальном списке",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
            
        current_options = self.questions_with_options[question]
        logger.info(f"Текущие варианты ответов для вопроса '{question}': {current_options}")
        
        # Проверяем, что вариант существует и находим его
        parent_found = False
        for i, opt in enumerate(current_options):
            if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                parent_option_index = i
                context.user_data['editing_option_index'] = i
                parent_found = True
                break
                
        if not parent_found:
            logger.warning(f"Вариант '{parent_option_text}' не найден в актуальном списке вариантов для вопроса '{question}'")
            logger.info(f"Доступные варианты: {[opt.get('text') for opt in current_options if isinstance(opt, dict) and 'text' in opt]}")
            await update.message.reply_text(
                f"❌ Ошибка: вариант '{parent_option_text}' не найден в актуальном списке",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Получаем родительский вариант
        parent_option = current_options[parent_option_index]
        logger.info(f"Родительский вариант: {parent_option}")
        
        # Проверяем, что это вариант со свободным ответом
        if not isinstance(parent_option.get("sub_options"), list):
            logger.warning(f"Вариант '{parent_option_text}' не имеет свойства sub_options или это не список")
            await update.message.reply_text(
                f"❌ Ошибка: вариант '{parent_option_text}' не является свободным ответом",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        if parent_option.get("sub_options") != []:
            logger.warning(f"Вариант '{parent_option_text}' имеет непустой список sub_options: {parent_option.get('sub_options')}")
            await update.message.reply_text(
                f"❌ Ошибка: вариант '{parent_option_text}' не является свободным ответом",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Добавляем поле free_text_prompt к родительскому варианту
        parent_option["free_text_prompt"] = prompt
        logger.info(f"Добавлен вопрос для свободного ответа к варианту '{parent_option_text}': '{prompt}'")
        
        # Обновляем варианты ответов
        logger.info(f"Сохраняем обновленные варианты ответов: {current_options}")
        
        # Важно! Модифицируем метод сохранения для включения free_text_prompt
        try:
            # Прямое обновление в sheets через специальный метод
            success = self.sheets.edit_question_options_with_free_text(question_num, current_options)
            
            if not success:
                # Запасной вариант через обычный метод
                logger.warning(f"Не удалось сохранить через специальный метод, используем обычный метод edit_question_options")
                success = self.sheets.edit_question_options(question_num, current_options)
                
            logger.info(f"Результат сохранения вопроса со свободным ответом: {success}")
        except AttributeError:
            # Если метод edit_question_options_with_free_text не существует
            logger.warning(f"Метод edit_question_options_with_free_text не найден, используем обычный метод")
            # Пытаемся напрямую передать текст подсказки в значение ячейки
            success = self.sheets.edit_question_options(question_num, current_options, free_text_prompt=prompt, parent_option_text=parent_option_text)
        
        if success:
            # Обновляем список вопросов
            self.questions_with_options = self.sheets.get_questions_with_options()
            self.questions = list(self.questions_with_options.keys())
            
            # Проверяем, что prompt сохранен
            saved_options = self.questions_with_options.get(question, [])
            prompt_saved = False
            for opt in saved_options:
                if isinstance(opt, dict) and opt.get("text") == parent_option_text:
                    if opt.get("free_text_prompt") == prompt:
                        prompt_saved = True
                        logger.info(f"✅ Вопрос для свободного ответа успешно сохранен для варианта '{parent_option_text}'")
                        break
                    
            if not prompt_saved:
                # Пробуем прямой подход к работе с таблицей, минуя промежуточные функции
                try:
                    # Прямая запись в ячейку с подсказкой для свободного ответа
                    logger.warning(f"⚠️ Вопрос для свободного ответа НЕ был сохранен для варианта '{parent_option_text}', пробуем прямой метод")
                    
                    # Запрашиваем прямой доступ к листу
                    worksheet = self.sheets.sheet.worksheet(QUESTIONS_SHEET)
                    row = question_num + 2  # +2 для учета заголовка и 0-индексации
                    col = 2  # Столбец с вариантами ответов
                    
                    # Получаем текущее значение ячейки
                    cell_value = worksheet.cell(row, col).value
                    logger.info(f"Текущее значение ячейки ({row}, {col}): {cell_value}")
                    
                    # Формируем новое значение с добавлением free_text_prompt
                    if "::" in cell_value:
                        # Для свободного ответа (с пустым списком sub_options)
                        new_value = f"{parent_option_text}::{prompt}"
                    else:
                        # Для обычного варианта
                        new_value = f"{parent_option_text}:::{prompt}"
                    
                    logger.info(f"Записываем в ячейку ({row}, {col}) значение: {new_value}")
                    worksheet.update_cell(row, col, new_value)
                    prompt_saved = True
                    logger.info(f"✅ Вопрос для свободного ответа успешно сохранен напрямую: {new_value}")
                except Exception as e:
                    logger.error(f"❌ Ошибка при прямой записи в ячейку: {e}", exc_info=True)
            
            await update.message.reply_text(
                f"✅ Вопрос для свободного ответа {'' if prompt_saved else 'НЕ '}добавлен: '{prompt}'",
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
                "❌ Не удалось добавить вопрос для свободного ответа",
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
            
            # Дополнительный проход для проверки подвариантов
            for question, options in self.questions_with_options.items():
                logger.info(f"Вопрос: '{question}' имеет {len(options)} вариантов ответа")
                for opt in options:
                    if isinstance(opt, dict) and "text" in opt:
                        # Проверяем наличие sub_options
                        has_sub_options = "sub_options" in opt
                        
                        if has_sub_options:
                            sub_opts = opt.get("sub_options", [])
                            
                            if isinstance(sub_opts, list) and sub_opts == []:
                                logger.info(f"🆓 Вариант '{opt['text']}' имеет пустой список sub_options=[] (СВОБОДНЫЙ ОТВЕТ)")
                            elif isinstance(sub_opts, list) and sub_opts:
                                logger.info(f"📋 Вариант '{opt['text']}' имеет подварианты: {sub_opts}")
                            else:
                                logger.info(f"⚠️ Вариант '{opt['text']}' имеет некорректное значение sub_options: {sub_opts}, тип: {type(sub_opts)}")
                        else:
                            logger.info(f"📌 Вариант '{opt['text']}' - обычный вариант без подвариантов (ключ sub_options отсутствует)")
            
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
                                handler_instance.questions_with_options = self.questions_with_options.copy()
                                handler_instance.questions = self.questions.copy()
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