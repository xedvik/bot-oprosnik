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
    ADMINS_SHEET, SHEET_NAMES, SHEET_HEADERS,
    DEFAULT_MESSAGES, MESSAGE_TYPES
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
            
            # Инициализируем лист сообщений
            self.initialize_messages_sheet()
            
            # Инициализируем лист постов
            self.initialize_posts_sheet()
            
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
    
    def get_admins_info(self) -> list:
        """Получает полную информацию об администраторах (ID, имя, описание)"""
        try:
            logger.info("Получение информации об администраторах")
            
            # Получаем данные из листа администраторов
            admins_sheet = self.sheet.worksheet(ADMINS_SHEET)
            data = admins_sheet.get_all_values()
            
            # Если есть данные, пропускаем заголовки
            if data and len(data) > 1:
                data = data[1:]
            else:
                return []
                
            # Формируем список администраторов с полной информацией
            admins_info = []
            for row in data:
                if len(row) >= 3 and row[0]:  # ID, имя, описание
                    admins_info.append(row)
            
            logger.info(f"Получена информация о {len(admins_info)} администраторах")
            return admins_info
            
        except Exception as e:
            logger.error(f"Ошибка при получении информации об администраторах: {e}")
            return []

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

    def get_users_list(self, page: int = 1, page_size: int = 10) -> tuple:
        """Получение списка пользователей с пагинацией
        
        Args:
            page (int): Номер страницы (начиная с 1)
            page_size (int): Количество пользователей на странице
            
        Returns:
            tuple: (список пользователей, общее количество пользователей, количество страниц)
        """
        try:
            # Получаем данные листа пользователей
            values = self.get_sheet_values('users')
            if not values or len(values) <= 1:  # Только заголовки или нет данных
                return [], 0, 0
                
            # Пропускаем заголовок
            user_rows = values[1:]
            total_users = len(user_rows)
            total_pages = (total_users + page_size - 1) // page_size  # Округление вверх
            
            # Проверяем корректность номера страницы
            if page < 1:
                page = 1
            elif page > total_pages and total_pages > 0:
                page = total_pages
                
            # Вычисляем индексы для среза
            start_idx = (page - 1) * page_size
            end_idx = min(start_idx + page_size, total_users)
            
            # Получаем данные пользователей для текущей страницы
            # [ID, Telegram ID, Username, Дата регистрации]
            users = []
            for i in range(start_idx, end_idx):
                row = user_rows[i]
                user_id = row[0] if len(row) > 0 else 'Н/Д'
                telegram_id = row[1] if len(row) > 1 else 'Н/Д'
                username = row[2] if len(row) > 2 else 'Н/Д'
                reg_date = row[3] if len(row) > 3 else 'Н/Д'
                users.append((user_id, telegram_id, username, reg_date))
                
            return users, total_users, total_pages
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            return [], 0, 0

    def initialize_messages_sheet(self) -> bool:
        """Инициализация листа сообщений"""
        try:
            logger.info("Инициализация листа сообщений")
            
            # Проверяем существование листа
            try:
                messages_sheet = self.sheet.worksheet(SHEET_NAMES['messages'])
            except gspread.exceptions.WorksheetNotFound:
                logger.info("Создаем новый лист сообщений")
                messages_sheet = self.sheet.add_worksheet(
                    title=SHEET_NAMES['messages'],
                    rows=100,
                    cols=len(SHEET_HEADERS['messages'])
                )
                # Добавляем заголовки
                messages_sheet.update('A1:C1', [SHEET_HEADERS['messages']])
                
                # Добавляем сообщения по умолчанию
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                default_rows = [
                    ['start', DEFAULT_MESSAGES['start'], current_time],
                    ['finish', DEFAULT_MESSAGES['finish'], current_time]
                ]
                messages_sheet.update('A2:C3', default_rows)
                logger.info("Добавлены сообщения по умолчанию")
            
            return True
        except Exception as e:
            logger.error(f"Ошибка при инициализации листа сообщений: {e}")
            return False

    def get_message(self, message_type: str) -> str:
        """Получение текста сообщения по его типу"""
        try:
            messages_sheet = self.sheet.worksheet(SHEET_NAMES['messages'])
            all_messages = messages_sheet.get_all_values()
            
            # Пропускаем заголовок
            if len(all_messages) > 1:
                for row in all_messages[1:]:
                    if row[0] == message_type:
                        return row[1]
            
            # Если сообщение не найдено, возвращаем значение по умолчанию
            return DEFAULT_MESSAGES.get(message_type, '')
            
        except Exception as e:
            logger.error(f"Ошибка при получении сообщения типа {message_type}: {e}")
            return DEFAULT_MESSAGES.get(message_type, '')

    def update_message(self, message_type: str, new_text: str) -> bool:
        """Обновление текста сообщения"""
        try:
            if message_type not in MESSAGE_TYPES:
                logger.error(f"Неизвестный тип сообщения: {message_type}")
                return False
                
            messages_sheet = self.sheet.worksheet(SHEET_NAMES['messages'])
            all_messages = messages_sheet.get_all_values()
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message_row = None
            
            # Ищем строку с нужным типом сообщения
            for i, row in enumerate(all_messages):
                if row[0] == message_type:
                    message_row = i + 1  # +1 так как индексация с 1
                    break
            
            if message_row:
                # Обновляем существующую строку
                messages_sheet.update(f'B{message_row}:C{message_row}', [[new_text, current_time]])
            else:
                # Добавляем новую строку
                messages_sheet.append_row([message_type, new_text, current_time])
            
            logger.info(f"Сообщение типа {message_type} успешно обновлено")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении сообщения типа {message_type}: {e}")
            return False

    def initialize_posts_sheet(self) -> bool:
        """Инициализация листа постов"""
        try:
            logger.info("Инициализация листа постов")
            
            # Проверяем, существует ли уже лист с постами
            try:
                posts_sheet = self.sheet.worksheet(SHEET_NAMES['posts'])
                logger.info("Лист постов уже существует")
                
                # Проверяем и обновляем заголовки для существующего листа
                current_headers = posts_sheet.row_values(1)
                if current_headers and len(current_headers) < len(SHEET_HEADERS['posts']):
                    logger.info("Обновляем структуру таблицы постов")
                    posts_sheet.update('A1:H1', [SHEET_HEADERS['posts']])
                    logger.info("Структура таблицы постов обновлена")
                    
                    # Мигрируем существующие данные
                    self.migrate_posts_data()
                
            except gspread.exceptions.WorksheetNotFound:
                # Создаем новый лист для постов
                posts_sheet = self.sheet.add_worksheet(
                    title=SHEET_NAMES['posts'],
                    rows=1000,
                    cols=10
                )
                logger.info("Создан новый лист для постов")
                
                # Добавляем заголовки
                posts_sheet.append_row(SHEET_HEADERS['posts'])
                logger.info("Добавлены заголовки в лист постов")
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации листа постов: {e}")
            return False

    def migrate_posts_data(self):
        """Миграция данных в таблице постов для добавления столбца 'Название'"""
        try:
            logger.info("Начинаем миграцию данных постов")
            
            # Получаем лист с постами
            posts_sheet = self.sheet.worksheet(SHEET_NAMES['posts'])
            
            # Получаем все данные (пропускаем заголовок)
            data = posts_sheet.get_all_values()
            if len(data) <= 1:  # Только заголовок или пусто
                logger.info("Нет данных для миграции")
                return True
            
            # Пропускаем заголовок
            rows = data[1:]
            
            # Обрабатываем каждую строку
            for i, row in enumerate(rows, start=2):  # начинаем с индекса 2 (после заголовка)
                if len(row) < 7:  # Пропускаем некорректные строки
                    continue
                
                post_id = row[0]
                old_text = row[1]  # Старый текст в столбце B
                
                # Формируем название (первые 30 символов текста или ID поста)
                title = f"Пост №{post_id}"
                if old_text:
                    title_from_text = old_text[:30].strip()
                    if title_from_text:
                        title = title_from_text + ("..." if len(old_text) > 30 else "")
                
                # Вставляем новую ячейку с названием (столбец B)
                posts_sheet.update_cell(i, 2, title)
                
                # Если нужно, смещаем остальные данные
                # Для этого получаем оставшиеся данные и обновляем их
                remaining_data = row[1:]  # Текст, Изображение, Кнопка (текст), Кнопка (ссылка), Дата создания, Создал
                if remaining_data:
                    # Обновляем ячейки C-H
                    cell_range = f"C{i}:H{i}" if len(remaining_data) >= 6 else f"C{i}:{chr(66+len(remaining_data)+1)}{i}"
                    posts_sheet.update(cell_range, [remaining_data])
            
            logger.info("Миграция данных постов завершена успешно")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при миграции данных постов: {e}")
            return False
    
    def save_post(self, title: str, text: str, image_url: str, button_text: str, button_url: str, admin_id: int) -> int:
        """Сохранение поста в таблицу"""
        try:
            logger.info(f"Сохранение поста от администратора {admin_id}")
            
            # Открываем лист с постами
            posts_sheet = self.sheet.worksheet(SHEET_NAMES['posts'])
            
            # Получаем текущую дату и время
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Генерируем уникальный ID для поста
            post_id = str(int(datetime.now().timestamp()))
            
            # Подготавливаем данные для добавления
            row_data = [post_id, title, text, image_url, button_text, button_url, current_time, str(admin_id)]
            
            # Добавляем пост
            posts_sheet.append_row(row_data)
            
            logger.info(f"Пост с ID {post_id} успешно сохранен")
            return post_id
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении поста: {e}")
            return 0
    
    def get_all_posts(self) -> list:
        """Получение всех постов из таблицы"""
        try:
            logger.info("Получение всех постов")
            posts_sheet = self.sheet.worksheet(SHEET_NAMES['posts'])
            
            # Получаем все данные из таблицы
            data = posts_sheet.get_all_values()
            
            # Пропускаем заголовок
            if data and len(data) > 0:
                data = data[1:]
            
            # Преобразуем данные в список словарей
            posts = []
            for row in data:
                if len(row) >= 8:  # Новый формат с названием
                    post = {
                        'id': row[0],
                        'title': row[1],
                        'text': row[2],
                        'image_url': row[3],
                        'button_text': row[4],
                        'button_url': row[5],
                        'created_at': row[6],
                        'admin_id': row[7]
                    }
                elif len(row) >= 7:  # Старый формат без названия, но с кнопками
                    post = {
                        'id': row[0],
                        'title': 'Пост №' + row[0],  # Генерируем название для старых постов
                        'text': row[1],
                        'image_url': row[2],
                        'button_text': row[3],
                        'button_url': row[4],
                        'created_at': row[5],
                        'admin_id': row[6]
                    }
                else:
                    # Обрабатываем самые старые посты без кнопок
                    post = {
                        'id': row[0],
                        'title': 'Пост №' + row[0],  # Генерируем название
                        'text': row[1],
                        'image_url': row[2],
                        'button_text': '',
                        'button_url': '',
                        'created_at': row[3] if len(row) > 3 else '',
                        'admin_id': row[4] if len(row) > 4 else ''
                    }
                posts.append(post)
            
            logger.info(f"Получено {len(posts)} постов")
            return posts
            
        except Exception as e:
            logger.error(f"Ошибка при получении постов: {e}")
            return []
    
    def get_post_by_id(self, post_id: str) -> dict:
        """Получение поста по ID"""
        try:
            logger.info(f"Получение поста с ID {post_id}")
            posts_sheet = self.sheet.worksheet(SHEET_NAMES['posts'])
            
            # Находим пост по ID
            cell = posts_sheet.find(post_id)
            if not cell:
                logger.error(f"Пост с ID {post_id} не найден")
                return {}
            
            # Получаем всю строку
            row_data = posts_sheet.row_values(cell.row)
            
            # Преобразуем данные в словарь
            if len(row_data) >= 8:  # Новый формат с названием
                post = {
                    'id': row_data[0],
                    'title': row_data[1],
                    'text': row_data[2],
                    'image_url': row_data[3],
                    'button_text': row_data[4],
                    'button_url': row_data[5],
                    'created_at': row_data[6],
                    'admin_id': row_data[7]
                }
            elif len(row_data) >= 7:  # Старый формат без названия, но с кнопками
                post = {
                    'id': row_data[0],
                    'title': 'Пост №' + row_data[0],  # Генерируем название для старых постов
                    'text': row_data[1],
                    'image_url': row_data[2],
                    'button_text': row_data[3],
                    'button_url': row_data[4],
                    'created_at': row_data[5],
                    'admin_id': row_data[6]
                }
            else:
                # Обрабатываем самые старые посты без кнопок
                post = {
                    'id': row_data[0],
                    'title': 'Пост №' + row_data[0],  # Генерируем название
                    'text': row_data[1],
                    'image_url': row_data[2],
                    'button_text': '',
                    'button_url': '',
                    'created_at': row_data[3] if len(row_data) > 3 else '',
                    'admin_id': row_data[4] if len(row_data) > 4 else ''
                }
            
            logger.info(f"Пост с ID {post_id} успешно получен")
            return post
            
        except Exception as e:
            logger.error(f"Ошибка при получении поста по ID: {e}")
            return {}
    
    def update_post(self, post_id, text=None, image_url=None, button_text=None, button_url=None):
        """Обновляет существующий пост по ID"""
        logger.info(f"Обновление поста с ID {post_id}")
        logger.info(f"Параметры обновления: text={text}, image_url={image_url}, button_text={button_text}, button_url={button_url}")
        
        try:
            # Получаем все посты
            posts_sheet = self.sheet.worksheet(SHEET_NAMES['posts'])
            rows = posts_sheet.get_all_values()
            
            # Ищем пост по ID
            row_index = None
            for idx, row in enumerate(rows[1:], 2):  # Начинаем с 2, так как первая строка - заголовки
                if len(row) >= 1 and row[0] == str(post_id):
                    row_index = idx
                    logger.info(f"Найден пост с ID {post_id} в строке {row_index}")
                    break
            
            if row_index is None:
                logger.warning(f"Пост с ID {post_id} не найден для обновления")
                return False
            
            # Обновляем только те поля, которые переданы
            if text is not None:
                logger.info(f"Обновление текста поста {post_id}: {text[:30]}...")
                posts_sheet.update_cell(row_index, 2, text)
            
            if image_url is not None:
                logger.info(f"Обновление изображения поста {post_id}")
                posts_sheet.update_cell(row_index, 3, image_url)
            
            if button_text is not None:
                logger.info(f"Обновление текста кнопки поста {post_id}: {button_text}")
                posts_sheet.update_cell(row_index, 4, button_text)
            
            if button_url is not None:
                logger.info(f"Обновление URL кнопки поста {post_id}: {button_url}")
                posts_sheet.update_cell(row_index, 5, button_url)
            
            logger.info(f"Пост с ID {post_id} успешно обновлен")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении поста {post_id}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def delete_post(self, post_id):
        """Удаляет пост по его ID"""
        logger.info(f"Удаление поста с ID {post_id}")
        
        try:
            # Получаем все посты
            posts_sheet = self.sheet.worksheet(SHEET_NAMES['posts'])
            rows = posts_sheet.get_all_values()
            
            # Ищем пост по ID
            row_index = None
            for idx, row in enumerate(rows[1:], 2):  # Начинаем с 2, так как первая строка - заголовки
                if len(row) >= 1 and row[0] == str(post_id):
                    row_index = idx
                    break
            
            if row_index is None:
                logger.warning(f"Пост с ID {post_id} не найден для удаления")
                return False
            
            # Удаляем строку
            posts_sheet.delete_rows(row_index)
            
            logger.info(f"Пост с ID {post_id} успешно удален")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при удалении поста: {e}")
            return False 