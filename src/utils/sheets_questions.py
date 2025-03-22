"""
Методы для работы с вопросами в Google Sheets
"""

import logging
from utils.sheets import GoogleSheets
from config import QUESTIONS_SHEET, ANSWERS_SHEET, STATS_SHEET, ADMINS_SHEET

# Настройка логирования
logger = logging.getLogger(__name__)

# Добавляем методы в класс GoogleSheets
def add_question(self, question: str, options: list = None) -> bool:
    """Добавление нового вопроса в таблицу"""
    try:
        logger.info(f"Добавление нового вопроса: {question}")
        logger.info(f"Варианты ответов: {options}")
        
        questions_sheet = self.sheet.worksheet(QUESTIONS_SHEET)
        
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
                                logger.info(f"Вариант '{option_text}' с подвариантами: {option['sub_options']}")
                            elif len(option["sub_options"]) == 0:
                                # Пустой список подвариантов - свободный ответ
                                option_for_sheet = f"{option_text}::"
                                logger.info(f"Вариант '{option_text}' со свободным ответом (пустой список sub_options)")
                        else:
                            logger.warning(f"Некорректный тип sub_options для '{option_text}': {type(option['sub_options'])}")
                    
                    logger.info(f"Добавляем в строку вариант: '{option_for_sheet}'")
                    row_data.append(option_for_sheet)
                else:
                    # Обратная совместимость со старым форматом (просто строка)
                    row_data.append(option)
        
        # Добавляем новый вопрос
        logger.info(f"Отправляем в таблицу строку: {row_data}")
        questions_sheet.append_row(row_data, value_input_option='USER_ENTERED')
        
        # Обновляем структуру других листов
        self.update_sheets_structure()
        
        # После добавления, проверяем структуру
        questions_with_options = self.get_questions_with_options()
        if question in questions_with_options:
            added_options = questions_with_options[question]
            logger.info(f"Проверка добавленного вопроса '{question}', варианты: {added_options}")
            
            # Проверяем структуру вариантов
            for option in added_options:
                if isinstance(option, dict) and "text" in option:
                    option_text = option["text"]
                    
                    # Проверяем наличие sub_options для свободных ответов
                    if "sub_options" in option and isinstance(option["sub_options"], list) and option["sub_options"] == []:
                        logger.info(f"✅ Вариант '{option_text}' сохранен с пустым списком sub_options (свободный ответ)")
                    elif "sub_options" in option and option["sub_options"]:
                        logger.info(f"✅ Вариант '{option_text}' сохранен с подвариантами: {option['sub_options']}")
                    else:
                        logger.info(f"✅ Вариант '{option_text}' сохранен как обычный вариант без подвариантов")
        
        logger.info("Вопрос успешно добавлен")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении вопроса: {e}")
        return False

def edit_question_text(self, question_index: int, new_text: str) -> bool:
    """Редактирование текста вопроса"""
    try:
        logger.info(f"Редактирование текста вопроса с индексом {question_index}")
        logger.info(f"Новый текст вопроса: {new_text}")
        
        questions_sheet = self.sheet.worksheet(QUESTIONS_SHEET)
        
        # Проверяем, что индекс - это число
        if not isinstance(question_index, int):
            try:
                question_index = int(question_index)
            except (ValueError, TypeError):
                logger.error(f"Некорректный индекс вопроса (не число): {question_index}")
                return False
        
        # Учитываем заголовок
        row_index = question_index + 2  # +1 для индексации с 1, +1 для заголовка
        
        # Обновляем текст вопроса
        questions_sheet.update_cell(row_index, 1, new_text)
        
        # Обновляем структуру других листов
        self.update_sheets_structure()
        
        logger.info(f"Текст вопроса успешно обновлен")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при редактировании текста вопроса: {e}")
        return False

