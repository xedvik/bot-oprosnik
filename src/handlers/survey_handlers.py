"""
Обработчики для проведения опроса
"""

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
import asyncio
from datetime import datetime
import time

from models.states import *
from handlers.base_handler import BaseHandler
from config import QUESTIONS_SHEET  # Добавляем импорт для доступа к имени листа вопросов
from utils.logger import get_logger
from utils.sheets_cache import sheets_cache

# Настройка логирования
logger = get_logger()

class SurveyHandler(BaseHandler):
    """Обработчики для проведения опроса"""
    
    async def begin_survey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало опроса"""
        user_id = update.effective_user.id
        logger.user_action(user_id, "Начало опроса", "Попытка регистрации")
        
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
        logger.warning(f"Принудительная инициализация списка ответов (answers_init)", 
                    details={"user_id": user_id, "причина": "отсутствовал ключ 'answers'"})
        
        # Отправляем первый вопрос
        return await self.send_question(update, context)
    
    async def send_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отправка вопроса пользователю"""
        user_id = update.effective_user.id
        
        # Проверяем наличие ключа 'answers'
        if 'answers' not in context.user_data:
            context.user_data['answers'] = []
            logger.warning(f"Принудительная инициализация списка ответов (answers_init)", 
                        details={"user_id": user_id, "причина": "отсутствовал ключ 'answers'"})
        
        current_question_num = len(context.user_data['answers'])
        
        # Показываем результаты, если ответили на все вопросы
        if current_question_num >= len(self.questions):
            logger.user_action(user_id, "Завершение опроса", details={"причина": "все вопросы пройдены"})
            
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
        logger.user_action(user_id, "Отображение вопроса", details={"номер": current_question_num+1, "вопрос": current_question})
        
        # Детальная диагностика
        logger.data_processing("вопрос", "Анализ вопроса", details={"номер": current_question_num+1, "тип": str(type(current_question)), 
                               "длина": len(str(current_question)), "user_id": user_id})
        
        # Добавлена проверка и форматирование вопроса
        display_question = current_question
        
        # Если вопрос слишком короткий или это только число, пробуем найти более полное описание
        if len(str(current_question)) <= 3 or str(current_question).isdigit():
            logger.warning(f"Обнаружен потенциально некорректный вопрос: '{current_question}' (некорректный_вопрос)", 
                          details={"user_id": user_id, "длина": len(str(current_question))})
            
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
                            logger.data_processing("вопрос", "Замена короткого вопроса", details={"вопрос": current_question, 
                                                  "на": full_question, "user_id": user_id})
                            display_question = full_question
                            # Обновляем вопрос в списке вопросов для исправления проблемы
                            self.questions[current_question_num] = full_question
                            found_full_question = True
                            break
                        else:
                            logger.data_processing("вопрос", "Пропуск вопроса", details={"вопрос": full_question, 
                                                  "причина": "уже задан", "user_id": user_id})
                
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
                                        logger.data_processing("вопрос", "Замена короткого вопроса", details={"вопрос": current_question, 
                                                      "на": row[0], "user_id": user_id})
                                        display_question = row[0]
                                        # Обновляем вопрос в списке вопросов
                                        self.questions[current_question_num] = row[0]
                                        found_full_question = True
                                        break
                                    else:
                                        logger.data_processing("вопрос", "Пропуск вопроса", details={"вопрос": row[0], 
                                                      "причина": "уже задан", "user_id": user_id})
                        
                        # Если мы все еще не нашли вопрос, это может быть новый вопрос
                        if not found_full_question:
                            logger.warning(f"Не удалось найти полный текст для вопроса (полный_текст_не_найден)", 
                                        details={"вопрос": current_question, "user_id": user_id})
            except Exception as e:
                logger.error("получение_полного_текста_вопроса", e, details={"user_id": user_id, "question": current_question})
        
        # Проверяем, есть ли у текущего вопроса варианты ответов
        # Сначала проверяем варианты для отображаемого вопроса (он может отличаться от current_question)
        options = self.questions_with_options.get(display_question, [])
        if not options:
            # Если для display_question нет вариантов, проверяем для original_question
            options = self.questions_with_options.get(current_question, [])
            logger.data_processing("варианты", "Использование вариантов оригинального вопроса", 
                                details={"причина": "для display_question нет вариантов", "user_id": user_id})
        
        # Добавляем диагностику вариантов ответов
        logger.data_processing("варианты", "Анализ вариантов ответов", 
                            details={"номер_вопроса": current_question_num+1, "вариантов": len(options), "user_id": user_id})
        
        # Проверяем, находимся ли мы в подварианте вопроса
        current_parent_answer = context.user_data.get('current_parent_answer')
        
        if current_parent_answer:
            logger.user_action(user_id, "Работа с подвариантами", 
                            details={"родительский_ответ": current_parent_answer})
            
            # Ищем варианты, соответствующие родительскому ответу
            parent_option = None
            for opt in options:
                if isinstance(opt, dict) and "text" in opt and opt["text"] == current_parent_answer:
                    parent_option = opt
                    break
            
            if parent_option:
                # Проверяем, есть ли у родительского варианта подварианты
                sub_options = parent_option.get("sub_options")
                
                # Проверяем, есть ли у родительского варианта подсказку для свободного ввода
                free_text_prompt = parent_option.get("free_text_prompt", "")
                
                # Проверяем формат подвариантов
                if sub_options is None or not isinstance(sub_options, list):
                    # Некорректные подварианты, сбрасываем родительский ответ
                    logger.warning(f"Некорректный формат подвариантов, сброс (некорректные_подварианты)", 
                                 details={"подварианты": str(sub_options), "user_id": user_id})
                    context.user_data.pop('current_parent_answer', None)
                    return await self.send_question(update, context)
                
                # Если у варианта есть подсказка для свободного ответа или список пуст, это свободный ответ
                if free_text_prompt or sub_options == []:
                    # Определяем подсказку для свободного ответа
                    if free_text_prompt:
                        prompt_text = f"*{display_question}*\n\n📝 *{free_text_prompt}*"
                        logger.user_action(user_id, "Использование подсказки для свободного ввода", 
                                        details={"подсказка": free_text_prompt})
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
                    logger.user_action(user_id, "Запрос свободного ответа", 
                                     details={"тип": "подвопрос", "текст_подсказки": prompt_text[:50] + "..."})
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
                    logger.user_action(user_id, "Обнаружение свободного ввода", 
                                   details={"тип": "из подсказки", "подсказка": free_text_prompt[:50]})
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
                
                logger.user_action(user_id, "Отображение подвариантов", 
                                details={"родительский_ответ": current_parent_answer, "количество": len(keyboard)-1})
                return f"QUESTION_{current_question_num}_SUB"
            else:
                # Родительский вариант не найден
                logger.warning(f"Родительский вариант не найден (родительский_вариант_не_найден)", 
                            details={"вариант": current_parent_answer, "user_id": user_id})
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
            logger.user_action(user_id, "Запрос свободного ответа", 
                            details={"вопрос": current_question_num+1, "тип": "основной вопрос"})
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
                    logger.data_processing("варианты", "Анализ варианта со свободным вводом", 
                                       details={"вариант": opt['text'], "подсказка": opt.get('free_text_prompt', '')[:50], "user_id": user_id})
                
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
        
        logger.user_action(user_id, "Отображение вопроса с вариантами", 
                       details={"номер": current_question_num+1, "количество_вариантов": len(keyboard)})
        return f"QUESTION_{current_question_num}"
    
    async def handle_answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ответов пользователя"""
        answer = update.message.text
        user_id = update.effective_user.id
        
        # Проверяем наличие ключа 'answers'
        if 'answers' not in context.user_data:
            context.user_data['answers'] = []
            logger.warning(f"Принудительная инициализация списка ответов (answers_init)", 
                        details={"user_id": user_id, "причина": "отсутствовал ключ 'answers'"})
        
        current_question_num = len(context.user_data['answers'])
        
        # Обработка подтверждения ответов
        if current_question_num == len(self.questions):
            if answer == "✅ Подтвердить":
                logger.user_action(user_id, "Подтверждение ответов", 
                               details={"действие": "начало сохранения"})
                start_time = datetime.now()
                
                # Асинхронно сохраняем ответы с ID пользователя
                try:
                    success = await self.sheets.async_save_answers(context.user_data['answers'], user_id)
                    
                    if success:
                        save_duration = (datetime.now() - start_time).total_seconds()
                        logger.data_processing("ответы", "Сохранение ответов", 
                                          details={"user_id": user_id, "количество": len(context.user_data['answers']), "длительность": f"{save_duration:.2f} сек"})
                        
                        # Отправляем сообщение о завершении опроса
                        await self.finish_survey(update, context)
                        
                        # Запускаем асинхронное обновление статистики после отправки сообщения
                        logger.data_processing("статистика", "Запуск обновления статистики", 
                                           details={"режим": "асинхронный", "user_id": user_id})
                        asyncio.create_task(self.update_statistics_async())
                        
                        # Важно! Очищаем данные пользователя для предотвращения дальнейшей обработки
                        context.user_data.clear()
                        return ConversationHandler.END
                    else:
                        logger.error("сохранение_ответов", None, user_id=user_id, details={"operation": "save_answers", "status": "failed"})
                        await update.message.reply_text(
                            "⚠️ Произошла ошибка при сохранении ответов. Пожалуйста, попробуйте ещё раз."
                        )
                        return "CONFIRMING"
                except Exception as e:
                    logger.error("сохранение_ответов", e, user_id=user_id, details={"operation": "async_save_answers"})
                    await update.message.reply_text(
                        "⚠️ Произошла ошибка при сохранении ответов. Пожалуйста, попробуйте ещё раз."
                    )
                    return "CONFIRMING"
            
            elif answer == "🔄 Начать заново":
                # Очищаем ответы и начинаем заново
                context.user_data.clear()
                return await self.begin_survey(update, context)
            
            else:
                await update.message.reply_text(
                    "❌ Пожалуйста, выберите один из вариантов.",
                    reply_markup=ReplyKeyboardMarkup([
                        [KeyboardButton("✅ Подтвердить")],
                        [KeyboardButton("🔄 Начать заново")]
                    ], resize_keyboard=True)
                )
                return CONFIRMING
        
        # Убеждаемся, что мы не вышли за границы вопросов после успешного сохранения
        if current_question_num >= len(self.questions):
            logger.warning(f"Попытка доступа к несуществующему вопросу (question_index_out_of_range)",
                          details={"user_id": user_id, "current_num": current_question_num, "total_questions": len(self.questions)})
            # Перенаправляем на начало опроса
            context.user_data.clear()
            return await self.begin_survey(update, context)
            
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
                logger.data_processing("варианты", "Анализ родительского варианта", 
                                   details={"вариант": parent_answer, "структура": str(parent_option)[:100], "user_id": user_id})
                
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
                        logger.user_action(user_id, "Сохранение свободного ответа", 
                                        details={"тип": "с пользовательским вопросом", "ответ": full_answer, "вопрос": free_text_prompt[:50]})
                    else:
                        full_answer = f"{parent_answer} - {answer}"
                        logger.user_action(user_id, "Сохранение свободного ответа", 
                                        details={"ответ": full_answer})
                    
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
                    logger.user_action(user_id, "Обработка свободного ответа", 
                                    details={"тип": "подсказка из подвариантов", "подсказка": free_text_prompt[:50]})
                    
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
                    logger.user_action(user_id, "Сохранение ответа", 
                                   details={"тип": "без подвариантов", "ответ": parent_answer})
                    
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
                logger.user_action(user_id, "Сохранение составного ответа", 
                               details={"ответ": full_answer})
                
                # Переходим к следующему вопросу
                return await self.send_question(update, context)
            else:
                # Если родительский вариант не найден, сбрасываем context.user_data['current_parent_answer']
                logger.warning(f"Родительский вариант не найден (родительский_вариант_не_найден)", 
                             details={"вариант": current_parent_answer, "user_id": user_id})
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
                logger.data_processing("варианты", "Анализ выбранного варианта", 
                                   details={"ответ": answer, "структура": str(selected_option)[:100], "user_id": user_id})
                break
            elif not isinstance(opt, dict) and str(opt) == answer:
                is_valid_option = True
                break
        
        if not is_valid_option:
            # Если ответ не соответствует ни одному из вариантов или нет доступных вариантов,
            # считаем это свободным ответом для вопроса без вариантов
            context.user_data['answers'].append(answer)
            logger.user_action(user_id, "Сохранение ответа", 
                           details={"тип": "свободный для вопроса без вариантов", "ответ": answer})
        else:
            # Если у выбранного варианта есть ключ sub_options
            if selected_option and "sub_options" in selected_option:
                sub_options = selected_option.get("sub_options")
                # Добавляем отладочную информацию о структуре выбранного варианта и его подвариантах
                logger.data_processing("варианты", "Проверка подвариантов", 
                                   details={"ответ": answer, "тип_подвариантов": str(type(sub_options)), "user_id": user_id})
                
                # Проверяем тип sub_options и его содержимое
                if isinstance(sub_options, list):
                    if sub_options == []:  # Пустой список - свободный ответ
                        # Это свободный ответ (явно указан пустой список)
                        context.user_data['current_parent_answer'] = answer
                        
                        # Запоминаем пользовательский вопрос для свободного ответа, если он задан
                        free_text_prompt = selected_option.get("free_text_prompt", "")
                        if free_text_prompt:
                            logger.data_processing("варианты", "Обработка пользовательского вопроса", 
                                               details={"вопрос_для_ввода": free_text_prompt[:50], "user_id": user_id})
                        
                        # Сохраняем подсказку как free_text_prompt, если она не установлена и есть элементы в sub_options
                        if not free_text_prompt and sub_options and len(sub_options) > 0:
                            free_text_prompt = sub_options[0]
                            selected_option["free_text_prompt"] = free_text_prompt
                        
                        selected_option["sub_options"] = []  # Делаем пустой список, чтобы обозначить свободный ответ
                        
                        logger.data_processing("варианты", "Преобразование подсказки", 
                                          details={"тип": "в свободный ввод", "подсказка": free_text_prompt[:50], "user_id": user_id})
                        logger.user_action(user_id, "Подготовка свободного ввода", 
                                       details={"тип": "установка родительского ответа", "ответ": answer})
                        return await self.send_question(update, context)
                    # Проверяем, является ли первый подвариант подсказкой для свободного ввода
                    elif sub_options and isinstance(sub_options[0], str) and ("вопрос для" in sub_options[0].lower() or "введите" in sub_options[0].lower()):
                        # Это свободный ответ с подсказкой во вложенном варианте
                        context.user_data['current_parent_answer'] = answer
                        
                        # Сохраняем подсказку как free_text_prompt
                        free_text_prompt = sub_options[0] if sub_options and len(sub_options) > 0 else "Введите свой ответ"
                        selected_option["free_text_prompt"] = free_text_prompt
                        selected_option["sub_options"] = []  # Делаем пустой список, чтобы обозначить свободный ответ
                        
                        logger.data_processing("варианты", "Преобразование подсказки", 
                                          details={"тип": "в свободный ввод", "подсказка": free_text_prompt[:50], "user_id": user_id})
                        logger.user_action(user_id, "Подготовка свободного ввода", 
                                       details={"тип": "установка родительского ответа", "ответ": answer})
                        return await self.send_question(update, context)
                    elif sub_options:  # Непустой список - выбор подварианта
                        # Есть вложенные варианты для выбора
                        context.user_data['current_parent_answer'] = answer
                        logger.user_action(user_id, "Подготовка подвариантов", 
                                       details={"тип": "установка родительского ответа", "ответ": answer})
                        return await self.send_question(update, context)
                
            # Это обычный вариант без подвариантов или с некорректными подвариантами
            context.user_data['answers'].append(answer)
            logger.user_action(user_id, "Сохранение ответа", 
                           details={"тип": "без подвариантов", "ответ": answer})
        
        # Переходим к следующему вопросу
        return await self.send_question(update, context)
    
    async def finish_survey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Завершение опроса и благодарность пользователю"""
        # Вызываем метод базового класса вместо использования своего кода
        return await super().finish_survey(update, context)
    
    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ статистики опроса"""
        user_id = update.effective_user.id
        logger.user_action(user_id, "Запрос статистики", details={"тип": "общая статистика"})
        
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
            
            # Считаем общее количество ответов для этого вопроса
            total_answers = sum(count for _, count in options_data)
            
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
                percentage = (count / total_answers * 100) if total_answers > 0 else 0
                statistics += f"└ {option}: {count} ({percentage:.1f}%)\n"
                
                # Если у основного варианта есть вложенные, выводим их
                if option in sub_options:
                    for sub_option, sub_count in sub_options[option]:
                        sub_percentage = (sub_count / total_answers * 100) if total_answers > 0 else 0
                        statistics += f"   └ {sub_option}: {sub_count} ({sub_percentage:.1f}%)\n"
            
            # Добавляем пустую строку между вопросами
            statistics += "\n"
        
        # Проверяем длину статистики и разбиваем на части при необходимости
        if len(statistics) > 4000:
            logger.warning(f"Статистика слишком длинная, необходимо разбиение (длинная_статистика)", 
                         details={"длина": len(statistics), "user_id": user_id})
            
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
            start_time = time.time()
            logger.data_processing("статистика", "Обновление статистики", details={"этап": "начало"})
            
            # Используем ограничитель запросов для обновления статистики
            await sheets_cache.execute_with_rate_limit(self.sheets.update_statistics)
            
            duration = time.time() - start_time
            logger.data_processing("статистика", "Обновление статистики", details={"этап": "завершено", "длительность": f"{duration:.2f} сек"})
        except Exception as e:
            try:
                duration = time.time() - start_time
            except:
                duration = 0
            logger.warning(f"Ошибка обновления статистики (stat_update_failed)", 
                         exception=e, details={"длительность": f"{duration:.2f} сек"}) 