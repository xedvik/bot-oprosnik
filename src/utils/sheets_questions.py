"""
Методы для работы с вопросами в Google Sheets
"""

import time
from utils.sheets import GoogleSheets
from utils.logger import get_logger
from gspread.exceptions import APIError

# Получаем логгер для модуля
logger = get_logger()

# Добавление функции для безопасного выполнения API-запросов с повторными попытками
def safe_api_call(func, max_retries=3, base_delay=2):
    """Декоратор для безопасного выполнения API-запросов с повторными попытками при превышении квоты"""
    def wrapper(*args, **kwargs):
        retries = 0
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except APIError as e:
                if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                    wait_time = base_delay * (2 ** retries)  # экспоненциальная задержка
                    logger.data_processing("api_quota_exceeded", f"Превышение квоты API Google Sheets", 
                                         details={"ожидание": f"{wait_time} сек", "попытка": f"{retries+1}/{max_retries}"})
                    time.sleep(wait_time)
                    retries += 1
                    if retries == max_retries:
                        logger.error("исчерпаны_все_попытки_выполнения_api_запроса_последняя_ошибка", e, 
                                    details={"модуль": "sheets_questions"})
                        return False
                else:
                    logger.error("ошибка_api_google_sheets", e, 
                                details={"модуль": "sheets_questions"})
                    return False
            except Exception as e:
                logger.error("неожиданная_ошибка", e, 
                            details={"модуль": "sheets_questions"})
                return False
    return wrapper

# Добавляем методы в класс GoogleSheets
def add_question(self, question: str, options: list = None) -> bool:
    """Добавление нового вопроса в таблицу"""
    try:
        logger.data_processing("вопрос", f"Добавление нового вопроса: {question}", 
                               details={"вопрос": question})
        logger.data_processing("варианты", f"Варианты ответов: {options}", 
                               details={"количество": len(options) if options else 0})
        
        questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
        
        # Подготавливаем данные для добавления
        row_data = [question]
        if options:
            # Преобразуем варианты ответов в нужный формат
            for option in options:
                if isinstance(option, dict) and "text" in option:
                    option_text = option["text"]
                    option_for_sheet = option_text
                    
                    # Если есть вложенные варианты или пустой список sub_options, форматируем соответственно
                    if "sub_options" in option:
                        if isinstance(option["sub_options"], list):
                            if len(option["sub_options"]) > 0:
                                # Непустой список подвариантов
                                sub_options_str = ";".join(option["sub_options"])
                                option_for_sheet = f"{option_text}::{sub_options_str}"
                                logger.data_processing("варианты", f"Вариант '{option_text}' с подвариантами", 
                                                     details={"подварианты": option['sub_options']})
                            elif len(option["sub_options"]) == 0:
                                # Пустой список подвариантов - свободный ответ
                                option_for_sheet = f"{option_text}::"
                                logger.data_processing("варианты", f"Вариант '{option_text}' со свободным ответом", 
                                                     details={"тип": "пустой список sub_options"})
                        else:
                            logger.data_processing("варианты", f"Некорректный тип sub_options", 
                                                 details={"вариант": option_text, "тип": str(type(option['sub_options']))})
                    
                    logger.data_processing("таблицы", f"Добавляем в строку вариант", 
                                         details={"вариант": option_for_sheet})
                    row_data.append(option_for_sheet)
                else:
                    # Обратная совместимость со старым форматом (просто строка)
                    row_data.append(str(option))
        
        # Добавляем новый вопрос
        logger.data_processing("таблицы", f"Отправляем в таблицу строку", 
                             details={"данные": row_data})
        
        # Используем декоратор для безопасного API-вызова
        @safe_api_call
        def append_row():
            return questions_sheet.append_row(row_data, value_input_option='USER_ENTERED')
        
        append_row()
        
        # Инвалидируем кэш вопросов
        self.invalidate_questions_cache()
        
        # Обновляем структуру других листов
        self.update_sheets_structure()
        
        # После добавления, проверяем структуру
        questions_with_options = self.get_questions_with_options()
        if question in questions_with_options:
            added_options = questions_with_options[question]
            logger.data_processing("таблицы", f"Проверка добавленного вопроса", 
                                 details={"вопрос": question, "варианты": added_options})
            
            # Проверяем структуру вариантов
            for option in added_options:
                if isinstance(option, dict) and "text" in option:
                    option_text = option["text"]
                    
                    # Проверяем наличие sub_options для свободных ответов
                    if "sub_options" in option and isinstance(option["sub_options"], list) and option["sub_options"] == []:
                        logger.data_processing("варианты", f"Вариант сохранен с пустым списком sub_options", 
                                             details={"вариант": option_text, "тип": "свободный ответ"})
                    elif "sub_options" in option and option["sub_options"]:
                        logger.data_processing("варианты", f"Вариант сохранен с подвариантами", 
                                             details={"вариант": option_text, "подварианты": option['sub_options']})
                    else:
                        logger.data_processing("варианты", f"Вариант сохранен как обычный вариант", 
                                             details={"вариант": option_text, "тип": "без подвариантов"})
        
        logger.data_processing("операция", "Вопрос успешно добавлен", 
                             details={"статус": "успех"})
        return True
        
    except Exception as e:
        logger.error("ошибка_при_добавлении_вопроса", e, 
                     details={"модуль": "sheets_questions"})
        return False