def edit_question_options(self, question_index: int, options: list) -> bool:
    """Редактирование вариантов ответов для вопроса"""
    # Проверяем валидность индекса вопроса
    if question_index < 0 or question_index >= len(list(self.get_questions_with_options().keys())):
        logger.error(f"Ошибка: индекс вопроса {question_index} выходит за границы списка вопросов")
        return False

    try:
        # Получаем таблицу вопросов
        questions_sheet = self.sheet.worksheet(QUESTIONS_SHEET)
        
        # Получаем текст вопроса из листа
        row = question_index + 2  # +2 для учета заголовка и 0-индексации
        question_text = questions_sheet.cell(row, 1).value
        
        logger.info(f"Редактирование вариантов ответов для вопроса с индексом {question_index}")
        logger.info(f"Новые варианты ответов: {options}")

        # Преобразуем варианты ответов в строку для сохранения в ячейке
        options_str = ""
        for opt in options:
            if isinstance(opt, dict) and "text" in opt:
                if "sub_options" in opt and isinstance(opt["sub_options"], list):
                    if opt["sub_options"]:  # Непустой список подвариантов
                        # Формат: "вариант::подвариант1,подвариант2,..."
                        sub_options_str = ",".join(opt["sub_options"])
                        logger.info(f"Сохраняем вариант '{opt['text']}' с подвариантами: {opt['sub_options']}")
                        options_str = f"{opt['text']}::{sub_options_str}"
                    else:  # Пустой список подвариантов (свободный ответ)
                        logger.info(f"Сохраняем вариант '{opt['text']}' со свободным ответом (пустой список sub_options)")
                        options_str = f"{opt['text']}::"
                else:
                    # Обычный вариант без подвариантов
                    logger.info(f"Сохраняем вариант '{opt['text']}' без подвариантов")
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
                    if isinstance(opt, dict) and "text" in opt and opt["text"] == options[0]["text"]:
                        # Проверяем сохранение подвариантов
                        if "sub_options" in options[0] and isinstance(options[0]["sub_options"], list):
                            if options[0]["sub_options"]:  # Непустой список подвариантов
                                if "sub_options" in opt and opt["sub_options"] == options[0]["sub_options"]:
                                    logger.info(f"✅ Вариант '{opt['text']}' сохранил подварианты: {opt['sub_options']}")
                                else:
                                    logger.warning(f"⚠️ Вариант '{opt['text']}' НЕ сохранил подварианты: {opt.get('sub_options')}")
                            else:  # Пустой список подвариантов (свободный ответ)
                                if "sub_options" in opt and opt["sub_options"] == []:
                                    logger.info(f"✅ Вариант '{opt['text']}' сохранил ПУСТОЙ список sub_options (свободный ответ)")
                                else:
                                    logger.warning(f"⚠️ Вариант '{opt['text']}' НЕ сохранил пустой список sub_options: {opt.get('sub_options')}")
                        break
                break
        
        logger.info(f"Варианты ответов для вопроса успешно обновлены")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при редактировании вариантов ответов: {e}")
        logger.exception(e)
        return False

def edit_question_options_with_free_text(self, question_index, options):
    """Редактирование вариантов ответов для вопроса со свободным текстом"""
    # Проверяем валидность индекса вопроса
    if question_index < 0 or question_index >= len(list(self.get_questions_with_options().keys())):
        logger.error(f"Ошибка: индекс вопроса {question_index} выходит за границы списка вопросов")
        return False

    try:
        # Получаем таблицу вопросов
        questions_sheet = self.sheet.worksheet(QUESTIONS_SHEET)
        
        # Получаем текст вопроса из листа
        row = question_index + 2  # +2 для учета заголовка и 0-индексации
        question_text = questions_sheet.cell(row, 1).value
        
        logger.info(f"Редактирование вариантов ответов со свободным текстом для вопроса с индексом {question_index}")
        logger.info(f"Новые варианты ответов: {options}")

        # Убедимся, что есть хотя бы один вариант
        if not options or not isinstance(options[0], dict):
            logger.error(f"Ошибка: некорректный формат вариантов ответов")
            return False
            
        # Получаем первый вариант, который должен содержать free_text_prompt
        main_option = options[0]
        
        # Проверяем, содержит ли вариант free_text_prompt
        if "free_text_prompt" not in main_option:
            logger.warning(f"Вариант не содержит free_text_prompt, используем стандартный метод")
            return self.edit_question_options(question_index, options)
            
        # Извлекаем необходимые данные
        option_text = main_option["text"]
        free_text_prompt = main_option["free_text_prompt"]
        
        # Формируем специальный формат для сохранения free_text_prompt
        if "sub_options" in main_option and isinstance(main_option["sub_options"], list) and main_option["sub_options"] == []:
            # Формат для свободного ответа: "вариант::prompt=текст_подсказки"
            options_str = f"{option_text}::prompt={free_text_prompt}"
            logger.info(f"Сохраняем вариант '{option_text}' со свободным ответом и подсказкой: '{free_text_prompt}'")
        else:
            # Формат некорректный - у варианта со свободным ответом должен быть пустой список sub_options
            logger.warning(f"Некорректный формат варианта для свободного ответа: {main_option}")
            return self.edit_question_options(question_index, options)
            
        # Сохраняем в ячейку
        questions_sheet.update_cell(row, 2, options_str)

        # Обновляем структуру листов после редактирования
        self.update_sheets_structure()
        
        # Проверяем, что подсказка была сохранена
        # Т.к. update_sheets_structure может не поддерживать формат prompt, проверим ячейку напрямую
        cell_value = questions_sheet.cell(row, 2).value
        if "prompt=" in cell_value:
            logger.info(f"✅ Подсказка для свободного ответа '{free_text_prompt}' успешно сохранена: {cell_value}")
            prompt_saved = True
        else:
            logger.warning(f"⚠️ Подсказка для свободного ответа НЕ сохранена: {cell_value}")
            # Пробуем еще раз с другим форматом
            try:
                # Используем формат с тремя двоеточиями
                options_str = f"{option_text}:::{free_text_prompt}"
                logger.info(f"Пробуем альтернативный формат: {options_str}")
                questions_sheet.update_cell(row, 2, options_str)
                
                # Проверяем результат
                cell_value = questions_sheet.cell(row, 2).value
                logger.info(f"Результат сохранения с альтернативным форматом: {cell_value}")
                if ":::" in cell_value:
                    prompt_saved = True
                else:
                    prompt_saved = False
            except Exception as e2:
                logger.error(f"Ошибка при попытке альтернативного сохранения: {e2}")
                prompt_saved = False
        
        logger.info(f"Варианты ответов со свободным текстом для вопроса {'успешно' if prompt_saved else 'НЕ'} обновлены")
        return prompt_saved
        
    except Exception as e:
        logger.error(f"Ошибка при редактировании вариантов ответов со свободным текстом: {e}")
        logger.exception(e)
        return False

