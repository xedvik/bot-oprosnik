"""
Модуль для работы с Google Sheets
"""

import logging
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os

from config import (
    GOOGLE_CREDENTIALS_FILE, SPREADSHEET_ID,
    QUESTIONS_SHEET, ANSWERS_SHEET, STATS_SHEET,
    ADMINS_SHEET, SHEET_NAMES, SHEET_HEADERS
)

# Настройка логирования
logger = logging.getLogger(__name__)

class GoogleSheets:
    """Класс для работы с Google Sheets"""
    
    def __init__(self):
        """Инициализация подключения к Google Sheets"""
        try:
            logger.info("Инициализация подключения к Google Sheets")
            
            # Определяем необходимые разрешения
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Создаем учетные данные из файла
            credentials = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_FILE, scopes=scopes
            )
            
            # Авторизуемся в Google Sheets с использованием нового API
            self.client = gspread.Client(auth=credentials)
            
            # Открываем таблицу
            self.sheet = self.client.open_by_key(SPREADSHEET_ID)
            
            logger.info("Подключение к Google Sheets успешно установлено")
            
            # Инициализируем все необходимые листы при старте
            self.initialize_sheets()
            
        except Exception as e:
            logger.error(f"Ошибка при подключении к Google Sheets: {e}")
            raise
    
    def initialize_sheets(self):
        """Инициализация всех необходимых листов"""
        try:
            logger.info("Инициализация листов таблицы")
            
            # Инициализируем лист пользователей
            self.initialize_users_sheet()
            
            # Здесь можно добавить инициализацию других листов при необходимости
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации листов: {e}")
            raise
    
    def get_questions_with_options(self) -> dict:
        """Получение вопросов с вариантами ответов из таблицы"""
        try:
            logger.info("Получение вопросов с вариантами ответов")
            questions_sheet = self.sheet.worksheet(QUESTIONS_SHEET)
            
            # Получаем все данные из таблицы
            data = questions_sheet.get_all_values()
            
            # Пропускаем заголовок
            if data and len(data) > 0:
                data = data[1:]
            
            # Формируем словарь вопросов с вариантами ответов
            questions_with_options = {}
            for row in data:
                if not row or not row[0]:  # Пропускаем пустые строки
                    continue
                    
                question = row[0]
                # Получаем варианты ответов, пропуская пустые
                options = [opt for opt in row[1:] if opt]
                questions_with_options[question] = options
            
            logger.info(f"Получено {len(questions_with_options)} вопросов")
            return questions_with_options
            
        except Exception as e:
            logger.error(f"Ошибка при получении вопросов: {e}")
            return {}
    
    def save_answers(self, answers: list, user_id: int) -> bool:
        """Сохранение ответов пользователя в таблицу"""
        try:
            logger.info(f"[{user_id}] Начало сохранения ответов")
            start_time = datetime.now()
            
            # Получаем список вопросов
            questions = list(self.get_questions_with_options().keys())
            
            # Проверяем, что количество ответов соответствует количеству вопросов
            if len(answers) != len(questions):
                logger.error(f"[{user_id}] Количество ответов ({len(answers)}) не соответствует количеству вопросов ({len(questions)})")
                return False
            
            # Получаем текущую дату и время
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Сохраняем ответы в таблицу ответов
            answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
            
            # Подготавливаем данные для добавления
            row_data = [current_time, str(user_id)] + answers
            
            logger.info(f"[{user_id}] Отправка данных в таблицу...")
            # Добавляем ответы
            answers_sheet.append_row(row_data)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"[{user_id}] Ответы успешно сохранены за {duration:.2f} секунд")
            return True
            
        except Exception as e:
            logger.error(f"[{user_id}] Ошибка при сохранении ответов: {e}")
            return False
    
    def update_statistics_sheet(self) -> bool:
        """Полное обновление листа статистики на основе всех ответов"""
        try:
            logger.info("Обновление листа статистики")
            
            # Получаем вопросы с вариантами ответов
            questions_with_options = self.get_questions_with_options()
            
            # Получаем данные из листа ответов
            answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
            answers_data = answers_sheet.get_all_values()
            
            if len(answers_data) <= 1:  # Только заголовок или пусто
                logger.info("Нет данных для обновления статистики")
                stats_sheet = self.sheet.worksheet(STATS_SHEET)
                stats_sheet.clear()
                stats_sheet.append_row(["Статистика опроса"])
                stats_sheet.append_row(["Всего пройдено опросов:", "0"])
                return True
            
            # Инициализируем словарь для статистики
            stats = {}
            
            # Получаем список вопросов
            questions = list(questions_with_options.keys())
            
            # Инициализируем статистику для каждого вопроса с вариантами
            for question, options in questions_with_options.items():
                if options:  # Только для вопросов с вариантами ответов
                    stats[question] = {option: 0 for option in options}
            
            # Обрабатываем ответы (пропускаем заголовок)
            for row in answers_data[1:]:
                # Пропускаем дату и ID пользователя
                for i, answer in enumerate(row[2:]):
                    if i < len(questions):
                        question = questions[i]
                        # Учитываем только вопросы с вариантами ответов
                        if question in stats and answer in stats[question]:
                            stats[question][answer] += 1
            
            # Обновляем лист статистики
            stats_sheet = self.sheet.worksheet(STATS_SHEET)
            
            # Очищаем текущие данные
            stats_sheet.clear()
            
            # Добавляем заголовок
            stats_sheet.append_row(["Статистика опроса"])
            
            # Для каждого вопроса с вариантами добавляем строки с вариантами и процентами
            for question, answers_count in stats.items():
                # Добавляем строку с вопросом
                stats_sheet.append_row([question])
                
                # Получаем общее количество ответов на этот вопрос
                total_answers = sum(answers_count.values())
                
                # Для каждого варианта ответа показываем статистику
                for option, count in answers_count.items():
                    percentage = (count / total_answers * 100) if total_answers > 0 else 0
                    stats_sheet.append_row([option, f"{percentage:.1f}%", str(count)])
            
            # Добавляем общее количество опросов
            total_surveys = len(answers_data) - 1  # -1 для заголовка
            stats_sheet.append_row(["Всего пройдено опросов:", str(total_surveys)])
            
            logger.info("Лист статистики успешно обновлен")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении листа статистики: {e}")
            return False
    
    def update_statistics(self, question_index: int, answer: str) -> bool:
        """Обновление статистики для вопроса"""
        try:
            logger.info(f"Обновление статистики для вопроса {question_index}, ответ: {answer}")
            
            # Получаем текущую статистику из ответов
            stats_data = self.get_statistics()
            
            # Обновляем лист статистики полностью
            stats_sheet = self.sheet.worksheet(STATS_SHEET)
            
            # Очищаем текущие данные
            stats_sheet.clear()
            
            # Добавляем заголовок
            stats_sheet.append_row(["Статистика опроса"])
            
            # Получаем вопросы и варианты ответов
            questions_with_options = self.get_questions_with_options()
            
            # Для каждого вопроса добавляем строки с вариантами и процентами
            for question, options in questions_with_options.items():
                # Добавляем строку с вопросом
                stats_sheet.append_row([question])
                
                # Если у вопроса есть варианты ответов
                if options:
                    # Получаем статистику для этого вопроса
                    question_stats = stats_data.get(question, {})
                    total_answers = sum(question_stats.values()) if question_stats else 0
                    
                    # Для каждого варианта ответа показываем статистику
                    for option in options:
                        count = question_stats.get(option, 0)
                        percentage = (count / total_answers * 100) if total_answers > 0 else 0
                        stats_sheet.append_row([option, f"{percentage:.1f}%", str(count)])
            
            # Добавляем общее количество опросов
            answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
            answers_data = answers_sheet.get_all_values()
            total_surveys = max(0, len(answers_data) - 1)  # -1 для заголовка
            stats_sheet.append_row(["Всего пройдено опросов:", str(total_surveys)])
            
            logger.info("Лист статистики успешно обновлен с процентами")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении листа статистики: {e}")
            return False

    def update_stats_sheet_with_percentages(self):
        """Обновление листа статистики с процентами для всех вариантов ответов"""
        try:
            logger.info("Обновление листа статистики с процентами")
            
            # Получаем данные для статистики
            answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
            answers_data = answers_sheet.get_all_values()
            
            # Пропускаем заголовок
            if len(answers_data) <= 1:
                logger.info("Нет данных для статистики")
                return True
            
            # Получаем вопросы с вариантами ответов
            questions_with_options = self.get_questions_with_options()
            questions = list(questions_with_options.keys())
            
            # Создаем словарь для подсчета ответов
            question_answers = {}
            question_totals = {}
            
            # Индексы столбцов с ответами (пропускаем дату/время и ID пользователя)
            answer_start_index = 2
            
            # Подсчитываем ответы
            for row in answers_data[1:]:  # Пропускаем заголовок
                for i, question in enumerate(questions):
                    if i + answer_start_index < len(row):
                        answer = row[i + answer_start_index]
                        
                        # Инициализируем счетчики, если нужно
                        if question not in question_answers:
                            question_answers[question] = {}
                            question_totals[question] = 0
                        
                        # Увеличиваем счетчик для этого ответа
                        if answer not in question_answers[question]:
                            question_answers[question][answer] = 0
                        question_answers[question][answer] += 1
                        question_totals[question] += 1
            
            # Обновляем лист статистики
            stats_sheet = self.sheet.worksheet(STATS_SHEET)
            
            # Очищаем текущие данные
            stats_sheet.clear()
            
            # Добавляем заголовок
            stats_sheet.append_row(["Статистика опроса"])
            
            # Добавляем статистику по каждому вопросу
            for question, total in question_totals.items():
                # Добавляем строку с вопросом
                stats_sheet.append_row([question])
                
                # Получаем все возможные варианты ответов для этого вопроса
                all_options = questions_with_options.get(question, [])
                
                # Для каждого варианта ответа показываем статистику
                for option in all_options:
                    count = question_answers[question].get(option, 0)
                    percentage = (count / total * 100) if total > 0 else 0
                    stats_sheet.append_row([option, f"{percentage:.1f}%", str(count)])
            
            # Добавляем общее количество опросов
            total_surveys = len(answers_data) - 1
            stats_sheet.append_row(["Всего пройдено опросов:", str(total_surveys)])
            
            logger.info("Лист статистики успешно обновлен с процентами")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении листа статистики с процентами: {e}")
            return False
    
    def get_statistics_from_sheet(self) -> str:
        """Получение статистики из листа статистики"""
        try:
            logger.info("Получение статистики из листа")
            
            # Получаем данные из листа статистики
            stats_sheet = self.sheet.worksheet(STATS_SHEET)
            stats_data = stats_sheet.get_all_values()
            
            if len(stats_data) <= 1:  # Только заголовок или пусто
                return "📊 Статистика опроса:\n\n"
            
            # Формируем текст со статистикой
            stats_text = "📊 Статистика опроса:\n\n"
            
            current_question = None
            
            for row in stats_data[1:]:  # Пропускаем заголовок
                if len(row) == 0:
                    continue
                    
                if len(row) == 1 or (len(row) > 1 and not row[1]):
                    # Это строка с вопросом
                    current_question = row[0]
                    stats_text += f"❓ {current_question}\n"
                elif row[0] == "Всего пройдено опросов:":
                    # Это строка с общим количеством опросов
                    stats_text += f"\n📋 {row[0]} {row[1]}\n"
                elif current_question and len(row) >= 3:
                    # Это строка с вариантом ответа и статистикой
                    option = row[0]
                    percentage = row[1]
                    count = row[2]
                    stats_text += f"{option}: {percentage} ({count})\n"
            
            return stats_text
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return "❌ Ошибка при получении статистики"
    
    def get_admins(self) -> list:
        """Получение списка ID админов из таблицы"""
        try:
            logger.info("Получение списка админов из таблицы")
            
            # Проверяем существование листа с админами
            try:
                admins_sheet = self.sheet.worksheet(ADMINS_SHEET)
            except gspread.exceptions.WorksheetNotFound:
                logger.warning(f"Лист '{ADMINS_SHEET}' не найден. Создаем новый.")
                # Создаем лист с админами, если его нет
                admins_sheet = self.sheet.add_worksheet(title=ADMINS_SHEET, rows=100, cols=2)
                # Добавляем заголовок
                admins_sheet.update('A1:B1', [['ID', 'Имя']])
            
            # Получаем все данные из таблицы
            data = admins_sheet.get_all_values()
            
            # Пропускаем заголовок
            if data and len(data) > 0:
                data = data[1:]
            
            # Извлекаем ID админов
            admin_ids = []
            for row in data:
                if row and row[0]:  # Проверяем, что строка не пустая и есть ID
                    try:
                        admin_id = int(row[0])
                        admin_ids.append(admin_id)
                    except ValueError:
                        logger.warning(f"Некорректный ID админа: {row[0]}")
            
            # Добавляем админов из переменной окружения
            env_admins = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
            for admin_id in env_admins:
                if admin_id not in admin_ids:
                    admin_ids.append(admin_id)
            
            logger.info(f"Получено {len(admin_ids)} админов: {admin_ids}")
            return admin_ids
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка админов: {e}")
            # Возвращаем админов из переменной окружения в случае ошибки
            env_admins = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
            logger.info(f"Используем админов из переменной окружения: {env_admins}")
            return env_admins

    def get_statistics(self) -> list:
        """Получение статистики ответов для вопросов с вариантами"""
        try:
            logger.info("Получение статистики ответов")
            
            # Получаем вопросы с вариантами ответов
            questions_with_options = self.get_questions_with_options()
            
            # Получаем все ответы
            answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
            all_values = answers_sheet.get_all_values()
            
            if len(all_values) < 2:  # Если есть только заголовки или лист пустой
                return []
            
            headers = all_values[0]
            answers = all_values[1:]
            
            statistics = []
            
            # Для каждого вопроса с вариантами
            for question, options in questions_with_options.items():
                if not options:  # Пропускаем вопросы без вариантов
                    continue
                    
                # Находим индекс колонки для текущего вопроса
                try:
                    question_index = headers.index(question)
                except ValueError:
                    continue
                    
                # Подсчитываем количество каждого варианта ответа
                option_counts = {}
                total_answers = 0
                
                for row in answers:
                    if question_index < len(row):
                        answer = row[question_index]
                        if answer:  # Учитываем только непустые ответы
                            option_counts[answer] = option_counts.get(answer, 0) + 1
                            total_answers += 1
                
                # Формируем статистику с процентами
                for option in options:
                    count = option_counts.get(option, 0)
                    percentage = round((count / total_answers * 100) if total_answers > 0 else 0)
                    statistics.append([question, option, f"{count} ({percentage}%)"])
            
            logger.info(f"Получено {len(statistics)} строк статистики")
            return statistics
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            logger.exception(e)
            return []

    def get_sheet_values(self, sheet_name: str) -> list:
        """Получение всех значений с листа"""
        try:
            worksheet = self.sheet.worksheet(SHEET_NAMES[sheet_name])
            return worksheet.get_all_values()
        except Exception as e:
            logger.error(f"Ошибка при получении данных с листа {sheet_name}: {e}")
            return []

    def get_next_user_id(self) -> int:
        """Получение следующего доступного ID пользователя"""
        try:
            values = self.get_sheet_values('users')
            if not values or len(values) == 1:  # Только заголовки
                return 1
            return max(int(row[0]) for row in values[1:]) + 1
        except Exception as e:
            logger.error(f"Ошибка при получении следующего ID пользователя: {e}")
            return 1

    def initialize_users_sheet(self) -> bool:
        """Инициализация листа пользователей"""
        try:
            logger.info("Инициализация листа пользователей")
            
            # Проверяем существование листа
            try:
                users_sheet = self.sheet.worksheet(SHEET_NAMES['users'])
            except gspread.exceptions.WorksheetNotFound:
                logger.info("Создаем новый лист пользователей")
                users_sheet = self.sheet.add_worksheet(
                    title=SHEET_NAMES['users'],
                    rows=1000,
                    cols=len(SHEET_HEADERS['users'])
                )
                # Добавляем заголовки
                users_sheet.update('A1:D1', [SHEET_HEADERS['users']])
                logger.info("Заголовки листа пользователей установлены")
                return True
            
            # Проверяем и обновляем заголовки
            current_headers = users_sheet.row_values(1)
            if not current_headers or current_headers != SHEET_HEADERS['users']:
                logger.info("Обновляем заголовки листа пользователей")
                users_sheet.update('A1:D1', [SHEET_HEADERS['users']])
                logger.info("Заголовки листа пользователей обновлены")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при инициализации листа пользователей: {e}")
            return False

    def add_user(self, telegram_id: int, username: str) -> bool:
        """Добавление нового пользователя"""
        try:
            # Получаем лист пользователей
            users_sheet = self.sheet.worksheet(SHEET_NAMES['users'])
            
            # Получаем следующий ID
            user_id = self.get_next_user_id()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Добавляем пользователя
            users_sheet.append_row([
                str(user_id),
                str(telegram_id),
                username,
                current_time
            ])
            
            logger.info(f"Добавлен новый пользователь: ID={user_id}, Telegram ID={telegram_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при добавлении пользователя: {e}")
            return False

    def is_user_exists(self, telegram_id: int) -> bool:
        """Проверка существования пользователя"""
        try:
            values = self.get_sheet_values('users')
            if not values or len(values) == 1:  # Только заголовки
                return False
            return any(str(telegram_id) == row[1] for row in values[1:])
        except Exception as e:
            logger.error(f"Ошибка при проверке существования пользователя: {e}")
            return False 