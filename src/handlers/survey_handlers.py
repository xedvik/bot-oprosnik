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
        """Отправка вопроса пользователю"""
        # Получаем номер текущего вопроса
        current_question_num = len(context.user_data['answers'])
        
        # Проверяем, что не вышли за пределы списка вопросов
        if current_question_num >= len(self.questions):
            # Все вопросы заданы, показываем подтверждение
            return await self.show_confirmation(update, context)
        
        # Получаем текущий вопрос
        question = self.questions[current_question_num]
        options = self.questions_with_options[question]
        
        # Создаем клавиатуру с вариантами ответов, если они есть
        if options:
            keyboard = [[KeyboardButton(opt)] for opt in options]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        else:
            # Если вариантов нет, используем обычный ввод
            reply_markup = ReplyKeyboardRemove()
        
        # Отправляем вопрос
        await update.message.reply_text(
            f"Вопрос {current_question_num + 1}/{len(self.questions)}:\n\n{question}",
            reply_markup=reply_markup
        )
        
        # Возвращаем состояние для текущего вопроса
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
        
        # Проверяем, есть ли варианты ответов и соответствует ли ответ одному из них
        if available_options and answer not in available_options:
            logger.warning(f"[{user_id}] Получен недопустимый ответ: {answer}")
            # Формируем клавиатуру с доступными вариантами
            keyboard = [[KeyboardButton(opt)] for opt in available_options]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                "❌ Пожалуйста, выберите один из предложенных вариантов ответа:",
                reply_markup=reply_markup
            )
            return f"QUESTION_{current_question_num}"
        
        # Сохраняем ответ
        context.user_data['answers'].append(answer)
        logger.info(f"Сохранен ответ: {answer}")
        
        # Отправляем следующий вопрос
        return await self.send_question(update, context)
    
    async def show_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ подтверждения ответов"""
        # Формируем текст с ответами
        answers_text = "Ваши ответы:\n\n"
        for i, (question, answer) in enumerate(zip(self.questions, context.user_data['answers'])):
            answers_text += f"{i+1}. {question}\n➡️ {answer}\n\n"
        
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
        statistics = f"📊 Статистика опроса\n👥 Всего пройдено: {total_surveys}\n\n"
        
        # Группируем статистику по вопросам
        current_question = None
        for question, option, count in self.sheets.get_statistics():
            if question != current_question:
                if current_question:  # Добавляем пустую строку между вопросами
                    statistics += "\n"
                statistics += f"*{question}*\n"  # Выделяем вопрос жирным
                current_question = question
            statistics += f"└ {option}: {count}\n"
        
        # Проверяем, есть ли статистика
        if statistics == f"📊 Статистика опроса\n👥 Всего пройдено: {total_surveys}\n\n":
            statistics = "📊 Статистика недоступна. Нет вопросов с вариантами ответов или еще не получено ответов."
        
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