def edit_question_text(self, question_index: int, new_text: str) -> bool:
    """Редактирование текста вопроса"""
    try:
        logger.data_processing("вопрос", f"Редактирование текста вопроса", 
                             details={"индекс": question_index, "новый_текст": new_text})
        
        questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
        
        # Проверяем, что индекс - это число
        if not isinstance(question_index, int):
            try:
                question_index = int(question_index)
            except (ValueError, TypeError):
                logger.error("некорректный_индекс_вопроса", f"Индекс вопроса не является числом", 
                           details={"индекс": question_index})
                return False
        
        # Учитываем заголовок
        row_index = question_index + 2  # +1 для индексации с 1, +1 для заголовка
        
        # Обновляем текст вопроса
        questions_sheet.update_cell(row_index, 1, new_text)
        
        # Обновляем структуру других листов
        self.update_sheets_structure()
        
        logger.data_processing("операция", f"Текст вопроса успешно обновлен", 
                             details={"статус": "успех"})
        return True
        
    except Exception as e:
        logger.error("ошибка_при_редактировании_текста_вопроса", e, 
                    details={"модуль": "sheets_questions"})
        return False

def edit_question_options(self, question_index: int, options: list, free_text_prompt: str = None, parent_option_text: str = None) -> bool:
    """Редактирование вариантов ответов для вопроса"""
    # Проверяем валидность индекса вопроса
    if question_index < 0 or question_index >= len(list(self.get_questions_with_options().keys())):
        logger.error("индекс_вопроса_вне_диапазона", f"Индекс вопроса выходит за границы списка", details={"индекс": question_index, "максимум": len(list(self.get_questions_with_options().keys()))-1})
        return False

    try:
        # Получаем таблицу вопросов
        questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
        
        # Получаем текст вопроса из листа
        row = question_index + 2  # +2 для учета заголовка и 0-индексации
        question_text = questions_sheet.cell(row, 1).value
        
        logger.data_processing("вопрос", f"Редактирование вариантов ответов", 
                             details={"индекс": question_index})
        logger.data_processing("варианты", f"Новые варианты ответов", 
                             details={"количество": len(options) if options else 0})

        # Проверка на добавление free_text_prompt через дополнительные параметры
        if free_text_prompt and parent_option_text:
            logger.data_processing("варианты", f"Обнаружены дополнительные параметры", 
                                details={"free_text_prompt": free_text_prompt, "parent_option_text": parent_option_text})
            
            # Найдем нужный вариант в списке опций
            target_option = None
            for opt in options:
                if isinstance(opt, dict) and "text" in opt and opt["text"] == parent_option_text:
                    target_option = opt
                    break
            
            if target_option:
                # Проверяем, соответствует ли формат свободного ввода
                if "sub_options" in target_option and isinstance(target_option["sub_options"], list) and target_option["sub_options"] == []:
                    # Формируем строку для сохранения с подсказкой
                    options_str = f"{parent_option_text}::prompt={free_text_prompt}"
                    logger.data_processing("варианты", f"Сохраняем вариант со свободным ответом и подсказкой", 
                                        details={"вариант": parent_option_text, "подсказка": free_text_prompt})
                    
                    # Сохраняем в ячейку
                    questions_sheet.update_cell(row, 2, options_str)
                    
                    # Обновляем структуру листов после редактирования
                    self.update_sheets_structure()
                    
                    # Проверяем, что подсказка была сохранена
                    current_cell_value = questions_sheet.cell(row, 2).value
                    if "prompt=" in current_cell_value:
                        logger.data_processing("варианты", f"Подсказка для свободного ответа успешно сохранена", 
                                            details={"подсказка": free_text_prompt, "результат": current_cell_value})
                        return True
                    else:
                        # Подсказка не сохранилась в формате prompt=, пробуем альтернативный формат
                        options_str = f"{parent_option_text}::{free_text_prompt}"
                        logger.data_processing("варианты", f"Пробуем альтернативный формат", 
                                            details={"формат": options_str})
                        questions_sheet.update_cell(row, 2, options_str)
                        return True
                else:
                    logger.data_processing("варианты", f"Вариант не соответствует формату свободного ответа", 
                                         details={"вариант": parent_option_text})
            else:
                logger.data_processing("варианты", f"Вариант не найден в списке опций", 
                                     details={"вариант": parent_option_text})

        # Стандартная обработка без free_text_prompt
        # Преобразуем варианты ответов в строку для сохранения в ячейке
        options_str = ""
        for opt in options:
            if isinstance(opt, dict) and "text" in opt:
                if "sub_options" in opt and isinstance(opt["sub_options"], list):
                    if opt["sub_options"]:  # Непустой список подвариантов
                        # Формат: "вариант::подвариант1,подвариант2,..."
                        sub_options_str = ",".join(opt["sub_options"])
                        logger.data_processing("варианты", f"Сохраняем вариант с подвариантами", 
                                           details={"вариант": opt['text'], "подварианты": opt['sub_options']})
                        options_str = f"{opt['text']}::{sub_options_str}"
                    else:  # Пустой список подвариантов (свободный ответ)
                        # Проверяем, есть ли подсказка для свободного ввода
                        if "free_text_prompt" in opt:
                            logger.data_processing("варианты", f"Сохраняем вариант со свободным ответом и подсказкой", 
                                                details={"вариант": opt['text'], "подсказка": opt['free_text_prompt']})
                            options_str = f"{opt['text']}::prompt={opt['free_text_prompt']}"
                        else:
                            logger.data_processing("варианты", f"Сохраняем вариант со свободным ответом", 
                                                details={"вариант": opt['text'], "тип": "пустой список sub_options"})
                            options_str = f"{opt['text']}::"
                else:
                    # Обычный вариант без подвариантов
                    logger.data_processing("варианты", f"Сохраняем вариант без подвариантов", 
                                        details={"вариант": opt['text']})
                    options_str = opt["text"]
            else:
                # Для обратной совместимости
                options_str = str(opt)
            
            # Сохраняем в ячейку
            questions_sheet.update_cell(row, 2, options_str)

        # Обновляем структуру листов после редактирования
        self.update_sheets_structure()
        
        # Проверяем, что редактирование прошло успешно
        updated_questions = self.get_questions_with_options()
        for q, opts in updated_questions.items():
            if q == question_text:
                for i, opt in enumerate(opts):
                    if isinstance(opt, dict) and "text" in opt and i < len(options) and isinstance(options[i], dict) and "text" in options[i] and opt["text"] == options[i]["text"]:
                        # Проверяем сохранение подвариантов
                        if "sub_options" in options[i] and isinstance(options[i]["sub_options"], list):
                            if options[i]["sub_options"]:  # Непустой список подвариантов
                                if "sub_options" in opt and opt["sub_options"] == options[i]["sub_options"]:
                                    logger.data_processing("варианты", f"✅ Вариант '{opt['text']}' сохранил подварианты: {opt['sub_options']}", 
                                                        details={"действие": "операция"})
                                else:
                                    logger.data_processing(f"Вариант не сохранил подварианты", 
                                                        details={"вариант": opt['text'], "подварианты": f"{opt.get('sub_options')}"},
                                                        type="missing_sub_options")
                            else:  # Пустой список подвариантов (свободный ответ)
                                if "sub_options" in opt and opt["sub_options"] == []:
                                    if "free_text_prompt" in options[i] and "free_text_prompt" in opt:
                                        if opt["free_text_prompt"] == options[i]["free_text_prompt"]:
                                            logger.data_processing("варианты", f"✅ Вариант '{opt['text']}' сохранил ПУСТОЙ список sub_options и free_text_prompt: '{opt['free_text_prompt']}'", 
                                                                details={"действие": "операция"})
                                        else:
                                            logger.data_processing(f"Изменен текст подсказки для свободного ответа", 
                                                                details={"вариант": opt['text'], 
                                                                         "новый_текст": opt['free_text_prompt'], 
                                                                         "старый_текст": options[i]['free_text_prompt']},
                                                                type="prompt_text_changed")
                                    else:
                                        logger.data_processing("варианты", f"✅ Вариант '{opt['text']}' сохранил ПУСТОЙ список sub_options (свободный ответ)", 
                                                            details={"действие": "операция"})
                                else:
                                    logger.data_processing(f"Вариант не сохранил пустой список sub_options", 
                                                       details={"вариант": opt['text'], "подварианты": f"{opt.get('sub_options')}"},
                                                       type="missing_empty_sub_options")
                        break
                break
        
        logger.data_processing("варианты", f"Варианты ответов для вопроса успешно обновлены", 
                             details={"статус": "успех"})
        return True
        
    except Exception as e:
        logger.error("ошибка_при_редактировании_вариантов_ответов", e, 
                     details={"модуль": "sheets_questions"})
        return False

