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

# Настройка логирования
logger = logging.getLogger(__name__)

class SurveyHandler(BaseHandler):
    """Обработчики для проведения опроса"""
    
    async def begin_survey(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало опроса"""
        user_id = update.effective_user.id
        logger.info(f"Пользователь {user_id} пытается пройти анкету")
        
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
        """Отправка текущего вопроса пользователю"""
        # Проверяем наличие ключа 'answers'
        if 'answers' not in context.user_data:
            context.user_data['answers'] = []
        
        current_question_num = len(context.user_data['answers'])
        
        # Проверка, что есть еще вопросы
        if current_question_num >= len(self.questions):
            return await self.show_confirmation(update, context)
        
        current_question = self.questions[current_question_num]
        options = self.questions_with_options[current_question]
        
        # Проверка для вложенных вариантов
        if 'current_parent_answer' in context.user_data:
            parent_answer = context.user_data['current_parent_answer']
            parent_option = None
            
            # Найдем родительский вариант
            for opt in options:
                if isinstance(opt, dict) and opt.get("text") == parent_answer:
                    parent_option = opt
                    break
            
            if parent_option:
                sub_options = parent_option.get("sub_options", [])
                
                # Проверка на свободный ответ (пустой список подвариантов)
                if not sub_options:
                    # Это свободный вложенный ответ
                    await update.message.reply_text(
                        f"Введите ваш ответ для варианта '{parent_answer}':\n\n"
                        "Или нажмите кнопку для возврата к основным вариантам:",
                        reply_markup=ReplyKeyboardMarkup([
                            [KeyboardButton("◀️ Назад к основным вариантам")]
                        ], resize_keyboard=True)
                    )
                    return f"QUESTION_{current_question_num}_SUB"
                
                # Создаем кнопки с вложенными вариантами ответов
                keyboard = [[KeyboardButton(sub_opt)] for sub_opt in sub_options]
                keyboard.append([KeyboardButton("◀️ Назад к основным вариантам")])
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                await update.message.reply_text(
                    f"Выберите вариант для '{parent_answer}':",
                    reply_markup=reply_markup
                )
                
                return f"QUESTION_{current_question_num}_SUB"
            else:
                # Если родительский вариант не найден, очищаем current_parent_answer и показываем обычный вопрос
                logger.warning(f"Родительский вариант '{parent_answer}' не найден, возвращаемся к обычному вопросу")
                context.user_data.pop('current_parent_answer', None)
        
        # Отправляем вопрос
        if options:
            # Создаем кнопки с вариантами ответов
            keyboard = []
            for opt in options:
                if isinstance(opt, dict) and "text" in opt:
                    keyboard.append([KeyboardButton(opt["text"])])
                else:
                    keyboard.append([KeyboardButton(str(opt))])
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                current_question,
                reply_markup=reply_markup
            )
        else:
            # Вопрос со свободным ответом
            await update.message.reply_text(
                current_question,
                reply_markup=ReplyKeyboardRemove()
            )
        
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
                # Проверяем, есть ли вложенные варианты
                sub_options = parent_option.get("sub_options", [])
                
                if answer == "◀️ Назад к основным вариантам":
                    # Возвращаемся к основным вариантам
                    context.user_data.pop('current_parent_answer', None)
                    return await self.send_question(update, context)
                
                # Если список подвариантов пуст - это свободный ответ для вложенного варианта
                if not sub_options:
                    # Сохраняем свободный ответ в формате "родительский - введенный"
                    full_answer = f"{parent_answer} - {answer}"
                    context.user_data['answers'].append(full_answer)
                    # Очищаем текущий родительский ответ
                    context.user_data.pop('current_parent_answer', None)
                    logger.info(f"[{user_id}] Сохранен свободный ответ для вложенного варианта: {full_answer}")
                    
                    # Переходим к следующему вопросу
                    return await self.send_question(update, context)
                
                # Проверяем, соответствует ли ответ одному из подвариантов
                if answer not in sub_options:
                    # Ответ не соответствует ни одному из подвариантов
                    keyboard = [[KeyboardButton(sub_opt)] for sub_opt in sub_options]
                    keyboard.append([KeyboardButton("◀️ Назад к основным вариантам")])
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
        
        # Обработка для вариантов без вложенных опций
        if available_options:
            # Проверяем, соответствует ли ответ одному из вариантов
            is_valid_option = False
            selected_option = None
            
            for opt in available_options:
                if isinstance(opt, dict) and "text" in opt and opt["text"] == answer:
                    is_valid_option = True
                    selected_option = opt
                    break
                elif not isinstance(opt, dict) and str(opt) == answer:
                    is_valid_option = True
                    break
            
            if not is_valid_option:
                # Ответ не соответствует ни одному из вариантов
                keyboard = []
                for opt in available_options:
                    if isinstance(opt, dict) and "text" in opt:
                        keyboard.append([KeyboardButton(opt["text"])])
                    else:
                        keyboard.append([KeyboardButton(str(opt))])
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                await update.message.reply_text(
                    "❌ Пожалуйста, выберите один из предложенных вариантов:",
                    reply_markup=reply_markup
                )
                return f"QUESTION_{current_question_num}"
            
            # Если у выбранного варианта есть вложенные опции или пустой список (свободный ответ)
            if selected_option and "sub_options" in selected_option:
                # Сохраняем родительский ответ для последующего использования
                context.user_data['current_parent_answer'] = answer
                logger.info(f"[{user_id}] Установлен родительский ответ: {answer}")
                
                # Переходим к подвариантам
                return await self.send_question(update, context)
            
            # Сохраняем обычный ответ
            context.user_data['answers'].append(answer)
            logger.info(f"[{user_id}] Сохранен ответ: {answer}")
        else:
            # Сохраняем свободный ответ
            context.user_data['answers'].append(answer)
            logger.info(f"[{user_id}] Сохранен свободный ответ: {answer}")
        
        # Переходим к следующему вопросу
        return await self.send_question(update, context)
    
    async def show_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ подтверждения ответов"""
        # Формируем текст с ответами
        answers_text = "Ваши ответы:\n\n"
        for i, (question, answer) in enumerate(zip(self.questions, context.user_data['answers'])):
            # Проверяем, является ли ответ составным (для вложенных вариантов)
            if " - " in answer:
                main_part, sub_part = answer.split(" - ", 1)
                formatted_answer = f"➡️ {main_part}\n   ↳ {sub_part}"
            else:
                formatted_answer = f"➡️ {answer}"
            
            answers_text += f"{i+1}. {question}\n{formatted_answer}\n\n"
        
        # Создаем клавиатуру для подтверждения
        keyboard = [
            [KeyboardButton("✅ Подтвердить")],
            [KeyboardButton("🔄 Начать заново")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # Отправляем сообщение с подтверждением
        await update.message.reply_text(
            f"{answers_text}\nПожалуйста, подтвердите ваши ответы или начните заново:",
            reply_markup=reply_markup
        )
        
        return CONFIRMING
    
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
        """Асинхронное обновление статистики"""
        try:
            start_time = datetime.now()
            logger.info("Начало асинхронного обновления статистики")
            
            self.sheets.update_statistics_sheet()
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Статистика успешно обновлена за {duration:.2f} секунд")
        except Exception as e:
            logger.error(f"Ошибка при обновлении статистики: {e}") 