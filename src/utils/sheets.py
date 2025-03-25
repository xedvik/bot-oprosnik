"""
Модуль для работы с Google Sheets
"""

from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import os
import time
import asyncio

# Избегаем циклического импорта, перенесем константы из config непосредственно сюда
# Для гибкости сохраним возможность переопределения этих значений при инициализации
from utils.questions_cache import QuestionsCache
from utils.sheets_cache import sheets_cache
from utils.logger import get_logger

# Получаем логгер для модуля
logger = get_logger()

class GoogleSheets:
    """Класс для работы с Google Sheets"""
    
    def __init__(self, 
                 google_credentials_file=None, 
                 spreadsheet_id=None,
                 sheet_names=None,
                 sheet_headers=None,
                 default_messages=None,
                 message_types=None):
        """Инициализация подключения к Google Sheets"""
        # Инициализируем логгер для экземпляра класса
        self.logger = logger
        self.logger.init("GoogleSheets", "Инициализация подключения")
        
        # Загружаем переменные окружения, если они не предоставлены
        if google_credentials_file is None:
            google_credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "/app/credentials.json")
        
        if spreadsheet_id is None:
            spreadsheet_id = os.getenv("SPREADSHEET_ID")
            
        # Загружаем конфигурацию названий листов, если она не предоставлена
        self._load_sheet_config(sheet_names, sheet_headers, default_messages, message_types)
        
        # Область видимости, необходимая для работы с Google Sheets
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Создаем клиент для работы с Google Sheets
        try:
            creds = Credentials.from_service_account_file(google_credentials_file, scopes=scope)
            self.sheet = gspread.authorize(creds).open_by_key(spreadsheet_id)
            self.logger.init("GoogleSheets", "Подключение установлено")
            
            # Инициализируем кэш вопросов
            self.questions_cache = QuestionsCache()
            
            # Инициализируем листы таблицы, если они не существуют
            self.initialize_sheets()
            
        except Exception as e:
            self.logger.error("подключение_к_sheets", e)
            raise e
    
    def _load_sheet_config(self, sheet_names=None, sheet_headers=None, default_messages=None, message_types=None):
        """Загружает конфигурацию листов и другие настройки из переменных окружения"""
        # Импортируем здесь, чтобы избежать циклической зависимости
        from config import (
            SHEET_NAMES, SHEET_HEADERS, DEFAULT_MESSAGES, MESSAGE_TYPES,
            QUESTIONS_SHEET, ANSWERS_SHEET, STATS_SHEET, ADMINS_SHEET
        )
        
        # Устанавливаем значения из config или из переданных параметров
        self.SHEET_NAMES = sheet_names or SHEET_NAMES
        self.SHEET_HEADERS = sheet_headers or SHEET_HEADERS
        self.DEFAULT_MESSAGES = default_messages or DEFAULT_MESSAGES
        self.MESSAGE_TYPES = message_types or MESSAGE_TYPES
        
        # Сохраняем основные названия листов для простого доступа
        self.QUESTIONS_SHEET = QUESTIONS_SHEET
        self.ANSWERS_SHEET = ANSWERS_SHEET
        self.STATS_SHEET = STATS_SHEET
        self.ADMINS_SHEET = ADMINS_SHEET
    
    def initialize_sheets(self):
        """Инициализация всех необходимых листов"""
        try:
            self.logger.init("sheets", "Инициализация листов таблицы")
            
            # Инициализируем лист пользователей
            self.initialize_users_sheet()
            
            # Инициализируем лист сообщений
            self.initialize_messages_sheet()
            
            # Инициализируем лист постов
            self.initialize_posts_sheet()
            
            # Здесь можно добавить инициализацию других листов при необходимости
            
        except Exception as e:
            self.logger.error("инициализация_листов", e)
            raise
    
    def get_questions_with_options(self) -> dict:
        """Получение вопросов с вариантами ответов из таблицы с кэшированием"""
        # Используем синглтон-кэш для получения вопросов
        return self.questions_cache.get_questions(self._fetch_questions_from_sheet)
            
    # Метод для принудительного обновления кэша
    def invalidate_questions_cache(self):
        """Сбрасывает кэш вопросов, чтобы при следующем вызове данные были загружены заново"""
        self.questions_cache.invalidate_cache()
        
    def _fetch_questions_from_sheet(self) -> dict:
        """Загружает вопросы с вариантами ответов из таблицы напрямую"""
        try:
            self.logger.data_load("вопросы", f"Google Sheets/{self.QUESTIONS_SHEET}")
            questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
            
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
                options = []
                for opt in row[1:]:
                    if not opt:  # Пропускаем пустые ячейки
                        continue
                    
                    # Проверяем, содержит ли опция вложенные варианты (формат: "Вариант::подвариант1;подвариант2")
                    if "::" in opt:
                        main_opt, sub_opts_str = opt.split("::", 1)
                        main_opt = main_opt.strip()  # Важно очистить пробелы до проверки
                        
                        # Проверяем, является ли это свободным ответом или подсказкой
                        if sub_opts_str.strip() == "":
                            # Пустая строка после :: означает свободный ввод
                            self.logger.data_processing("options", "Обработка варианта ответа", 
                                                      details={"тип": "свободный_ответ", "вариант": main_opt})
                            options.append({"text": main_opt, "sub_options": []})
                        # Проверяем формат с префиксом prompt=
                        elif sub_opts_str.strip().startswith("prompt="):
                            # Это специальный формат для сохранения подсказки для свободного ввода
                            free_text_prompt = sub_opts_str.strip()[7:]  # Убираем префикс "prompt="
                            self.logger.data_processing("options", "Обработка варианта ответа", 
                                                      details={"тип": "свободный_ответ_с_подсказкой", 
                                                              "вариант": main_opt, 
                                                              "подсказка": free_text_prompt})
                            options.append({
                                "text": main_opt,
                                "sub_options": [], # Пустой список означает свободный ответ
                                "free_text_prompt": free_text_prompt
                            })
                        # Проверяем другие форматы подсказок
                        elif ";" not in sub_opts_str and ("вопрос" in sub_opts_str.lower() or "введите" in sub_opts_str.lower()):
                            # Это подсказка для свободного ввода, а не список подвариантов
                            self.logger.data_processing("options", "Обработка варианта ответа", 
                                                      details={"тип": "свободный_ответ_с_подсказкой", 
                                                              "вариант": main_opt, 
                                                              "подсказка": sub_opts_str.strip()})
                            options.append({
                                "text": main_opt,
                                "sub_options": [], # Пустой список означает свободный ответ
                                "free_text_prompt": sub_opts_str.strip()
                            })
                        else:
                            # Парсим подварианты
                            sub_options_list = [sub_opt.strip() for sub_opt in sub_opts_str.split(";") if sub_opt.strip()]
                            
                            if len(sub_options_list) == 1 and ("вопрос для" in sub_options_list[0].lower() or "введите" in sub_options_list[0].lower()):
                                # Это подсказка для свободного ввода, преобразуем в соответствующий формат
                                self.logger.data_processing("options", "Обработка варианта ответа", 
                                                          details={"тип": "свободный_ответ_с_подсказкой", 
                                                                  "вариант": main_opt, 
                                                                  "подсказка": sub_options_list[0]})
                                options.append({
                                    "text": main_opt, 
                                    "sub_options": [], 
                                    "free_text_prompt": sub_options_list[0]
                                })
                            else:
                                # Обычные подварианты
                                options.append({"text": main_opt, "sub_options": sub_options_list})
                    else:
                        # Обычный вариант без подвариантов
                        options.append({"text": opt.strip()})
                
                questions_with_options[question] = options
            
            # Логируем структуру вариантов для проверки только при отладке
            options_structure = {}
            for question, opts in questions_with_options.items():
                for opt in opts:
                    if "sub_options" in opt:
                        if isinstance(opt["sub_options"], list) and opt["sub_options"] == []:
                            if "free_text_prompt" in opt:
                                option_key = f"{question}:{opt['text']}"
                                options_structure[option_key] = {"type": "free_text_with_prompt", "prompt": opt['free_text_prompt']}
                            else:
                                option_key = f"{question}:{opt['text']}"
                                options_structure[option_key] = {"type": "free_text"}
            
            if options_structure:
                self.logger.data_processing("options", "Структура специальных опций", 
                                          details={"options": str(options_structure)[:500]})
            
            questions_count = len(questions_with_options)
            self.logger.data_load("вопросы", f"Google Sheets/{self.QUESTIONS_SHEET}", count=questions_count, 
                                details={"options_count": sum(len(opts) for opts in questions_with_options.values())})
            
            return questions_with_options
            
        except Exception as e:
            self.logger.error("получение_вопросов", e, details={"sheet": self.QUESTIONS_SHEET})
            # Возвращаем пустой словарь в случае ошибки
            return {}
    
    def save_answers(self, answers: list, user_id: int) -> bool:
        """Сохранение ответов пользователя в таблицу"""
        try:
            self.logger.user_action(user_id, "Сохранение ответов", f"Начало сохранения: {len(answers)} ответов")
            start_time = datetime.now()
            
            # Получаем список вопросов
            questions = list(self.get_questions_with_options().keys())
            
            # Проверяем, что количество ответов соответствует количеству вопросов
            if len(answers) != len(questions):
                self.logger.error("несоответствие_данных", 
                                 f"Количество ответов не соответствует количеству вопросов", 
                                 details={"user_id": user_id, 
                                         "answers_count": len(answers), 
                                         "questions_count": len(questions)})
                self.logger.data_processing("answer_data", "Данные ответов пользователя", 
                                         details={"user_id": user_id, "answers": str(answers)[:300]})
                self.logger.data_processing("question_data", "Данные вопросов", 
                                         details={"user_id": user_id, "questions": str(questions)[:300]})
                return False
            
            # Получаем текущую дату и время
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Сохраняем ответы в таблицу ответов
            answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
            
            # Подготавливаем данные для добавления
            row_data = [current_time, str(user_id)] + answers
            
            self.logger.data_processing(user_id, "Отправка данных в таблицу")
            # Добавляем ответы
            answers_sheet.append_row(row_data)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.logger.data_processing(user_id, "Ответы успешно сохранены", 
                                       details={"duration": f"{duration:.2f}"})
            return True
            
        except Exception as e:
            self.logger.error("сохранение_ответов", e, details={"user_id": user_id})
            return False
    
    def update_statistics_sheet(self) -> bool:
        """Полное обновление листа статистики на основе всех ответов"""
        try:
            self.logger.data_processing("system", "Обновление листа статистики")
            
            # Получаем вопросы с вариантами ответов
            questions_with_options = self.get_questions_with_options()
            
            # Получаем данные из листа ответов
            answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
            answers_data = answers_sheet.get_all_values()
            
            if len(answers_data) <= 1:  # Только заголовок или пусто
                self.logger.data_processing("system", "Нет данных для обновления статистики", 
                                          details={"причина": "Таблица содержит только заголовки или пуста"})
                stats_sheet = self.sheet.worksheet(self.STATS_SHEET)
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
                    stats[question] = {}
                    for option in options:
                        # Добавляем основной вариант
                        option_text = option["text"]
                        stats[question][option_text] = 0
                        
                        # Добавляем вложенные варианты, если они есть
                        if option.get("sub_options"):
                            for sub_option in option["sub_options"]:
                                combined_option = f"{option_text} - {sub_option}"
                                stats[question][combined_option] = 0
            
            # Обрабатываем ответы (пропускаем заголовок)
            for row in answers_data[1:]:
                # Пропускаем дату и ID пользователя
                for i, answer in enumerate(row[2:]):
                    if i < len(questions):
                        question = questions[i]
                        # Учитываем только вопросы с вариантами ответов
                        if question in stats:
                            if answer in stats[question]:
                                stats[question][answer] += 1
            
            # Обновляем лист статистики
            stats_sheet = self.sheet.worksheet(self.STATS_SHEET)
            
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
                
                # Сортируем ответы: сначала основные варианты, потом вложенные
                main_options = {}
                nested_options = {}
                
                for option, count in answers_count.items():
                    if " - " in option:
                        main_opt, sub_opt = option.split(" - ", 1)
                        if main_opt not in nested_options:
                            nested_options[main_opt] = []
                        nested_options[main_opt].append((sub_opt, count))
                    else:
                        main_options[option] = count
                
                # Выводим статистику для каждого основного варианта и его вложенных вариантов
                for option, count in main_options.items():
                    percentage = (count / total_answers * 100) if total_answers > 0 else 0
                    stats_sheet.append_row([option, f"{percentage:.1f}%", str(count)])
                    
                    # Если у этого варианта есть вложенные, выводим их с отступом
                    if option in nested_options:
                        for sub_opt, sub_count in nested_options[option]:
                            sub_percentage = (sub_count / total_answers * 100) if total_answers > 0 else 0
                            stats_sheet.append_row([f"  └ {sub_opt}", f"{sub_percentage:.1f}%", str(sub_count)])
            
            # Добавляем общее количество опросов
            total_surveys = len(answers_data) - 1  # -1 для заголовка
            stats_sheet.append_row(["Всего пройдено опросов:", str(total_surveys)])
            
            self.logger.data_processing("system", "Лист статистики успешно обновлен")
            return True
            
        except Exception as e:
            self.logger.error("обновление_листа_статистики", e)
            return False
    
    def update_statistics(self):
        """
        Обновление статистики в отдельном листе.
        
        Подсчитывает количество и процент для каждого варианта ответа по каждому вопросу.
        Учитывает только вопросы с предопределенными вариантами ответов.
        Свободные ответы исключаются из статистики.
        """
        try:
            # Проверяем наличие листа статистики
            stats_sheet = self.sheet.worksheet(self.STATS_SHEET)
            
            if not stats_sheet:
                self.logger.warning("statistics_sheet_missing", "Лист статистики не найден", 
                                  details={"причина": "Лист не существует", "действие": "Создание невозможно"})
                return False
                
            # Получаем все ответы
            self.logger.data_processing("system", "Начало обновления статистики...")
            
            # Получаем все ответы из листа ответов
            answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
            all_responses = answers_sheet.get_all_values()
            
            if len(all_responses) <= 1:  # Только заголовки или пусто
                self.logger.warning("no_statistics_data", "Нет данных для обновления статистики", 
                                  details={"причина": "Таблица содержит только заголовки или пуста"})
                return False
                
            # Пропускаем заголовок
            responses = all_responses[1:]
            
            # Получаем вопросы
            questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
            questions_data = questions_sheet.get_all_values()
            
            if len(questions_data) <= 1:  # Только заголовки или пусто
                self.logger.warning("no_questions_for_statistics", "Нет вопросов для обработки статистики", 
                                  details={"причина": "Таблица вопросов содержит только заголовки или пуста"})
                return False
                
            # Пропускаем заголовок
            questions = [row[0] for row in questions_data[1:] if row and len(row) > 0]
            
            # Получаем структуру вопросов с вариантами для определения типа вопроса
            questions_with_options = self.get_questions_with_options()
            
            # Словарь для подсчета статистики
            stats = {}
            
            # Для отладки - записываем информацию о структуре ответов
            self.logger.data_processing("statistics", "Анализ структуры ответов", 
                                     details={"заголовки": all_responses[0][:5], 
                                            "ответы_пример": str(responses[0][:5]) if responses else "нет ответов"})
            
            # Индексы вопросов в ответах
            # Первый столбец в responses - это timestamp, второй - user_id, начиная с третьего идут ответы
            for i, question in enumerate(questions):
                question_idx = i + 2  # +2 потому что первые два столбца - timestamp и user_id
                
                # Проверка на корректность индекса
                if question_idx >= len(all_responses[0]) and len(all_responses[0]) > 0:
                    self.logger.warning("incorrect_question_index", "Некорректный индекс вопроса", 
                                     details={"вопрос": question, "индекс": question_idx, 
                                            "количество_столбцов": len(all_responses[0])})
                    continue
                
                # Получаем варианты ответов для этого вопроса, чтобы определить тип
                question_options = questions_with_options.get(question, [])
                
                # Улучшенная проверка: вопрос считается с предопределенными вариантами, 
                # только если у него есть хотя бы один фиксированный вариант ответа
                has_predefined_options = False
                predefined_option_texts = []
                
                # Логируем информацию о вариантах ответов для отладки
                self.logger.data_processing("statistics", f"Анализ вариантов вопроса: {question}", 
                                         details={"варианты": str(question_options)[:300]})
                
                for opt in question_options:
                    # Если это простой текстовый вариант
                    if not isinstance(opt, dict):
                        has_predefined_options = True
                        predefined_option_texts.append(str(opt))
                        continue
                    
                    # Если это словарь с текстом
                    if isinstance(opt, dict) and "text" in opt:
                        # Проверяем, имеет ли вариант подварианты для выбора или это просто контейнер для свободного ввода
                        if "sub_options" not in opt or (isinstance(opt["sub_options"], list) and len(opt["sub_options"]) > 0):
                            # Вариант имеет подварианты для выбора или не имеет подвариантов вообще (обычный вариант)
                            has_predefined_options = True
                            predefined_option_texts.append(opt["text"])
                
                # Если у вопроса нет предопределенных вариантов, это свободный ввод - пропускаем его
                if not has_predefined_options or len(predefined_option_texts) == 0:
                    self.logger.data_processing("statistics", "Пропуск вопроса со свободным вводом", 
                                               details={"вопрос": question})
                    continue
                
                # Логируем найденные предопределенные варианты
                self.logger.data_processing("statistics", f"Предопределенные варианты для вопроса: {question}", 
                                        details={"варианты": str(predefined_option_texts)})
                
                # Список всех ответов на этот вопрос
                answers = []
                for row in responses:
                    if len(row) > question_idx:
                        answer = row[question_idx]
                        # Проверяем, является ли ответ одним из предопределенных вариантов или начинается с него
                        for opt_text in predefined_option_texts:
                            if answer == opt_text or answer.startswith(opt_text + " - "):
                                answers.append(answer)
                                break
                
                # Логируем количество найденных ответов для отладки
                self.logger.data_processing("statistics", f"Найдено ответов для вопроса: {question}", 
                                        details={"количество": len(answers), 
                                                "примеры": str(answers[:3]) if answers else "нет ответов"})
                
                # Группируем ответы для подсчета статистики
                answer_counts = {}
                for answer in answers:
                    # Проверяем, является ли ответ свободным вводом для варианта
                    is_free_text_answer = False
                    
                    # Обрабатываем составные ответы
                    if " - " in answer:
                        parts = answer.split(" - ", 1)
                        main_part = parts[0]
                        
                        # Проверяем, соответствует ли основная часть варианту со свободным вводом
                        for opt in question_options:
                            if isinstance(opt, dict) and "text" in opt and opt["text"] == main_part:
                                # Если для этого варианта есть свободный ввод, пропускаем детальную статистику
                                if "sub_options" in opt and isinstance(opt["sub_options"], list) and not opt["sub_options"]:
                                    # Учитываем только основной вариант, а не подварианты
                                    if main_part not in answer_counts:
                                        answer_counts[main_part] = 0
                                    answer_counts[main_part] += 1
                                    is_free_text_answer = True
                                    break
                        
                        # Если это не свободный ввод, обрабатываем как обычный подвариант
                        if not is_free_text_answer and len(parts) > 1:
                            sub_part = parts[1]
                            
                            # Учитываем основной вариант
                            if main_part not in answer_counts:
                                answer_counts[main_part] = 0
                            answer_counts[main_part] += 1
                            
                            # Учитываем подвариант (без добавочного текста)
                            compound_key = f"{main_part} - {sub_part.split(' (на вопрос:', 1)[0]}"
                            if compound_key not in answer_counts:
                                answer_counts[compound_key] = 0
                            answer_counts[compound_key] += 1
                    else:
                        # Простой ответ
                        if answer not in answer_counts:
                            answer_counts[answer] = 0
                        answer_counts[answer] += 1
                
                # Если есть ответы для этого вопроса, добавляем в статистику
                if answer_counts:
                    stats[question] = answer_counts
                    self.logger.data_processing("statistics", f"Подсчитанная статистика для вопроса: {question}", 
                                            details={"статистика": str(answer_counts)})
            
            # Очищаем лист статистики и обновляем заголовки
            stats_sheet.clear()
            stats_sheet.update_cell(1, 1, "Вопрос")
            stats_sheet.update_cell(1, 2, "Вариант ответа")
            stats_sheet.update_cell(1, 3, "Количество")
            stats_sheet.update_cell(1, 4, "Процент")
            
            # Если нет данных для статистики, завершаем работу
            if not stats:
                self.logger.warning("no_statistics_data", "Нет данных для статистики", 
                                  details={"причина": "Все вопросы являются вопросами со свободным вводом или нет ответов на вопросы с вариантами"})
                return True
            
            # Заполняем статистику
            row = 2
            for question, answer_counts in stats.items():
                # Получаем только ответы, которые соответствуют предопределенным вариантам
                question_options = questions_with_options.get(question, [])
                predefined_option_texts = []
                
                for opt in question_options:
                    if not isinstance(opt, dict):
                        predefined_option_texts.append(str(opt))
                    elif "text" in opt:
                        predefined_option_texts.append(opt["text"])
                
                for answer, count in answer_counts.items():
                    # Проверяем, соответствует ли ответ предопределенному варианту или его подварианту
                    is_predefined = False
                    for opt_text in predefined_option_texts:
                        if answer == opt_text or (isinstance(answer, str) and " - " in answer and answer.startswith(opt_text + " - ")):
                            is_predefined = True
                            break
                    
                    if not is_predefined:
                        # Пропускаем ответы, которые не соответствуют предопределенным вариантам
                        self.logger.data_processing("statistics", f"Пропуск неопределенного ответа", 
                                                details={"вопрос": question, "ответ": answer})
                        continue
                        
                    # Вычисляем процент
                    total_answers = sum(answer_counts.values())
                    percentage = 0 if total_answers == 0 else (count / total_answers) * 100
                    
                    # Добавляем строку статистики
                    stats_sheet.update_cell(row, 1, question)
                    stats_sheet.update_cell(row, 2, answer)
                    stats_sheet.update_cell(row, 3, count)
                    stats_sheet.update_cell(row, 4, f"{percentage:.1f}%")
                    
                    row += 1
            
            self.logger.data_processing("system", "Статистика успешно обновлена", 
                                       details={"responses": len(responses), 
                                               "questions": len(questions), 
                                               "questions_in_stats": len(stats)})
            return True
            
        except Exception as e:
            self.logger.error("обновление_статистики", e)
            return False

    def update_stats_sheet_with_percentages(self) -> bool:
        """Обновление листа статистики с процентами для всех вариантов ответов"""
        try:
            self.logger.data_processing("system", "Обновление листа статистики с процентами")
            
            # Получаем данные для статистики
            answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
            answers_data = answers_sheet.get_all_values()
            
            # Пропускаем заголовок
            if len(answers_data) <= 1:
                self.logger.data_processing("system", "Нет данных для статистики")
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
            stats_sheet = self.sheet.worksheet(self.STATS_SHEET)
            
            # Очищаем текущие данные
            stats_sheet.clear()
            
            # Добавляем заголовок
            stats_sheet.append_row(["Статистика опроса"])
            
            # Добавляем статистику по каждому вопросу
            for question, total in question_totals.items():
                # Получаем все возможные варианты ответов для этого вопроса
                all_options = questions_with_options.get(question, [])
                
                # Проверяем, имеет ли вопрос предопределенные варианты ответов
                has_predefined_options = False
                for opt in all_options:
                    # Если это обычный вариант ответа (текст или словарь без свободного ввода)
                    if isinstance(opt, dict) and "sub_options" in opt:
                        # Если sub_options непустой список или отсутствует, это предопределенный вариант
                        if "sub_options" not in opt or (isinstance(opt["sub_options"], list) and opt["sub_options"]):
                            has_predefined_options = True
                            break
                    else:
                        # Простой текстовый вариант считается предопределенным
                        has_predefined_options = True
                        break
                
                # Пропускаем вопросы со свободным вводом
                if not has_predefined_options:
                    self.logger.data_processing("statistics", "Пропуск вопроса со свободным вводом", 
                                               details={"вопрос": question})
                    continue
                
                # Добавляем строку с вопросом
                stats_sheet.append_row([question])
                
                # Обрабатываем ответы с вариантами выбора
                processed_options = {}
                
                # Обрабатываем все полученные ответы
                for answer, count in question_answers[question].items():
                    # Проверяем, является ли ответ составным (с вложенным свободным вводом)
                    if " - " in answer:
                        parts = answer.split(" - ", 1)
                        main_part = parts[0]
                        
                        # Проверяем, является ли основной вариант свободным вводом
                        is_free_text_option = False
                        for opt in all_options:
                            if isinstance(opt, dict) and "text" in opt and opt["text"] == main_part:
                                if "sub_options" in opt and isinstance(opt["sub_options"], list) and not opt["sub_options"]:
                                    is_free_text_option = True
                                    break
                        
                        # Если вариант со свободным вводом, учитываем только основную часть
                        if is_free_text_option:
                            if main_part not in processed_options:
                                processed_options[main_part] = 0
                            processed_options[main_part] += count
                        else:
                            # Обычный вариант с подвариантом, учитываем полный ответ
                            if answer not in processed_options:
                                processed_options[answer] = 0
                            processed_options[answer] += count
                    else:
                        # Простой ответ
                        if answer not in processed_options:
                            processed_options[answer] = 0
                        processed_options[answer] += count
                
                # Выводим статистику по обработанным вариантам
                for option, count in processed_options.items():
                    percentage = (count / total * 100) if total > 0 else 0
                    stats_sheet.append_row([option, f"{percentage:.1f}%", str(count)])
                
                # Добавляем пустую строку после вопроса
                stats_sheet.append_row([""])
            
            # Добавляем общее количество опросов
            total_surveys = len(answers_data) - 1
            stats_sheet.append_row(["Всего пройдено опросов:", str(total_surveys)])
            
            self.logger.data_processing("system", "Лист статистики успешно обновлен с процентами")
            return True
            
        except Exception as e:
            self.logger.error("обновление_статистики_с_процентами", e)
            return False
    
    def get_statistics_from_sheet(self) -> str:
        """Получение статистики из листа статистики"""
        try:
            self.logger.data_processing("system", "Получение статистики из листа")
            
            # Получаем данные из листа статистики
            stats_sheet = self.sheet.worksheet(self.STATS_SHEET)
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
            self.logger.error("получение_статистики", e)
            return "❌ Ошибка при получении статистики"
    
    def get_admins(self) -> list:
        """Получение списка ID админов из таблицы"""
        # Используем кэш для получения списка админов
        def actual_fetch():
            try:
                self.logger.data_processing("system", "Получение списка админов из таблицы")
                
                # Проверяем существование листа с админами
                try:
                    admins_sheet = self.sheet.worksheet(self.ADMINS_SHEET)
                except gspread.exceptions.WorksheetNotFound:
                    self.logger.warning("admins_sheet_not_found", "Лист администраторов не найден", 
                                      details={"лист": self.ADMINS_SHEET, "действие": "Создание нового листа"})
                    # Создаем лист с админами, если его нет
                    admins_sheet = self.sheet.add_worksheet(title=self.ADMINS_SHEET, rows=100, cols=2)
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
                            self.logger.warning("invalid_admin_id", "Некорректный формат ID администратора", 
                                             details={"значение": row[0], "ожидаемый_тип": "целое число"})
                
                # Добавляем админов из переменной окружения
                env_admins = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
                for admin_id in env_admins:
                    if admin_id not in admin_ids:
                        admin_ids.append(admin_id)
                
                self.logger.data_processing("system", f"Получено {len(admin_ids)} админов", 
                                           details={"admins": admin_ids})
                return admin_ids
                
            except Exception as e:
                self.logger.error("получение_списка_админов", e)
                # Возвращаем админов из переменной окружения в случае ошибки
                env_admins = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]
                self.logger.data_processing("system", "Используем админов из переменной окружения", 
                                           details={"admins": env_admins})
                return env_admins
                
        return sheets_cache.get_admins(actual_fetch)

    def get_admins_info(self) -> list:
        """Получает полную информацию об администраторах (ID, имя, описание)"""
        try:
            self.logger.data_processing("system", "Получение информации об администраторах")
            
            # Получаем данные из листа администраторов
            admins_sheet = self.sheet.worksheet(self.ADMINS_SHEET)
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
            
            self.logger.data_processing("system", "Получена информация об администраторах", 
                                      details={"count": len(admins_info)})
            return admins_info
            
        except Exception as e:
            self.logger.error("получение_информации_о_администраторах", e)
            return []

    def get_statistics(self) -> list:
        """Получение статистики ответов для вопросов с вариантами"""
        try:
            self.logger.data_processing("system", "Получение статистики ответов")
            
            # Получаем вопросы с вариантами ответов
            questions_with_options = self.get_questions_with_options()
            
            # Получаем все ответы
            answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
            all_values = answers_sheet.get_all_values()
            
            if len(all_values) < 2:  # Если есть только заголовки или лист пустой
                return []
            
            headers = all_values[0]
            answers = all_values[1:]
            
            statistics = []
            
            # Для каждого вопроса с вариантами
            for question, options in questions_with_options.items():
                # Проверяем, является ли вопрос вопросом со свободным вводом
                has_predefined_options = False
                for opt in options:
                    # Если это обычный вариант ответа (текст или словарь без свободного ввода)
                    if isinstance(opt, dict) and "sub_options" in opt:
                        # Если sub_options непустой список или отсутствует, это предопределенный вариант
                        if "sub_options" not in opt or (isinstance(opt["sub_options"], list) and opt["sub_options"]):
                            has_predefined_options = True
                            break
                    else:
                        # Простой текстовый вариант считается предопределенным
                        has_predefined_options = True
                        break
                
                # Пропускаем вопросы со свободным вводом
                if not has_predefined_options:
                    self.logger.data_processing("statistics", "Пропуск вопроса со свободным вводом", 
                                               details={"вопрос": question})
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
                            # Обрабатываем составные ответы для свободного ввода
                            if " - " in answer:
                                parts = answer.split(" - ", 1)
                                main_part = parts[0]
                                
                                # Проверяем, является ли основной вариант свободным вводом
                                is_free_text_option = False
                                for opt in options:
                                    if isinstance(opt, dict) and "text" in opt and opt["text"] == main_part:
                                        if "sub_options" in opt and isinstance(opt["sub_options"], list) and not opt["sub_options"]:
                                            is_free_text_option = True
                                            break
                                
                                # Если это свободный ввод, учитываем только основную часть
                                if is_free_text_option:
                                    option_counts[main_part] = option_counts.get(main_part, 0) + 1
                                    total_answers += 1
                                else:
                                    option_counts[answer] = option_counts.get(answer, 0) + 1
                                    total_answers += 1
                            else:
                                option_counts[answer] = option_counts.get(answer, 0) + 1
                                total_answers += 1
                
                # Формируем статистику 
                for answer, count in option_counts.items():
                    percentage = round((count / total_answers * 100) if total_answers > 0 else 0)
                    statistics.append([question, answer, count])
            
            self.logger.data_processing("system", f"Получено {len(statistics)} строк статистики")
            return statistics
            
        except Exception as e:
            self.logger.error("получение_статистики_ответов", e)
            return []

    def get_sheet_values(self, sheet_name):
        """Получение всех значений с указанного листа"""
        try:
            self.logger.data_load("sheet_values", f"Получение данных с листа {sheet_name}")
            
            # Проверяем, может быть нам нужно использовать имя листа из SHEET_NAMES
            if sheet_name in self.SHEET_NAMES:
                actual_sheet_name = self.SHEET_NAMES[sheet_name]
                self.logger.data_processing("sheets", "Преобразование имени листа", 
                                          details={"original": sheet_name, "actual": actual_sheet_name})
            else:
                actual_sheet_name = sheet_name
                
            worksheet = self.sheet.worksheet(actual_sheet_name)
            values = worksheet.get_all_values()
            self.logger.data_load("sheet_values", f"Получено данных с листа {sheet_name}", 
                                count=len(values))
            return values
        except Exception as e:
            self.logger.error("получение_данных_листа", e, details={"sheet_name": sheet_name})
            return None

    def get_next_user_id(self) -> int:
        """Получение следующего доступного ID пользователя"""
        try:
            values = self.get_sheet_values('users')
            if not values or len(values) == 1:  # Только заголовки
                return 1
                
            # Безопасное извлечение ID с обработкой ошибок
            max_id = 0
            for row in values[1:]:  # Пропускаем заголовок
                try:
                    if row and row[0] and row[0].strip():
                        user_id = int(row[0])
                        if user_id > max_id:
                            max_id = user_id
                except (ValueError, TypeError, IndexError):
                    # Пропускаем некорректные значения
                    continue
                    
            return max_id + 1
        except Exception as e:
            self.logger.error("получение_id_пользователя", e)
            return 1

    def initialize_users_sheet(self) -> bool:
        """Инициализация листа пользователей"""
        try:
            self.logger.init("sheets", "Инициализация листа пользователей")
            
            # Проверяем существование листа
            try:
                users_sheet = self.sheet.worksheet(self.SHEET_NAMES['users'])
            except gspread.exceptions.WorksheetNotFound:
                self.logger.init("sheets", "Создание нового листа пользователей")
                users_sheet = self.sheet.add_worksheet(
                    title=self.SHEET_NAMES['users'],
                    rows=1000,
                    cols=len(self.SHEET_HEADERS['users'])
                )
                # Добавляем заголовки
                users_sheet.update('A1:D1', [self.SHEET_HEADERS['users']])
                self.logger.init("sheets", "Заголовки листа пользователей установлены")
                return True
            
            # Проверяем и обновляем заголовки
            current_headers = users_sheet.row_values(1)
            if not current_headers or current_headers != self.SHEET_HEADERS['users']:
                self.logger.init("sheets", "Обновление заголовков листа пользователей")
                users_sheet.update('A1:D1', [self.SHEET_HEADERS['users']])
                self.logger.init("sheets", "Заголовки листа пользователей обновлены")
            
            return True
        except Exception as e:
            self.logger.error("инициализация_листа_пользователей", e)
            return False

    def add_user(self, telegram_id: int, username: str) -> bool:
        """Добавление нового пользователя"""
        try:
            # Проверяем, существует ли пользователь с таким telegram_id
            if self.is_user_exists(telegram_id):
                self.logger.user_action(telegram_id, "Повторная регистрация", 
                                      details={"username": username})
                return True  # Пользователь уже существует, считаем операцию успешной
                
            # Получаем лист пользователей
            users_sheet = self.sheet.worksheet(self.SHEET_NAMES['users'])
            
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
            
            # Инвалидируем кэш пользователей
            sheets_cache.invalidate_user_cache()
            
            self.logger.admin_action("system", "Добавление пользователя", 
                                    details={"user_id": user_id, "telegram_id": telegram_id, "username": username})
            return True
        except Exception as e:
            self.logger.error("добавление_пользователя", e, details={"telegram_id": telegram_id})
            return False

    def is_user_exists(self, telegram_id: int) -> bool:
        """Проверка существования пользователя"""
        # Используем кэш для проверки существования пользователя
        def actual_check(telegram_id):
            try:
                # Оптимизированный поиск с использованием фильтра по столбцу telegram_id
                users_sheet = self.sheet.worksheet(self.SHEET_NAMES['users'])
                
                # Находим ячейки, содержащие telegram_id
                cell_list = users_sheet.findall(str(telegram_id))
                
                # Проверяем, находится ли хотя бы одна из найденных ячеек во 2-м столбце (индекс 1)
                for cell in cell_list:
                    if cell.col == 2:  # Столбец B (telegram_id)
                        return True
                        
                return False
            except Exception as e:
                self.logger.error("проверка_существования_пользователя", e, details={"telegram_id": telegram_id})
                return False
                
        return sheets_cache.is_user_exists(telegram_id, lambda tid: actual_check(tid))

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
            self.logger.error("получение_списка_пользователей", e, 
                             details={"page": page, "page_size": page_size})
            return [], 0, 0

    def initialize_messages_sheet(self) -> bool:
        """Инициализация листа сообщений"""
        try:
            self.logger.init("sheets", "Инициализация листа сообщений")
            
            # Проверяем существование листа
            try:
                messages_sheet = self.sheet.worksheet(self.SHEET_NAMES['messages'])
                
                # Проверяем и обновляем структуру при необходимости
                headers = messages_sheet.row_values(1)
                if len(headers) < len(self.SHEET_HEADERS['messages']):
                    self.logger.init("sheets", "Обновление структуры таблицы сообщений")
                    messages_sheet.update('A1:D1', [self.SHEET_HEADERS['messages']])
                    
                    # Обновляем существующие данные, добавляя пустое значение для изображения
                    rows = messages_sheet.get_all_values()[1:]  # Пропускаем заголовок
                    for i, row in enumerate(rows, start=2):
                        # Если строка имеет только тип и текст (и возможно дату)
                        if len(row) < 3 or 'Изображение' not in headers:
                            # Добавляем пустое значение для изображения перед датой
                            message_type = row[0]
                            message_text = row[1]
                            date = row[2] if len(row) > 2 else datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            messages_sheet.update(f'A{i}:D{i}', [[message_type, message_text, "", date]])
                
            except gspread.exceptions.WorksheetNotFound:
                self.logger.init("sheets", "Создание нового листа сообщений")
                messages_sheet = self.sheet.add_worksheet(
                    title=self.SHEET_NAMES['messages'],
                    rows=100,
                    cols=len(self.SHEET_HEADERS['messages'])
                )
                # Добавляем заголовки
                messages_sheet.update('A1:D1', [self.SHEET_HEADERS['messages']])
                
                # Добавляем сообщения по умолчанию
                current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                default_rows = [
                    ['start', self.DEFAULT_MESSAGES['start'], "", current_time],
                    ['finish', self.DEFAULT_MESSAGES['finish'], "", current_time]
                ]
                messages_sheet.update('A2:D3', default_rows)
                self.logger.init("sheets", "Добавлены сообщения по умолчанию")
            
            return True
        except Exception as e:
            self.logger.error("инициализация_листа_сообщений", e)
            return False

    def get_message(self, message_type: str) -> dict:
        """Получение текста и изображения сообщения по его типу"""
        # Используем кэш для получения сообщения
        def actual_fetch(message_type):
            try:
                messages_sheet = self.sheet.worksheet(self.SHEET_NAMES['messages'])
                all_messages = messages_sheet.get_all_values()
                
                # Пропускаем заголовок
                if len(all_messages) > 1:
                    for row in all_messages[1:]:
                        if row[0] == message_type:
                            # Возвращаем текст и изображение
                            image_url = row[2] if len(row) > 2 else ""
                            return {
                                "text": row[1],
                                "image": image_url
                            }
                
                # Если сообщение не найдено, возвращаем значение по умолчанию
                return {
                    "text": self.DEFAULT_MESSAGES.get(message_type, ''),
                    "image": ""
                }
                
            except Exception as e:
                self.logger.error("получение_сообщения", e, details={"message_type": message_type})
                return {
                    "text": self.DEFAULT_MESSAGES.get(message_type, ''),
                    "image": ""
                }
                
        return sheets_cache.get_message(message_type, lambda mt: actual_fetch(mt))

    def update_message(self, message_type: str, new_text: str, image_url: str = None) -> bool:
        """Обновление текста и изображения сообщения"""
        try:
            if message_type not in self.MESSAGE_TYPES:
                self.logger.error("неизвестный_тип_сообщения", f"Неизвестный тип сообщения", details={"message_type": message_type})
                return False
                
            messages_sheet = self.sheet.worksheet(self.SHEET_NAMES['messages'])
            all_messages = messages_sheet.get_all_values()
            
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message_row = None
            
            # Ищем строку с нужным типом сообщения
            for i, row in enumerate(all_messages):
                if row[0] == message_type:
                    message_row = i + 1  # +1 так как индексация с 1
                    break
            
            if message_row:
                # Если image_url не передан, сохраняем текущее значение
                current_image = ""
                if len(all_messages[message_row-1]) > 2:
                    current_image = all_messages[message_row-1][2]
                
                image_to_save = image_url if image_url is not None else current_image
                
                # Обновляем существующую строку
                messages_sheet.update(f'B{message_row}:D{message_row}', [[new_text, image_to_save, current_time]])
            else:
                # Добавляем новую строку
                messages_sheet.append_row([
                    message_type, 
                    new_text, 
                    image_url if image_url is not None else "", 
                    current_time
                ])
            
            # Инвалидируем кэш сообщений для обновленного типа
            sheets_cache.invalidate_messages_cache(message_type)
            
            self.logger.admin_action("system", "Сообщение успешно обновлено", details={"message_type": message_type})
            return True
            
        except Exception as e:
            self.logger.error("обновление_сообщения", e, details={"message_type": message_type})
            return False

    def initialize_posts_sheet(self) -> bool:
        """Инициализация листа постов"""
        try:
            self.logger.init("sheets", "Инициализация листа постов")
            
            # Проверяем, существует ли уже лист с постами
            try:
                posts_sheet = self.sheet.worksheet(self.SHEET_NAMES['posts'])
                self.logger.init("sheets", "Лист постов уже существует")
                
                # Проверяем и обновляем заголовки для существующего листа
                current_headers = posts_sheet.row_values(1)
                if current_headers and len(current_headers) < len(self.SHEET_HEADERS['posts']):
                    self.logger.init("sheets", "Обновление структуры таблицы постов")
                    posts_sheet.update('A1:H1', [self.SHEET_HEADERS['posts']])
                    self.logger.init("sheets", "Структура таблицы постов обновлена")
                    
                    # Мигрируем существующие данные
                    self.migrate_posts_data()
                
            except gspread.exceptions.WorksheetNotFound:
                # Создаем новый лист для постов
                posts_sheet = self.sheet.add_worksheet(
                    title=self.SHEET_NAMES['posts'],
                    rows=1000,
                    cols=10
                )
                self.logger.init("sheets", "Создан новый лист для постов")
                
                # Добавляем заголовки
                posts_sheet.append_row(self.SHEET_HEADERS['posts'])
                self.logger.init("sheets", "Добавлены заголовки в лист постов")
            
            return True
            
        except Exception as e:
            self.logger.error("инициализация_листа_постов", e)
            return False

    def migrate_posts_data(self):
        """Миграция данных в таблице постов для добавления столбца 'Название'"""
        try:
            self.logger.data_processing("Начало миграции данных постов")
            
            # Получаем лист с постами
            posts_sheet = self.sheet.worksheet(self.SHEET_NAMES['posts'])
            
            # Получаем все данные (пропускаем заголовок)
            data = posts_sheet.get_all_values()
            if len(data) <= 1:  # Только заголовок или пусто
                self.logger.data_processing("Миграция данных постов не требуется", details={"reason": "Нет данных для миграции"})
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
            
            self.logger.init("sheets", "Миграция данных постов завершена успешно")
            return True
            
        except Exception as e:
            self.logger.error("миграция_данных_постов", e)
            return False
    
    def save_post(self, title: str, text: str, image_url: str, button_text: str, button_url: str, admin_id: int) -> int:
        """Сохранение поста в таблицу"""
        try:
            self.logger.admin_action(admin_id, "Сохранение поста", f"Заголовок: {title[:30]}...")
            
            # Открываем лист с постами
            posts_sheet = self.sheet.worksheet(self.SHEET_NAMES['posts'])
            
            # Получаем текущую дату и время
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Генерируем уникальный ID для поста
            post_id = str(int(datetime.now().timestamp()))
            
            # Подготавливаем данные для добавления
            row_data = [post_id, title, text, image_url, button_text, button_url, current_time, str(admin_id)]
            
            # Добавляем пост
            posts_sheet.append_row(row_data)
            
            # Инвалидируем кэш постов
            sheets_cache.invalidate_posts_cache()
            
            self.logger.admin_action("system", "Пост успешно сохранен", details={"post_id": post_id, "admin_id": admin_id})
            return post_id
            
        except Exception as e:
            self.logger.error("сохранение_поста", e)
            return 0
    
    def get_all_posts(self) -> list:
        """Получение всех постов из таблицы"""
        # Используем кэш для получения постов
        def actual_fetch():
            try:
                self.logger.data_processing("system", "Получение всех постов")
                posts_sheet = self.sheet.worksheet(self.SHEET_NAMES['posts'])
                
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
                
                self.logger.data_processing("system", f"Получено {len(posts)} постов")
                return posts
                
            except Exception as e:
                self.logger.error("получение_постов", e)
                return []
                
        return sheets_cache.get_posts(actual_fetch)
    
    def get_post_by_id(self, post_id: str) -> dict:
        """Получение поста по ID"""
        try:
            self.logger.data_processing("system", f"Получение поста с ID {post_id}")
            posts_sheet = self.sheet.worksheet(self.SHEET_NAMES['posts'])
            
            # Находим пост по ID
            cell = posts_sheet.find(post_id)
            if not cell:
                self.logger.warning("post_not_found", "Пост не найден в таблице", 
                                  details={"post_id": post_id, "действие": "Пропуск операции"})
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
            
            self.logger.data_processing("system", f"Пост с ID {post_id} успешно получен")
            return post
            
        except Exception as e:
            self.logger.error("получение_поста", e, details={"post_id": post_id})
            return {}
    
    def update_post(self, post_id, text=None, image_url=None, button_text=None, button_url=None):
        """Обновляет существующий пост по ID"""
        self.logger.admin_action("system", f"Обновление поста", 
                               details={"post_id": post_id, "text": text and text[:30]+"...", 
                                        "image_url": image_url, "button_text": button_text, 
                                        "button_url": button_url})
        
        try:
            # Получаем все посты
            posts_sheet = self.sheet.worksheet(self.SHEET_NAMES['posts'])
            rows = posts_sheet.get_all_values()
            
            # Ищем пост по ID
            row_index = None
            for idx, row in enumerate(rows[1:], 2):  # Начинаем с 2, так как первая строка - заголовки
                if len(row) >= 1 and row[0] == str(post_id):
                    row_index = idx
                    self.logger.data_processing("posts", "Найден пост в таблице", 
                                             details={"post_id": post_id, "строка": row_index})
                    break
            
            if row_index is None:
                self.logger.warning("post_not_found", "Пост не найден для обновления", 
                                  details={"post_id": post_id, "действие": "Пропуск обновления"})
                return False
            
            # Обновляем только те поля, которые переданы
            if text is not None:
                self.logger.data_processing("posts", "Обновление поля поста", 
                                         details={"post_id": post_id, "поле": "текст", "предпросмотр": text[:30]+"..." if len(text) > 30 else text})
                posts_sheet.update_cell(row_index, 2, text)
            
            if image_url is not None:
                self.logger.data_processing("posts", "Обновление поля поста", 
                                         details={"post_id": post_id, "поле": "изображение", "url": image_url})
                posts_sheet.update_cell(row_index, 3, image_url)
            
            if button_text is not None:
                self.logger.data_processing("posts", "Обновление поля поста", 
                                         details={"post_id": post_id, "поле": "текст кнопки", "значение": button_text})
                posts_sheet.update_cell(row_index, 4, button_text)
            
            if button_url is not None:
                self.logger.data_processing("posts", "Обновление поля поста", 
                                         details={"post_id": post_id, "поле": "url кнопки", "значение": button_url})
                posts_sheet.update_cell(row_index, 5, button_url)
            
            self.logger.admin_action("system", "Пост успешно обновлен", details={"post_id": post_id})
            return True
            
        except Exception as e:
            self.logger.error("обновление_поста", e, details={"post_id": post_id})
            return False
    
    def delete_post(self, post_id):
        """Удаляет пост по его ID"""
        self.logger.admin_action("system", "Удаление поста", details={"post_id": post_id})
        
        try:
            # Получаем все посты
            posts_sheet = self.sheet.worksheet(self.SHEET_NAMES['posts'])
            rows = posts_sheet.get_all_values()
            
            # Ищем пост по ID
            row_index = None
            for idx, row in enumerate(rows[1:], 2):  # Начинаем с 2, так как первая строка - заголовки
                if len(row) >= 1 and row[0] == str(post_id):
                    row_index = idx
                    break
            
            if row_index is None:
                self.logger.warning("post_not_found", "Пост не найден для удаления", 
                                  details={"post_id": post_id, "действие": "Пропуск удаления"})
                return False
            
            # Удаляем строку
            posts_sheet.delete_rows(row_index)
            
            # Инвалидируем кэш постов
            sheets_cache.invalidate_posts_cache()
            
            self.logger.admin_action("system", "Пост успешно удален", details={"post_id": post_id})
            return True
            
        except Exception as e:
            self.logger.error("удаление_поста", e)
            return False

    # Асинхронная реализация для операций с Google Sheets с учетом ограничения запросов
    async def async_is_user_exists(self, telegram_id: int) -> bool:
        """Асинхронная проверка существования пользователя с учетом ограничения запросов"""
        return await sheets_cache.execute_with_rate_limit(self.is_user_exists, telegram_id)
        
    async def async_add_user(self, telegram_id: int, username: str) -> bool:
        """Асинхронное добавление пользователя с учетом ограничения запросов"""
        return await sheets_cache.execute_with_rate_limit(self.add_user, telegram_id, username)
        
    async def async_get_message(self, message_type: str) -> dict:
        """Асинхронное получение сообщения с учетом ограничения запросов"""
        return await sheets_cache.execute_with_rate_limit(self.get_message, message_type)
        
    async def async_get_admins(self) -> list:
        """Асинхронное получение списка админов с учетом ограничения запросов"""
        return await sheets_cache.execute_with_rate_limit(self.get_admins)
        
    async def async_get_all_posts(self) -> list:
        """Асинхронное получение всех постов с учетом ограничения запросов"""
        return await sheets_cache.execute_with_rate_limit(self.get_all_posts)
        
    async def async_save_answers(self, answers: list, user_id: int) -> bool:
        """Асинхронное сохранение ответов с учетом ограничения запросов"""
        return await sheets_cache.execute_with_rate_limit(self.save_answers, answers, user_id)

# Импортируем и добавляем методы из sheets_questions к классу GoogleSheets
# Размещаем импорт в конце файла чтобы избежать циклических зависимостей
from utils.sheets_questions import * 