def edit_question_options_with_free_text(self, question_index: int, option_text: str, free_text_prompt: str) -> bool:
    """Редактирование вариантов ответов для вопроса с добавлением подсказки для свободного ввода"""
    # Проверяем валидность индекса вопроса
    questions = self.get_questions_with_options()
    questions_list = list(questions.keys())
    
    if question_index < 0 or question_index >= len(questions_list):
        logger.error("индекс_вопроса_вне_диапазона", f"Индекс вопроса выходит за границы списка", details={"индекс": question_index, "максимум": len(questions_list)-1})
        return False

    try:
        logger.data_processing("редактирование", f"Редактирование вариантов ответов для вопроса с индексом {question_index}", 
                             details={"действие": "операция"})
        logger.data_processing("варианты", f"Вариант: '{option_text}', подсказка: '{free_text_prompt}'", 
                             details={"действие": "операция"})
        
        # Получаем вопрос по индексу
        question = questions_list[question_index]
        options = questions[question]
        
        # Детальное логирование для отладки
        logger.data_processing("таблицы", f"Вопрос: '{question}'", 
                             details={"действие": "операция"})
        logger.data_processing("таблицы", f"Текущие варианты ответов: {options}", 
                             details={"действие": "операция"})
        
        # Находим опцию, которую нужно изменить
        option_found = False
        for i, opt in enumerate(options):
            if isinstance(opt, dict) and "text" in opt:
                # Проверяем точное совпадение и нечувствительное к регистру
                if opt["text"] == option_text or opt["text"].lower() == option_text.lower():
                    # Это наша опция
                    options[i]["sub_options"] = []  # Пустой список для свободного ввода
                    options[i]["free_text_prompt"] = free_text_prompt
                    option_text = opt["text"]  # Используем точный текст из опции
                    option_found = True
                    logger.data_processing("таблицы", f"Найден вариант '{option_text}' на позиции {i}, добавлена подсказка '{free_text_prompt}'", 
                                         details={"действие": "операция"})
                    break
        
        # Если опция не найдена, проверяем варианты с другой структурой в таблице
        if not option_found:
            # Получаем напрямую данные из таблицы для проверки
            questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
            row_index = question_index + 2  # +2 для учета заголовка и индексации с 0
            row_data = questions_sheet.row_values(row_index)
            
            logger.data_processing("таблицы", f"Данные строки из таблицы: {row_data}", 
                                 details={"действие": "операция"})
            
            # Проверяем каждую ячейку, начиная со второй (варианты ответов)
            for col_index, cell_value in enumerate(row_data[1:], start=2):
                if option_text in cell_value:
                    logger.data_processing("таблицы", f"Найден вариант '{option_text}' в ячейке {col_index} со значением '{cell_value}'", 
                                         details={"действие": "операция"})
                    
                    # Форматируем строку с подсказкой для свободного ввода
                    formatted_value = f"{option_text}::prompt={free_text_prompt}"
                    
                    # Обновляем ячейку
                    questions_sheet.update_cell(row_index, col_index, formatted_value)
                    logger.data_processing("таблицы", f"Обновлена ячейка {row_index}:{col_index} со значением '{formatted_value}'", 
                                         details={"действие": "операция"})
                    
                    option_found = True
                    
                    # Инвалидируем кэш и обновляем структуру листов
                    self.invalidate_questions_cache()
                    self.update_sheets_structure()
                    return True
            
            # Если опция всё ещё не найдена, возможно она в другом формате
            if not option_found:
                logger.error("вариант_не_найден", f"Вариант не найден ни в кэше, ни в таблице", details={"вариант": option_text, "вопрос": question})
                
                # Попробуем получить варианты снова и сравнить
                self.invalidate_questions_cache()
                refreshed_questions = self.get_questions_with_options()
                if question in refreshed_questions:
                    refreshed_options = refreshed_questions[question]
                    logger.data_processing("таблицы", f"Обновлённые варианты ответов: {refreshed_options}", 
                                         details={"действие": "операция"})
                    
                    # Ищем в обновлённых вариантах
                    for i, opt in enumerate(refreshed_options):
                        if isinstance(opt, dict) and "text" in opt:
                            if opt["text"] == option_text or opt["text"].lower() == option_text.lower():
                                logger.data_processing("таблицы", f"Найден вариант '{option_text}' после обновления кэша", 
                                                     details={"действие": "операция"})
                                option_found = True
                                
                                # Обновляем вариант
                                questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
                                # Находим колонку с этим вариантом
                                row_data = questions_sheet.row_values(row_index)
                                for col_index, cell_value in enumerate(row_data[1:], start=2):
                                    if opt["text"] in cell_value:
                                        # Форматируем строку с подсказкой для свободного ввода
                                        formatted_value = f"{opt['text']}::prompt={free_text_prompt}"
                                        # Обновляем ячейку
                                        questions_sheet.update_cell(row_index, col_index, formatted_value)
                                        logger.data_processing("таблицы", f"Обновлена ячейка {row_index}:{col_index} со значением '{formatted_value}'", 
                                                             details={"действие": "операция"})
                                        break
                                
                                # Инвалидируем кэш и обновляем структуру листов
                                self.invalidate_questions_cache()
                                self.update_sheets_structure()
                                return True
                
                return False
        
        # Сохраняем обновленные варианты в случае, если опция найдена через обычные методы
        @safe_api_call
        def update_options():
            questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
            # Учитываем заголовок (+2)
            row = question_index + 2
            
            # Преобразуем все варианты в строковый формат для таблицы
            formatted_options = []
            for opt in options:
                if isinstance(opt, dict) and "text" in opt:
                    opt_text = opt["text"]
                    
                    # Вариант с пустым списком sub_options и free_text_prompt
                    if "sub_options" in opt and isinstance(opt["sub_options"], list) and opt["sub_options"] == []:
                        if "free_text_prompt" in opt and opt["free_text_prompt"]:
                            # Формат с подсказкой для свободного ввода
                            formatted_opt = f"{opt_text}::prompt={opt['free_text_prompt']}"
                            logger.data_processing("варианты", f"Форматирован вариант со свободным вводом и подсказкой: '{formatted_opt}'", 
                                                 details={"действие": "операция"})
                        else:
                            # Простой свободный ввод без подсказки
                            formatted_opt = f"{opt_text}::"
                            logger.data_processing("варианты", f"Форматирован вариант со свободным вводом без подсказки: '{formatted_opt}'", 
                                                 details={"действие": "операция"})
                    # Вариант с подвариантами
                    elif "sub_options" in opt and opt["sub_options"]:
                        sub_options_str = ";".join(opt["sub_options"])
                        formatted_opt = f"{opt_text}::{sub_options_str}"
                        logger.data_processing("варианты", f"Форматирован вариант с подвариантами: '{formatted_opt}'", 
                                             details={"действие": "операция"})
                    else:
                        # Обычный вариант
                        formatted_opt = opt_text
                        logger.data_processing("варианты", f"Форматирован обычный вариант: '{formatted_opt}'", 
                                             details={"действие": "операция"})
                    
                    formatted_options.append(formatted_opt)
                else:
                    # Обратная совместимость
                    formatted_options.append(str(opt))
            
            # Сначала получаем текущее значение ячейки с вопросом
            question_text = questions_sheet.cell(row, 1).value
            
            # Создаем массив для обновления всей строки
            row_data = [question_text] + formatted_options
            logger.data_processing("таблицы", f"Данные для обновления строки: {row_data}", 
                                 details={"действие": "операция"})
            
            # Обновляем всю строку за один запрос вместо множества cell update
            last_col = chr(65 + len(row_data) - 1)  # Последняя колонка (A, B, C, ...)
            range_name = f'A{row}:{last_col}{row}'
            questions_sheet.update(range_name, [row_data])
            logger.data_processing("таблицы", f"Обновлён диапазон {range_name}", 
                                 details={"действие": "операция"})
            
            return True
        
        success = update_options()
        
        if success:
            # Инвалидируем кэш вопросов
            self.invalidate_questions_cache()
            
            # Обновляем структуру других листов
            self.update_sheets_structure()
            
            # Проверяем сохранение
            updated_questions = self.get_questions_with_options()
            if question in updated_questions:
                updated_options = updated_questions[question]
                for opt in updated_options:
                    if isinstance(opt, dict) and "text" in opt and opt["text"] == option_text:
                        if "sub_options" in opt and isinstance(opt["sub_options"], list) and opt["sub_options"] == []:
                            if "free_text_prompt" in opt and opt["free_text_prompt"] == free_text_prompt:
                                logger.data_processing("варианты", f"✅ Вариант '{option_text}' успешно обновлен с подсказкой для свободного ввода: '{free_text_prompt}'", 
                                                        details={"действие": "операция"})
                                return True
            
            logger.data_processing(f"Не удалось проверить сохранение подсказки", 
                                details={"вариант": option_text}, 
                                type="prompt_verification_failed")
            return True  # Считаем, что обновление прошло успешно, даже если не удалось проверить
            
        else:
            logger.error("обновление_вариантов_не_удалось", f"Не удалось обновить варианты ответов", details={"вопрос": question})
            return False
        
    except Exception as e:
        logger.error("ошибка_при_редактировании_вариантов_ответов_с_подсказкой", e, 
                     details={"модуль": "sheets_questions"})
        return False