def delete_question(self, question_or_index) -> bool:
    """Удаление вопроса из таблицы
    
    Args:
        question_or_index: Индекс вопроса (число) или текст вопроса (строка)
        
    Returns:
        bool: True если удаление прошло успешно, False в случае ошибки
    """
    try:
        logger.info(f"Запрос на удаление вопроса: {question_or_index}")
        
        questions_sheet = self.sheet.worksheet(QUESTIONS_SHEET)
        all_questions = questions_sheet.col_values(1)
        
        # Пропускаем заголовок
        all_questions = all_questions[1:]
        
        # Определяем индекс вопроса в зависимости от типа переданного параметра
        if isinstance(question_or_index, int):
            # Если передан индекс
            question_index = question_or_index
            logger.info(f"Получен числовой индекс вопроса: {question_index}")
            
            # Проверяем, что индекс находится в допустимом диапазоне
            if question_index < 0 or question_index >= len(all_questions):
                logger.error(f"Индекс вопроса {question_index} вне допустимого диапазона (0-{len(all_questions)-1})")
                return False
        else:
            # Если передан текст вопроса
            try:
                question_index = all_questions.index(question_or_index)
                logger.info(f"Найден вопрос по тексту: {question_or_index}, индекс: {question_index}")
            except ValueError:
                logger.error(f"Вопрос не найден: {question_or_index}")
                return False
        
        # Учитываем заголовок при удалении строки (индексация с 1 в таблице)
        row_index = question_index + 2  # +1 для индексации с 1, +1 для заголовка
        
        # Удаляем строку
        questions_sheet.delete_rows(row_index)
        
        # Обновляем структуру других листов
        self.update_sheets_structure()
        
        logger.info(f"Вопрос успешно удален: {question_or_index}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при удалении вопроса: {e}")
        logger.exception(e)
        return False

def clear_answers_and_stats(self) -> bool:
    """Очистка таблиц с ответами и статистикой"""
    try:
        logger.info("Начало очистки таблиц с ответами и статистикой")
        
        # Очищаем таблицу ответов
        answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
        # Получаем все значения для определения диапазона данных
        all_values = answers_sheet.get_all_values()
        if len(all_values) > 1:  # Если есть данные кроме заголовка
            # Очищаем все строки кроме заголовка
            answers_sheet.batch_clear([f"A2:Z{len(all_values)}"])
        
        # Очищаем таблицу статистики
        stats_sheet = self.sheet.worksheet(STATS_SHEET)
        all_values = stats_sheet.get_all_values()
        if len(all_values) > 1:
            stats_sheet.batch_clear([f"A2:Z{len(all_values)}"])
        
        logger.info("Таблицы успешно очищены")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при очистке таблиц: {e}")
        return False

async def get_admin_info(self, user_id: int) -> str:
    """Получение информации о пользователе Telegram по ID"""
    try:
        from telegram import Bot
        from config import BOT_TOKEN
        
        bot = Bot(BOT_TOKEN)
        user = await bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else "нет username"
        full_name = user.full_name
        return f"{full_name} ({username})"
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе {user_id}: {e}")
        return "Не удалось получить информацию"

