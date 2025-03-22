"""
Обработчики для проведения опроса
"""

import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
import asyncio
from datetime import datetime

from models.states import *
from handlers.base_handler import BaseHandler
from config import QUESTIONS_SHEET  # Добавляем импорт для доступа к имени листа вопросов

# Настройка логирования
logger = logging.getLogger(__name__)

class SurveyHandler(BaseHandler):
    """Обработчики для проведения опроса"""
    
    async def begin_survey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало опроса"""
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} пытается зарегистрироваться")
        
        # Проверяем, проходил ли пользователь опрос
        if self.sheets.has_user_completed_survey(user_id):
            await update.message.reply_text(
                "❌ Вы уже проходили этот опрос. Повторное прохождение невозможно.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Проверяем, есть ли вопросы
        if not self.questions:
            await update.message.reply_text(
                "❌ В данный момент нет доступных вопросов.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        
        # Инициализируем список ответов
        context.user_data['answers'] = []
        
        # Отправляем первый вопрос
        return await self.send_question(update, context)
    
    async def send_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправка вопроса пользователю"""
        user_id = update.effective_user.id
        
        # Проверяем наличие ключа 'answers'
        if 'answers' not in context.user_data:
            context.user_data['answers'] = []
            logger.info(f"[{user_id}] Инициализирован пустой список ответов")
        
        current_question_num = len(context.user_data['answers'])
        
        # Показываем результаты, если ответили на все вопросы
        if current_question_num >= len(self.questions):
            logger.info(f"[{user_id}] Все вопросы пройдены, показываем результаты")
            
            text = "✅ *Спасибо за ваши ответы!*\n\n"
            text += "📋 *Ваши ответы:*\n"
            
            # Отображаем ответы с номерами вопросов
            for i, q in enumerate(self.questions):
                if i < len(context.user_data['answers']):
                    # Форматируем ответ для улучшения отображения
                    answer = context.user_data['answers'][i]
                    
                    # Добавляем номер вопроса в начало
                    formatted_question = q
                    if not formatted_question.startswith(f"{i+1}.") and not formatted_question.startswith(f"{i+1} "):
                        formatted_question = f"{i+1}. {formatted_question}"
                    
                    text += f"{formatted_question}: *{answer}*\n"
            
            text += "\nНажмите кнопку для завершения."
            
            # Показываем кнопки подтверждения
            reply_markup = ReplyKeyboardMarkup([
                [KeyboardButton("✅ Подтвердить")],
                [KeyboardButton("🔄 Начать заново")]
            ], resize_keyboard=True)
            
            await update.message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            return CONFIRMING
        
        # Получаем текущий вопрос
        current_question = self.questions[current_question_num]
        logger.info(f"[{user_id}] Отображается вопрос #{current_question_num+1}: {current_question}")
        
        # Детальная диагностика
        logger.info(f"[{user_id}] Детали вопроса #{current_question_num+1}: тип={type(current_question)}, длина={len(str(current_question))}")
        
        # Добавлена проверка и форматирование вопроса
        display_question = current_question
        
        # Если вопрос слишком короткий или это только число, пробуем найти более полное описание
        if len(str(current_question)) <= 3 or str(current_question).isdigit():
            logger.warning(f"[{user_id}] Обнаружен потенциально некорректный вопрос: '{current_question}'")
            
            # Пробуем получить вопрос с полным описанием
            try:
                # Получаем данные из таблицы вопросов напрямую
                all_questions = self.sheets.get_questions_with_options()
                found_full_question = False
                
                # Ищем в текущем списке вопросов по номеру
                question_number = str(current_question).strip()
                
                # Перебираем вопросы, чтобы найти тот, который не совпадает с уже заданными
                for full_question in all_questions.keys():
                    # Проверяем, что вопрос начинается с номера
                    if full_question.startswith(question_number + ".") or full_question.startswith(question_number + " "):
                        # Проверяем, что этот вопрос еще не задавался
                        already_asked = False
                        for i in range(current_question_num):
                            if self.questions[i] == full_question:
                                already_asked = True
                                break
                                
                        if not already_asked:
                            logger.info(f"[{user_id}] Заменяем короткий вопрос '{current_question}' на полный: '{full_question}'")
                            display_question = full_question
                            # Обновляем вопрос в списке вопросов для исправления проблемы
                            self.questions[current_question_num] = full_question
                            found_full_question = True
                            break
                        else:
                            logger.info(f"[{user_id}] Пропускаем уже заданный вопрос: '{full_question}'")
                
                # Если не нашли подходящий вопрос в словаре, ищем в листе напрямую
                if not found_full_question:
                    sheet_values = self.sheets.get_sheet_values(QUESTIONS_SHEET)
                    if sheet_values:
                        for row in sheet_values[1:]:  # Пропускаем заголовок
                            if row and row[0]:
                                # Проверяем, что вопрос начинается с номера
                                if (row[0].startswith(question_number + ".") or 
                                    row[0].startswith(question_number + " ")):
                                    
                                    # Проверяем, что этот вопрос еще не задавался
                                    already_asked = False
                                    for i in range(current_question_num):
                                        if self.questions[i] == row[0]:
                                            already_asked = True
                                            break
                                            
                                    if not already_asked:
                                        logger.info(f"[{user_id}] Заменяем короткий вопрос '{current_question}' на полный из таблицы: '{row[0]}'")
                                        display_question = row[0]
                                        # Обновляем вопрос в списке вопросов
                                        self.questions[current_question_num] = row[0]
                                        found_full_question = True
                                        break
                                    else:
                                        logger.info(f"[{user_id}] Пропускаем уже заданный вопрос из таблицы: '{row[0]}'")
                        
                        # Если мы все еще не нашли вопрос, это может быть новый вопрос
                        if not found_full_question:
                            logger.warning(f"[{user_id}] Не удалось найти полный текст для вопроса '{current_question}', оставляем как есть")
            except Exception as e:
                logger.error(f"[{user_id}] Ошибка при получении полного текста вопроса: {e}")
        
        # Проверяем, есть ли у текущего вопроса варианты ответов
        # Сначала проверяем варианты для отображаемого вопроса (он может отличаться от current_question)
        options = self.questions_with_options.get(display_question, [])
        if not options:
            # Если для display_question нет вариантов, проверяем для original_question
            options = self.questions_with_options.get(current_question, [])
            logger.info(f"[{user_id}] Используем варианты ответов для оригинального вопроса, так как для display_question их нет")
        
        # Добавляем диагностику вариантов ответов
        logger.info(f"[{user_id}] Варианты ответов для вопроса #{current_question_num+1}: {options}")
        
        # Проверяем, находимся ли мы в подварианте вопроса
        current_parent_answer = context.user_data.get('current_parent_answer')
        
        if current_parent_answer:
            logger.info(f"[{user_id}] Выбран родительский ответ: {current_parent_answer}")
            
            # Ищем варианты, соответствующие родительскому ответу
            parent_option = None
            for opt in options:
                if isinstance(opt, dict) and "text" in opt and opt["text"] == current_parent_answer:
                    parent_option = opt
                    break
            
            if parent_option:
                # Проверяем, есть ли у родительского варианта подварианты
                sub_options = parent_option.get("sub_options")
                
                # Проверяем, есть ли у родительского варианта подсказка для свободного ввода
                free_text_prompt = parent_option.get("free_text_prompt", "")
                
                # Проверяем формат подвариантов
                if sub_options is None or not isinstance(sub_options, list):
                    # Некорректные подварианты, сбрасываем родительский ответ
                    logger.warning(f"[{user_id}] Некорректный формат подвариантов: {sub_options}, сброс")
                    context.user_data.pop('current_parent_answer', None)
                    return await self.send_question(update, context)
                
                # Если у варианта есть подсказка для свободного ввода или список пуст, это свободный ответ
                if free_text_prompt or sub_options == []:
                    # Определяем подсказку для свободного ответа
                    if free_text_prompt:
                        prompt_text = f"*{display_question}*\n\n📝 *{free_text_prompt}*"
                        logger.info(f"[{user_id}] Использование подсказки для свободного ввода: {free_text_prompt}")
                    else:
                        prompt_text = f"*{display_question}*\n\n📝 *Введите свой ответ:*"
                    
                    await update.message.reply_text(
                        prompt_text,
                        parse_mode='Markdown',
                        reply_markup=ReplyKeyboardMarkup(
                            [[KeyboardButton("◀️ Назад к вариантам")]],
                            resize_keyboard=True
                        )
                    )
                    logger.info(f"[{user_id}] Запрошен свободный ответ на подвопрос: {prompt_text}")
                    return f"QUESTION_{current_question_num}_SUB"
                
                # Есть подварианты для выбора
                keyboard = []
                for sub_opt in sub_options:
                    # Проверяем, не является ли подвариант подсказкой для свободного ввода
                    if not ("вопрос для" in sub_opt.lower() or "введите" in sub_opt.lower()):
                        keyboard.append([KeyboardButton(sub_opt)])
                
                # Если клавиатура пуста после фильтрации, это значит, что все подварианты были подсказками
                # В этом случае, обрабатываем как свободный ввод
                if not keyboard:
                    free_text_prompt = sub_options[0] if sub_options else "Введите свой ответ"
                    
                    # Определяем подсказку для свободного ответа
                    prompt_text = f"*{display_question}*\n\n📝 *{free_text_prompt}*"
                    
                    await update.message.reply_text(
                        prompt_text,
                        parse_mode='Markdown',
                        reply_markup=ReplyKeyboardMarkup(
                            [[KeyboardButton("◀️ Назад к вариантам")]],
                            resize_keyboard=True
                        )
                    )
                    logger.info(f"[{user_id}] Обнаружена и преобразована подсказка в свободный ввод: {free_text_prompt}")
                    return f"QUESTION_{current_question_num}_SUB"
                
                # Добавляем кнопку возврата к родительским вариантам
                keyboard.append([KeyboardButton("◀️ Назад к вариантам")])
                
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                # Отправляем сообщение с подвариантами
                await update.message.reply_text(
                    f"*{display_question}*\n\nВыберите вариант:",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                logger.info(f"[{user_id}] Отображаются подварианты для ответа '{current_parent_answer}'")
                return f"QUESTION_{current_question_num}_SUB"
            else:
                # Родительский вариант не найден
                logger.warning(f"[{user_id}] Родительский вариант не найден: {current_parent_answer}")
                context.user_data.pop('current_parent_answer', None)
                return await self.send_question(update, context)
        
        # Обычный вопрос (не подвариант)
        # Если у вопроса нет вариантов ответа, запрашиваем свободный ввод
        if not options:
            await update.message.reply_text(
                f"*{display_question}*\n\n📝 Введите свой ответ:",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove()
            )
            logger.info(f"[{user_id}] Запрошен свободный ответ на вопрос #{current_question_num+1}")
            return f"QUESTION_{current_question_num}"
        
        # Создаем клавиатуру с вариантами ответов
        keyboard = []
        
        # Добавляем все варианты ответов
        for opt in options:
            if isinstance(opt, dict) and "text" in opt:
                option_text = opt["text"]
                
                # Проверяем, если это вариант со свободным ответом (free_text_prompt)
                has_free_text = isinstance(opt.get("sub_options"), list) and opt["sub_options"] == []
                has_prompt = "free_text_prompt" in opt
                
                # Логируем информацию о варианте для отладки
                if has_free_text and has_prompt:
                    logger.info(f"[{user_id}] Обнаружен вариант со свободным вводом: {opt['text']} с подсказкой: {opt.get('free_text_prompt', '')}")
                
                # Добавляем вариант в клавиатуру без смайлика
                keyboard.append([KeyboardButton(option_text)])
            else:
                # Простой вариант ответа
                keyboard.append([KeyboardButton(str(opt))])
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Отправляем вопрос с вариантами ответов
        await update.message.reply_text(
            f"*{display_question}*\n\nВыберите вариант:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        logger.info(f"[{user_id}] Отображен вопрос #{current_question_num+1} с {len(keyboard)} вариантами ответов")
        return f"QUESTION_{current_question_num}"
    
    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ответов пользователя"""
        answer = update.message.text
        user_id = update.effective_user.id
        
        # Проверяем наличие ключа 'answers'
        if 'answers' not in context.user_data:
            context.user_data['answers'] = []
            logger.warning(f"[{user_id}] Инициализирован пустой список ответов")
        
        current_question_num = len(context.user_data['answers'])
        
        # Обработка подтверждения ответов
        if current_question_num == len(self.questions):
            if answer == "✅ Подтвердить":
                logger.info(f"[{user_id}] Начало процесса сохранения ответов")
                start_time = datetime.now()
                
                # Сохраняем ответы с ID пользователя
                success = self.sheets.save_answers(context.user_data['answers'], user_id)
                
                if success:
                    save_duration = (datetime.now() - start_time).total_seconds()
                    logger.info(f"[{user_id}] Ответы сохранены за {save_duration:.2f} секунд")
                    
                    # Отправляем сообщение о завершении опроса
                    await self.finish_survey(update, context)
                    
                    # Запускаем асинхронное обновление статистики после отправки сообщения
                    logger.info(f"[{user_id}] Запуск асинхронного обновления статистики")
                    asyncio.create_task(self.update_statistics_async())
                else:
                    logger.error(f"[{user_id}] Ошибка при сохранении ответов")
                    await update.message.reply_text(
                        "❌ Произошла ошибка при сохранении ответов. Пожалуйста, попробуйте позже.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                
                # Очищаем данные пользователя
                context.user_data.clear()
                return ConversationHandler.END
                
            elif answer == "🔄 Начать заново":
                # Очищаем ответы и начинаем заново
                context.user_data['answers'] = []
                context.user_data.pop('current_parent_answer', None)
                return await self.send_question(update, context)
            
            else:
                # Неизвестный ответ при подтверждении
                await update.message.reply_text(
                    "❌ Пожалуйста, выберите один из вариантов.",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("✅ Подтвердить")],
                        [KeyboardButton("🔄 Начать заново")]
                    ], resize_keyboard=True)
                )
                return CONFIRMING
        
        # Получаем текущий вопрос и его варианты ответов
        current_question = self.questions[current_question_num]
        available_options = self.questions_with_options[current_question]
        
        # Проверка для вложенных вариантов (подвопросов)
        if current_question_num < len(self.questions) and context.user_data.get('current_parent_answer'):
            parent_answer = context.user_data.get('current_parent_answer')
            parent_option = None
            
            # Находим родительский вариант
            for opt in available_options:
                if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_answer:
                    parent_option = opt
                    break
            
            if parent_option:
                # Добавляем отладочную информацию о структуре родительского варианта
                logger.info(f"[{user_id}] Родительский вариант '{parent_answer}', структура: {parent_option}")
                
                # Специальная проверка для возврата к основным вариантам
                if answer == "◀️ Назад к вариантам":
                    # Возвращаемся к основным вариантам
                    context.user_data.pop('current_parent_answer', None)
                    return await self.send_question(update, context)
                
                # Проверяем, является ли это свободным ответом для вложенного варианта
                # Явная проверка на пустой список sub_options (свободный ответ)
                if "sub_options" in parent_option and isinstance(parent_option["sub_options"], list) and parent_option["sub_options"] == []:
                    # Обрабатываем свободный ответ
                    # Формируем структурированный ответ с информацией о подсказке, если она была
                    free_text_prompt = parent_option.get("free_text_prompt", "")
                    
                    # Сохраняем свободный ответ в структурированном формате
                    if free_text_prompt:
                        full_answer = f"{parent_answer} - {answer}"
                        logger.info(f"[{user_id}] Сохранен свободный ответ с пользовательским вопросом: {full_answer} (вопрос: {free_text_prompt})")
                    else:
                        full_answer = f"{parent_answer} - {answer}"
                        logger.info(f"[{user_id}] Сохранен свободный ответ: {full_answer}")
                    
                    context.user_data['answers'].append(full_answer)
                    # Очищаем текущий родительский ответ
                    context.user_data.pop('current_parent_answer', None)
                    
                    # Переходим к следующему вопросу
                    return await self.send_question(update, context)
                
                # Проверяем наличие подвариантов
                sub_options = parent_option.get("sub_options")
                
                # Проверяем, имеет ли вариант подсказку для свободного ввода
                if "free_text_prompt" in parent_option and parent_option["free_text_prompt"]:
                    # Обрабатываем как свободный ответ, даже если подварианты не пустые
                    free_text_prompt = parent_option["free_text_prompt"]
                    full_answer = f"{parent_answer} - {answer}"
                    logger.info(f"[{user_id}] Сохранен свободный ответ с подсказкой: {full_answer} (подсказка: {free_text_prompt})")
                    
                    context.user_data['answers'].append(full_answer)
                    # Очищаем текущий родительский ответ
                    context.user_data.pop('current_parent_answer', None)
                    
                    # Переходим к следующему вопросу
                    return await self.send_question(update, context)
                
                # Если это не свободный ответ, но у варианта нет подвариантов или они некорректны
                if sub_options is None or not isinstance(sub_options, list) or not sub_options:
                    # Нет подвариантов или sub_options не является списком, сохраняем основной ответ
                    context.user_data['answers'].append(parent_answer)
                    # Очищаем текущий родительский ответ
                    context.user_data.pop('current_parent_answer', None)
                    logger.info(f"[{user_id}] Сохранен ответ без подвариантов: {parent_answer}")
                    
                    # Переходим к следующему вопросу
                    return await self.send_question(update, context)
                
                # Проверяем, соответствует ли ответ одному из подвариантов
                if answer not in sub_options:
                    # Ответ не соответствует ни одному из подвариантов
                    keyboard = [[KeyboardButton(sub_opt)] for sub_opt in sub_options]
                    keyboard.append([KeyboardButton("◀️ Назад к вариантам")])
                    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                    
                    await update.message.reply_text(
                        "❌ Пожалуйста, выберите один из предложенных вариантов:",
                        reply_markup=reply_markup
                    )
                    return f"QUESTION_{current_question_num}_SUB"
                
                # Сохраняем полный ответ (родительский + дочерний)
                full_answer = f"{parent_answer} - {answer}"
                context.user_data['answers'].append(full_answer)
                # Очищаем текущий родительский ответ
                context.user_data.pop('current_parent_answer', None)
                logger.info(f"[{user_id}] Сохранен составной ответ: {full_answer}")
                
                # Переходим к следующему вопросу
                return await self.send_question(update, context)
            else:
                # Если родительский вариант не найден, сбрасываем context.user_data['current_parent_answer']
                logger.warning(f"[{user_id}] Родительский вариант '{parent_answer}' не найден")
                context.user_data.pop('current_parent_answer', None)
                # Повторно отправляем текущий вопрос
                return await self.send_question(update, context)
        
        # Обработка ответов на основные вопросы        
        # Проверяем, есть ли вариант среди доступных опций
        available_options = self.questions_with_options.get(current_question, [])
        
        # Проверяем, соответствует ли ответ одному из вариантов
        is_valid_option = False
        selected_option = None
        
        for opt in available_options:
            if isinstance(opt, dict) and "text" in opt and opt["text"] == answer:
                is_valid_option = True
                selected_option = opt
                # Добавляем отладочную информацию о структуре выбранного варианта
                logger.info(f"[{user_id}] Выбран вариант: {answer}, структура: {selected_option}")
                break
            elif not isinstance(opt, dict) and str(opt) == answer:
                is_valid_option = True
                break
        
        if not is_valid_option:
            # Если ответ не соответствует ни одному из вариантов или нет доступных вариантов,
            # считаем это свободным ответом для вопроса без вариантов
            context.user_data['answers'].append(answer)
            logger.info(f"[{user_id}] Сохранен свободный ответ для вопроса без вариантов: {answer}")
        else:
            # Если у выбранного варианта есть ключ sub_options
            if selected_option and "sub_options" in selected_option:
                sub_options = selected_option.get("sub_options")
                # Добавляем отладочную информацию о структуре выбранного варианта и его подвариантах
                logger.info(f"[{user_id}] Проверка sub_options для '{answer}': {sub_options}, тип: {type(sub_options)}")
                
                # Проверяем тип sub_options и его содержимое
                if isinstance(sub_options, list):
                    if sub_options == []:  # Пустой список - свободный ответ
                        # Это свободный ответ (явно указан пустой список)
                        context.user_data['current_parent_answer'] = answer
                        
                        # Запоминаем пользовательский вопрос для свободного ответа, если он задан
                        free_text_prompt = selected_option.get("free_text_prompt", "")
                        if free_text_prompt:
                            logger.info(f"[{user_id}] Найден пользовательский вопрос для свободного ввода: {free_text_prompt}")
                        
                        # ВАЖНОЕ ИЗМЕНЕНИЕ: Если выбран вариант с свободным вводом (пустой список sub_options),
                        # переходим к методу send_question, который отобразит форму ввода
                        logger.info(f"[{user_id}] Установлен родительский ответ для свободного ввода: {answer}")
                        return await self.send_question(update, context)
                    # Проверяем, является ли первый подвариант подсказкой для свободного ввода
                    elif sub_options and isinstance(sub_options[0], str) and ("вопрос для" in sub_options[0].lower() or "введите" in sub_options[0].lower()):
                        # Это свободный ответ с подсказкой во вложенном варианте
                        context.user_data['current_parent_answer'] = answer
                        
                        # Сохраняем подсказку как free_text_prompt
                        free_text_prompt = sub_options[0]
                        selected_option["free_text_prompt"] = free_text_prompt
                        selected_option["sub_options"] = []  # Делаем пустой список, чтобы обозначить свободный ответ
                        
                        logger.info(f"[{user_id}] Преобразован вариант в свободный ввод с подсказкой: {free_text_prompt}")
                        logger.info(f"[{user_id}] Установлен родительский ответ для свободного ввода: {answer}")
                        return await self.send_question(update, context)
                    elif sub_options:  # Непустой список - выбор подварианта
                        # Есть вложенные варианты для выбора
                        context.user_data['current_parent_answer'] = answer
                        logger.info(f"[{user_id}] Установлен родительский ответ для выбора подвариантов: {answer}")
                        return await self.send_question(update, context)
                
            # Это обычный вариант без подвариантов или с некорректными подвариантами
            context.user_data['answers'].append(answer)
            logger.info(f"[{user_id}] Сохранен обычный ответ: {answer}")
        
        # Переходим к следующему вопросу
        return await self.send_question(update, context)
    
    async def finish_survey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершение опроса и благодарность пользователю"""
        user_id = update.effective_user.id
        
        # Отправляем сообщение о завершении
        await update.message.reply_text(
            "Спасибо за прохождение опроса! Ваши ответы сохранены.",
            reply_markup=ReplyKeyboardRemove()
        )
        
        logger.info(f"[{user_id}] Опрос завершен, сохранено ответов: {len(context.user_data.get('answers', []))}")
        return ConversationHandler.END
    
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ статистики опроса"""
        logger.info(f"Пользователь {update.effective_user.id} запросил статистику")
        
        # Получаем общее количество пройденных опросов
        total_surveys = self.sheets.get_total_surveys_count()
        
        # Формируем заголовок статистики с общим количеством
        statistics = f"📊 *Статистика опроса*\n👥 *Всего пройдено: {total_surveys}*\n\n"
        
        # Получаем данные статистики
        stats_data = self.sheets.get_statistics()
        
        # Проверяем, есть ли статистика
        if not stats_data:
            statistics = "📊 *Статистика недоступна*. Нет вопросов с вариантами ответов или еще не получено ответов."
            
            # Отправляем статистику
            await update.message.reply_text(
                statistics,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode='Markdown'
            )
            
            return ConversationHandler.END
        
        # Группируем статистику по вопросам
        grouped_stats = {}
        for question, option, count in stats_data:
            if question not in grouped_stats:
                grouped_stats[question] = []
            
            # Добавляем информацию о варианте ответа
            grouped_stats[question].append((option, count))
        
        # Формируем текст статистики
        for question, options_data in grouped_stats.items():
            # Добавляем заголовок вопроса
            statistics += f"*{question}*\n"
            
            # Организуем вложенные варианты
            main_options = {}
            sub_options = {}
            
            # Сначала разделяем основные варианты и вложенные
            for option, count in options_data:
                if " - " in option:
                    # Это вложенный вариант
                    main_part, sub_part = option.split(" - ", 1)
                    if main_part not in sub_options:
                        sub_options[main_part] = []
                    sub_options[main_part].append((sub_part, count))
                else:
                    # Это основной вариант
                    main_options[option] = count
            
            # Выводим основные варианты с их вложенными вариантами
            for option, count in main_options.items():
                statistics += f"└ {option}: {count}\n"
                
                # Если у основного варианта есть вложенные, выводим их
                if option in sub_options:
                    for sub_option, sub_count in sub_options[option]:
                        statistics += f"   └ {sub_option}: {sub_count}\n"
            
            # Добавляем пустую строку между вопросами
            statistics += "\n"
        
        # Проверяем длину статистики и разбиваем на части при необходимости
        if len(statistics) > 4000:
            logger.warning(f"Статистика слишком длинная ({len(statistics)} символов), разбиваем на части")
            
            # Разбиваем на части примерно по 4000 символов
            parts = []
            current_part = ""
            for line in statistics.split('\n'):
                if len(current_part) + len(line) + 1 > 4000:
                    parts.append(current_part)
                    current_part = line
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part)
            
            # Отправляем каждую часть отдельным сообщением
            for i, part in enumerate(parts):
                await update.message.reply_text(
                    part,
                    reply_markup=ReplyKeyboardRemove() if i == len(parts) - 1 else None,
                    parse_mode='Markdown'
                )
        else:
            # Отправляем статистику с поддержкой Markdown
            await update.message.reply_text(
                statistics,
                reply_markup=ReplyKeyboardRemove(),
                parse_mode='Markdown'
            )
        
        return ConversationHandler.END

    async def update_statistics_async(self):
        """Асинхронное обновление статистики после опроса"""
        try:
            start_time = datetime.now()
            logger.info(f"Запуск обновления статистики...")
            
            # Выполняем обновление
            stats_updated = self.sheets.update_statistics()
            
            duration = (datetime.now() - start_time).total_seconds()
            if stats_updated:
                logger.info(f"Статистика успешно обновлена за {duration:.2f} секунд")
            else:
                logger.warning(f"Обновление статистики не выполнено за {duration:.2f} секунд")
        
        except Exception as e:
            logger.error(f"Ошибка при обновлении статистики: {e}") 