def delete_question(self, question_or_index) -> bool:
    """Удаление вопроса из таблицы
    
    Args:
        question_or_index: Индекс вопроса (число) или текст вопроса (строка)
        
    Returns:
        bool: True если удаление прошло успешно, False в случае ошибки
    """
    try:
        logger.data_processing("таблицы", f"Запрос на удаление вопроса: {question_or_index}", 
                             details={"действие": "операция"})
        
        questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
        all_questions = questions_sheet.col_values(1)
        
        # Пропускаем заголовок
        all_questions = all_questions[1:]
        
        # Определяем индекс вопроса в зависимости от типа переданного параметра
        if isinstance(question_or_index, int):
            # Если передан индекс
            question_index = question_or_index
            logger.data_processing("таблицы", f"Получен числовой индекс вопроса: {question_index}", 
                                 details={"действие": "операция"})
            
            # Проверяем, что индекс находится в допустимом диапазоне
            if question_index < 0 or question_index >= len(all_questions):
                logger.error("индекс_вопроса_вне_диапазона", f"Индекс вопроса выходит за границы списка", details={"индекс": question_index, "максимум": len(all_questions)-1})
                return False
        else:
            # Если передан текст вопроса
            try:
                question_index = all_questions.index(question_or_index)
                logger.data_processing("таблицы", f"Найден вопрос по тексту: {question_or_index}, индекс: {question_index}", 
                                     details={"действие": "операция"})
            except ValueError:
                logger.error("вопрос_не_найден", question_or_index, 
                             details={"модуль": "sheets_questions"})
                return False
        
        # Учитываем заголовок при удалении строки (индексация с 1 в таблице)
        row_index = question_index + 2  # +1 для индексации с 1, +1 для заголовка
        
        # Удаляем строку
        questions_sheet.delete_rows(row_index)
        
        # Обновляем структуру других листов
        self.update_sheets_structure()
        
        logger.data_processing("успех", f"Вопрос успешно удален: {question_or_index}", 
                             details={"действие": "операция"})
        return True
        
    except Exception as e:
        logger.error("ошибка_при_удалении_вопроса", e, 
                     details={"модуль": "sheets_questions"})
        return False