def add_admin(self, admin_id: int, admin_name: str, admin_description: str) -> bool:
    """Добавление нового администратора"""
    try:
        logger.info(f"Добавление нового администратора: {admin_id}")
        admins_sheet = self.sheet.worksheet(ADMINS_SHEET)
        
        # Проверяем, не существует ли уже такой админ
        existing_admins = [str(id) for id in self.get_admins()]
        if str(admin_id) in existing_admins:
            logger.warning(f"Администратор {admin_id} уже существует")
            return False
        
        # Добавляем нового админа
        admins_sheet.append_row([str(admin_id), admin_name, admin_description])
        logger.info(f"Администратор {admin_id} успешно добавлен")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении администратора: {e}")
        return False

def remove_admin(self, admin_id: int) -> bool:
    """Удаление администратора"""
    try:
        logger.info(f"Удаление администратора: {admin_id}")
        admins_sheet = self.sheet.worksheet(ADMINS_SHEET)
        
        # Получаем все ID админов
        admin_cells = admins_sheet.col_values(1)
        
        # Ищем индекс удаляемого админа
        try:
            row_index = admin_cells.index(str(admin_id)) + 1
        except ValueError:
            logger.warning(f"Администратор {admin_id} не найден")
            return False
        
        # Удаляем строку
        admins_sheet.delete_rows(row_index)
        logger.info(f"Администратор {admin_id} успешно удален")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при удалении администратора: {e}")
        return False

async def get_admins_list(self) -> list:
    """Получение списка всех администраторов с информацией"""
    try:
        admins_sheet = self.sheet.worksheet(ADMINS_SHEET)
        admin_ids = [int(id) for id in admins_sheet.col_values(1)[1:]]  # Пропускаем заголовок
        
        admin_info = []
        for admin_id in admin_ids:
            info = await self.get_admin_info(admin_id)  # Добавляем await
            admin_info.append((admin_id, info))
        
        return admin_info
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка администраторов: {e}")
        return []

def update_sheets_structure(self) -> bool:
    """Обновление структуры листов ответов и статистики в соответствии с текущими вопросами"""
    try:
        logger.info("Обновление структуры листов")
        
        # Получаем текущие вопросы и логируем их структуру перед обновлением
        questions = self.get_questions_with_options()
        logger.info(f"Получены вопросы для обновления структуры: {len(questions)}")
        
        # Логируем варианты с пустыми списками sub_options
        for question, options in questions.items():
            for opt in options:
                if isinstance(opt, dict) and "text" in opt and "sub_options" in opt:
                    if isinstance(opt["sub_options"], list) and not opt["sub_options"]:
                        logger.info(f"🔄 В вопросе '{question}' вариант '{opt['text']}' имеет пустой список sub_options (свободный ответ)")
        
        question_texts = list(questions.keys())
        
        # Обновляем лист ответов
        answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
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
        stats_sheet = self.sheet.worksheet(STATS_SHEET)
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
                            logger.info(f"🆓 Обработка свободного ответа для варианта '{option['text']}' в update_sheets_structure")
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
        logger.info(f"После обновления структуры получено {len(updated_questions)} вопросов")
        
        # Проверяем сохранение вариантов с пустыми списками sub_options после обновления
        for question, options in updated_questions.items():
            for opt in options:
                if isinstance(opt, dict) and "text" in opt and "sub_options" in opt:
                    if isinstance(opt["sub_options"], list) and not opt["sub_options"]:
                        logger.info(f"✅ После обновления структуры в вопросе '{question}' вариант '{opt['text']}' сохранил пустой список sub_options (свободный ответ)")
        
        logger.info("Структура листов успешно обновлена с сохранением существующих данных")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении структуры листов: {e}")
        logger.error(e)
        return False

def has_user_completed_survey(self, user_id: int) -> bool:
    """Проверка, проходил ли пользователь опрос"""
    try:
        answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
        # Получаем столбец с ID пользователей
        user_ids = answers_sheet.col_values(2)[1:]  # Пропускаем заголовок
        # Проверяем, есть ли ID пользователя в списке
        return str(user_id) in user_ids
    except Exception as e:
        logger.error(f"Ошибка при проверке завершения опроса: {e}")
        return False

def reset_user_survey(self, user_id: int) -> bool:
    """Удаление ответов конкретного пользователя"""
    try:
        answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
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
        stats_sheet = self.sheet.worksheet(STATS_SHEET)
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
        
        logger.info(f"Ответы пользователя {user_id} успешно удалены и статистика обновлена")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при удалении ответов пользователя: {e}")
        return False

def get_total_surveys_count(self) -> int:
    """Получение общего количества пройденных опросов"""
    try:
        answers_sheet = self.sheet.worksheet(ANSWERS_SHEET)
        # Получаем все значения из листа ответов
        all_values = answers_sheet.get_all_values()
        # Вычитаем 1 для учета заголовка
        return len(all_values) - 1 if len(all_values) > 1 else 0
    except Exception as e:
        logger.error(f"Ошибка при подсчете общего количества опросов: {e}")
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