def clear_answers_and_stats(self) -> bool:
    """Очистка таблиц с ответами и статистикой"""
    try:
        logger.data_processing("таблицы", "Начало очистки таблиц с ответами и статистикой", 
                             details={"действие": "операция"})
        
        # Очищаем таблицу ответов
        answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
        # Получаем все значения для определения диапазона данных
        all_values = answers_sheet.get_all_values()
        if len(all_values) > 1:  # Если есть данные кроме заголовка
            # Очищаем все строки кроме заголовка
            answers_sheet.batch_clear([f"A2:Z{len(all_values)}"])
        
        # Очищаем таблицу статистики
        stats_sheet = self.sheet.worksheet(self.STATS_SHEET)
        all_values = stats_sheet.get_all_values()
        if len(all_values) > 1:
            stats_sheet.batch_clear([f"A2:Z{len(all_values)}"])
        
        logger.data_processing("очистка", "Таблицы успешно очищены", 
                             details={"действие": "операция"})
        return True
        
    except Exception as e:
        logger.error("ошибка_при_очистке_таблиц", e, 
                     details={"модуль": "sheets_questions"})
        return False

async def get_admin_info(self, user_id: int) -> str:
    """Получение информации о пользователе Telegram по ID"""
    try:
        from telegram import Bot
        from telegram.error import TimedOut, NetworkError, Forbidden, BadRequest
        from config import BOT_TOKEN
        
        bot = Bot(BOT_TOKEN)
        user = await bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else "нет username"
        full_name = user.full_name
        return f"{full_name} ({username})"
    except TimedOut as e:
        logger.warning(f"Тайм-аут при получении информации о пользователе (timeout_get_user_info)", 
                     details={"user_id": user_id, "причина": "Превышено время ожидания ответа от API Telegram"})
        return f"ID: {user_id} (тайм-аут запроса)"
    except NetworkError as e:
        logger.warning(f"Сетевая ошибка при получении информации о пользователе (network_get_user_info)", 
                     details={"user_id": user_id, "причина": str(e)})
        return f"ID: {user_id} (ошибка сети)"
    except (Forbidden, BadRequest) as e:
        logger.warning(f"Ошибка доступа при получении информации о пользователе (access_get_user_info)", 
                     details={"user_id": user_id, "причина": str(e)})
        return f"ID: {user_id} (недоступен)"
    except Exception as e:
        logger.error("ошибка_при_получении_информации_о_пользователе_user_id", e, 
                     details={"user_id": user_id, "модуль": "sheets_questions"})
        return f"ID: {user_id} (ошибка запроса)"

def add_admin(self, admin_id: int, admin_name: str, admin_description: str) -> bool:
    """Добавление нового администратора"""
    try:
        logger.data_processing("таблицы", f"Добавление нового администратора: {admin_id}", 
                             details={"действие": "операция"})
        admins_sheet = self.sheet.worksheet(self.ADMINS_SHEET)
        
        # Получаем текущий список администраторов
        admins = admins_sheet.get_all_values()
        
        # Проверяем, есть ли уже такой администратор
        if str(admin_id) in [admin[0] for admin in admins]:
            logger.data_processing(f"Администратор уже существует", 
                                 details={"admin_id": admin_id}, 
                                 type="admin_already_exists")
            return False
        
        # Добавляем нового админа
        admins_sheet.append_row([str(admin_id), admin_name, admin_description])
        logger.data_processing("успех", f"Администратор {admin_id} успешно добавлен", 
                                details={"действие": "операция"})
        return True
        
    except Exception as e:
        logger.error("ошибка_при_добавлении_администратора", e, 
                     details={"admin_id": admin_id, "модуль": "sheets_questions"})
        return False

def remove_admin(self, admin_id: int) -> bool:
    """Удаление администратора"""
    try:
        logger.data_processing("таблицы", f"Удаление администратора: {admin_id}", 
                             details={"действие": "операция"})
        admins_sheet = self.sheet.worksheet(self.ADMINS_SHEET)
        
        # Получаем все ID админов
        admin_cells = admins_sheet.col_values(1)
        
        # Проверяем наличие администратора
        if str(admin_id) not in [admin[0] for admin in admins_sheet.get_all_values()]:
            logger.data_processing(f"Администратор не найден", 
                                 details={"admin_id": admin_id}, 
                                 type="admin_not_found")
            return False
        
        # Удаляем строку
        admins_sheet.delete_rows(admin_cells.index(str(admin_id)) + 1)
        logger.data_processing("успех", f"Администратор {admin_id} успешно удален", 
                                details={"действие": "операция"})
        return True
        
    except Exception as e:
        logger.error("ошибка_при_удалении_администратора", e, 
                     details={"admin_id": admin_id, "модуль": "sheets_questions"})
        return False

async def get_admins_list(self) -> list:
    """Получение списка всех администраторов с информацией"""
    try:
        from telegram.error import TimedOut, NetworkError
        
        admins_sheet = self.sheet.worksheet(self.ADMINS_SHEET)
        admin_ids = [int(id) for id in admins_sheet.col_values(1)[1:]]  # Пропускаем заголовок
        
        admin_info = []
        for admin_id in admin_ids:
            try:
                info = await self.get_admin_info(admin_id)
                admin_info.append((admin_id, info))
            except (TimedOut, NetworkError) as e:
                # Обрабатываем тайм-аут для конкретного администратора, но продолжаем обработку остальных
                logger.warning(f"Тайм-аут при получении информации об админе (timeout_get_admin)", 
                            details={"admin_id": admin_id, "причина": str(e)})
                admin_info.append((admin_id, f"ID: {admin_id} (недоступен)"))
            except Exception as e:
                # Обрабатываем другие ошибки для конкретного администратора
                logger.error("ошибка_при_получении_информации_об_админе", e, 
                            details={"admin_id": admin_id, "модуль": "sheets_questions"})
                admin_info.append((admin_id, f"ID: {admin_id} (ошибка запроса)"))
        
        return admin_info
        
    except Exception as e:
        logger.error("ошибка_при_получении_списка_администраторов", e, 
                     details={"модуль": "sheets_questions"})
        return []

def update_sheets_structure(self) -> bool:
    """Обновление структуры листов ответов и статистики в соответствии с текущими вопросами"""
    try:
        logger.data_processing("таблицы", "Обновление структуры листов", 
                             details={"действие": "операция"})
        
        # Получаем текущие вопросы и логируем их структуру перед обновлением
        questions = self.get_questions_with_options()
        logger.data_processing("таблицы", f"Получены вопросы для обновления структуры: {len(questions)}", 
                             details={"действие": "операция"})
        
        # Логируем варианты с пустыми списками sub_options и free_text_prompt
        for question, options in questions.items():
            for opt in options:
                if isinstance(opt, dict) and "text" in opt and "sub_options" in opt:
                    if isinstance(opt["sub_options"], list) and not opt["sub_options"]:
                        if "free_text_prompt" in opt:
                            logger.data_processing("варианты", f"🔄 В вопросе '{question}' вариант '{opt['text']}' имеет пустой список sub_options и free_text_prompt: '{opt['free_text_prompt']}'", 
                                                 details={"действие": "операция"})
                        else:
                            logger.data_processing("варианты", f"🔄 В вопросе '{question}' вариант '{opt['text']}' имеет пустой список sub_options (свободный ответ)", 
                                                 details={"действие": "операция"})
        
        # Сохраняем текущие данные вопросов, чтобы восстановить free_text_prompt после обновления структуры
        original_questions = {}
        for question, options in questions.items():
            original_options = []
            for opt in options:
                if isinstance(opt, dict) and "text" in opt:
                    opt_copy = opt.copy()  # Создаем копию опции
                    original_options.append(opt_copy)
                else:
                    original_options.append(opt)
            original_questions[question] = original_options
        
        question_texts = list(questions.keys())
        
        # Обновляем лист ответов
        answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
        # Формируем заголовки: Timestamp, User ID, все вопросы
        new_headers = ['Timestamp', 'User ID'] + question_texts
        
        # Получаем текущие данные
        existing_data = answers_sheet.get_all_values()
        if len(existing_data) > 0:
            # Сохраняем все строки кроме заголовка
            existing_rows = existing_data[1:] if len(existing_data) > 1 else []
            
            # Обновляем только первую строку (заголовки)
            answers_sheet.update('A1', [new_headers])
            
            # Если есть существующие данные, обновляем их формат
            if existing_rows:
                # Расширяем существующие строки до новой длины заголовков
                updated_rows = []
                for row in existing_rows:
                    # Если строка короче новых заголовков, добавляем пустые значения
                    if len(row) < len(new_headers):
                        row.extend([''] * (len(new_headers) - len(row)))
                    # Если строка длиннее, обрезаем
                    elif len(row) > len(new_headers):
                        row = row[:len(new_headers)]
                    updated_rows.append(row)
                
                # Обновляем данные, начиная со второй строки
                if updated_rows:
                    answers_sheet.update(f'A2:${chr(65+len(new_headers)-1)}{len(updated_rows)+1}', 
                                      updated_rows)
        else:
            # Если лист пустой, просто добавляем заголовки
            answers_sheet.update('A1', [new_headers])
        
        # Обновляем лист статистики
        stats_sheet = self.sheet.worksheet(self.STATS_SHEET)
        stats_data = []
        
        # Добавляем заголовки
        headers = ['Вопрос', 'Вариант ответа', 'Количество']
        stats_data.append(headers)
        
        # Для каждого вопроса с вариантами ответов
        for question, options in questions.items():
            if options:  # Только для вопросов с вариантами ответов
                for option in options:
                    if isinstance(option, dict) and "text" in option:
                        # Добавляем основной вариант
                        stats_data.append([question, option["text"], '0'])
                        
                        # Проверяем на свободный ответ (пустой список sub_options)
                        if "sub_options" in option and isinstance(option["sub_options"], list) and option["sub_options"] == []:
                            # Это свободный ответ - логируем для отладки
                            if "free_text_prompt" in option:
                                logger.data_processing("варианты", f"🆓 Обработка свободного ответа для варианта '{option['text']}' в update_sheets_structure с free_text_prompt: '{option['free_text_prompt']}'", 
                                                    details={"действие": "операция"})
                            else:
                                logger.data_processing("варианты", f"🆓 Обработка свободного ответа для варианта '{option['text']}' в update_sheets_structure", 
                                                    details={"действие": "операция"})
                            # Для свободных ответов не добавляем подварианты в статистику
                        # Обрабатываем вложенные варианты, если они есть и не пустые
                        elif "sub_options" in option and option["sub_options"]:
                            for sub_option in option["sub_options"]:
                                # Добавляем вложенный вариант с отступом
                                stats_data.append([question, f"  └ {sub_option}", '0'])
                    else:
                        # Для обратной совместимости со старым форматом
                        stats_data.append([question, option, '0'])
        
        # Обновляем весь лист статистики
        if stats_data:
            stats_sheet.clear()  # Очищаем текущие данные
            stats_sheet.update('A1', stats_data)  # Добавляем новые данные
        else:
            # Если нет вопросов с вариантами, оставляем только заголовки
            stats_sheet.update('A1', [['Вопрос', 'Вариант ответа', 'Количество']])
        
        # Повторно получаем вопросы для проверки сохранения структуры
        updated_questions = self.get_questions_with_options()
        logger.data_processing("таблицы", f"После обновления структуры получено {len(updated_questions)} вопросов", 
                             details={"действие": "операция"})
        
        # Проверяем сохранение вариантов с пустыми списками sub_options и free_text_prompt после обновления
        questions_sheet = self.sheet.worksheet(self.QUESTIONS_SHEET)
        
        # Проверяем строки для восстановления free_text_prompt если необходимо
        for i, (question, options) in enumerate(original_questions.items(), start=1):
            # Ищем соответствующий вопрос в обновленной структуре
            if question in updated_questions:
                updated_options = updated_questions[question]
                
                # Построим словарь опций с free_text_prompt из оригинальных данных
                original_prompts = {}
                for opt in options:
                    if isinstance(opt, dict) and "text" in opt and "free_text_prompt" in opt:
                        original_prompts[opt["text"]] = opt["free_text_prompt"]
                
                # Проверим, сохранились ли free_text_prompt в обновленных опциях
                for j, opt in enumerate(updated_options):
                    if isinstance(opt, dict) and "text" in opt and opt["text"] in original_prompts:
                        if "free_text_prompt" not in opt:
                            # Если у опции есть свободный ответ, но утерян free_text_prompt, пробуем восстановить
                            logger.data_processing(f"Восстановление утерянного free_text_prompt", 
                                                 details={"вопрос": question, "вариант": opt['text']}, 
                                                 type="restore_free_text_prompt")
                            opt["free_text_prompt"] = original_prompts[opt["text"]]
                        else:
                            # free_text_prompt сохранился, проверяем совпадение значений
                            if opt["free_text_prompt"] != original_prompts[opt["text"]]:
                                logger.data_processing(f"⚠️ Для варианта '{opt['text']}' значение free_text_prompt изменилось: '{opt['free_text_prompt']}' (было '{original_prompts[opt['text']]}')")
                
        # Проверяем сохранение структуры после всех модификаций
        for question, options in updated_questions.items():
            for opt in options:
                if isinstance(opt, dict) and "text" in opt and "sub_options" in opt:
                    if isinstance(opt["sub_options"], list) and not opt["sub_options"]:
                        if "free_text_prompt" in opt:
                            logger.data_processing("варианты", f"✅ После обновления структуры в вопросе '{question}' вариант '{opt['text']}' сохранил пустой список sub_options и free_text_prompt: '{opt['free_text_prompt']}'", 
                                                 details={"действие": "операция"})
                        else:
                            logger.data_processing("варианты", f"✅ После обновления структуры в вопросе '{question}' вариант '{opt['text']}' сохранил пустой список sub_options (свободный ответ)", 
                                                 details={"действие": "операция"})
        
        logger.data_processing("успех", "Структура листов успешно обновлена с сохранением существующих данных", 
                                        details={"действие": "операция"})
        return True
        
    except Exception as e:
        logger.error("ошибка_при_обновлении_структуры_листов", str(e), 
                     details={"модуль": "sheets_questions"})
        return False

def has_user_completed_survey(self, user_id: int) -> bool:
    """Проверка, проходил ли пользователь опрос"""
    try:
        answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
        # Получаем столбец с ID пользователей
        user_ids = answers_sheet.col_values(2)[1:]  # Пропускаем заголовок
        # Проверяем, есть ли ID пользователя в списке
        return str(user_id) in user_ids
    except Exception as e:
        logger.error("ошибка_при_проверке_завершения_опроса", e, 
                     details={"user_id": user_id, "модуль": "sheets_questions"})
        return False

def reset_user_survey(self, user_id: int) -> bool:
    """Удаление ответов конкретного пользователя"""
    try:
        answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
        # Получаем все данные
        all_values = answers_sheet.get_all_values()
        if len(all_values) <= 1:  # Только заголовок или пустой лист
            return True
            
        # Ищем строки с ответами пользователя
        headers = all_values[0]
        rows_to_delete = []
        
        # Собираем ответы пользователя для обновления статистики
        user_answers = []
        
        for i, row in enumerate(all_values[1:], start=2):  # start=2 для учета реальных номеров строк
            if row[1] == str(user_id):  # Проверяем ID пользователя (второй столбец)
                rows_to_delete.append(i)
                user_answers = row[2:]  # Сохраняем ответы пользователя (начиная с 3-го столбца)
        
        if not rows_to_delete:
            return True  # Нет ответов для удаления
            
        # Удаляем строки в обратном порядке, чтобы не нарушить индексацию
        for row_index in sorted(rows_to_delete, reverse=True):
            answers_sheet.delete_rows(row_index)
            
        # Обновляем статистику
        stats_sheet = self.sheet.worksheet(self.STATS_SHEET)
        questions = headers[2:]  # Получаем список вопросов
        questions_with_options = self.get_questions_with_options()
        
        # Получаем текущую статистику
        stats_data = stats_sheet.get_all_values()
        if len(stats_data) > 1:  # Есть данные кроме заголовка
            for q_idx, (question, answer) in enumerate(zip(questions, user_answers)):
                if question in questions_with_options and questions_with_options[question]:
                    # Ищем строку с соответствующим вопросом и ответом
                    for row_idx, row in enumerate(stats_data[1:], start=2):
                        if row[0] == question and row[1] == answer:
                            # Уменьшаем счетчик
                            current_count = int(row[2])
                            if current_count > 0:
                                stats_sheet.update_cell(row_idx, 3, str(current_count - 1))
                            break
        
        logger.data_processing("успех", f"Ответы пользователя {user_id} успешно удалены и статистика обновлена", 
                                        details={"действие": "операция"})
        return True
        
    except Exception as e:
        logger.error("ошибка_при_удалении_ответов_пользователя", e, 
                     details={"user_id": user_id, "модуль": "sheets_questions"})
        return False

def get_total_surveys_count(self) -> int:
    """Получение общего количества пройденных опросов"""
    try:
        answers_sheet = self.sheet.worksheet(self.ANSWERS_SHEET)
        # Получаем все значения из листа ответов
        all_values = answers_sheet.get_all_values()
        # Вычитаем 1 для учета заголовка
        return len(all_values) - 1 if len(all_values) > 1 else 0
    except Exception as e:
        logger.error("ошибка_при_подсчете_общего_количества_опросов", e, 
                     details={"модуль": "sheets_questions"})
        return 0

# Добавляем методы в класс GoogleSheets
GoogleSheets.add_question = add_question
GoogleSheets.edit_question_text = edit_question_text
GoogleSheets.edit_question_options = edit_question_options
GoogleSheets.edit_question_options_with_free_text = edit_question_options_with_free_text
GoogleSheets.delete_question = delete_question
GoogleSheets.clear_answers_and_stats = clear_answers_and_stats
GoogleSheets.add_admin = add_admin
GoogleSheets.remove_admin = remove_admin
GoogleSheets.get_admins_list = get_admins_list
GoogleSheets.get_admin_info = get_admin_info
GoogleSheets.update_sheets_structure = update_sheets_structure
GoogleSheets.has_user_completed_survey = has_user_completed_survey
GoogleSheets.reset_user_survey = reset_user_survey
GoogleSheets.get_total_surveys_count = get_total_surveys_count