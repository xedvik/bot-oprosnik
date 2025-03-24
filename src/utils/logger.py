"""
Модуль для стандартизации логирования в приложении.
Реализует независимую систему логирования без использования стандартного модуля logging.
"""

from functools import wraps
import inspect
import time
import traceback
import sys
import os
from datetime import datetime
from typing import Any, Optional, Dict, Callable, TextIO, List

# Константы для уровней логирования
DEBUG = 10
INFO = 20 
WARNING = 30
ERROR = 40
CRITICAL = 50

# Словарь названий уровней логирования
LEVEL_NAMES = {
    DEBUG: "DEBUG",
    INFO: "INFO",
    WARNING: "WARNING",
    ERROR: "ERROR",
    CRITICAL: "CRITICAL"
}

# Глобальный уровень логирования
_global_log_level = INFO
# Выходные потоки для логирования
_log_streams: List[TextIO] = [sys.stdout]
# Формат даты и времени
_date_format = "%Y-%m-%d %H:%M:%S"

def setup_logging(level: int = INFO, log_file: Optional[str] = None, date_format: str = "%Y-%m-%d %H:%M:%S"):
    """
    Настройка глобальных параметров логирования
    
    Args:
        level (int): Уровень логирования
        log_file (Optional[str]): Путь к файлу для записи логов
        date_format (str): Формат даты и времени
    """
    global _global_log_level, _log_streams, _date_format
    
    _global_log_level = level
    _date_format = date_format
    
    # Сбросим потоки
    _log_streams = [sys.stdout]
    
    # Добавим файл логов, если указан
    if log_file:
        try:
            # Убедимся, что директория существует
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            # Откроем файл для записи
            file_stream = open(log_file, "a", encoding="utf-8")
            _log_streams.append(file_stream)
        except Exception as e:
            _write_to_stream(sys.stderr, f"Ошибка при открытии файла логов {log_file}: {e}")

def _write_log(level: int, name: str, message: str, extra: Optional[Dict[str, Any]] = None, exc_info: bool = False):
    """
    Запись сообщения в лог
    
    Args:
        level (int): Уровень логирования
        name (str): Имя логгера
        message (str): Сообщение для логирования
        extra (Optional[Dict[str, Any]]): Дополнительная информация
        exc_info (bool): Добавлять ли информацию об исключении
    """
    if level < _global_log_level:
        return
    
    # Формируем временную метку
    timestamp = datetime.now().strftime(_date_format)
    
    # Формируем строку лога
    log_line = f"[{timestamp}] [{LEVEL_NAMES.get(level, 'UNKNOWN')}] [{name}] {message}"
    
    # Добавляем дополнительную информацию, если есть
    if extra:
        details = ", ".join(f"{k}={v}" for k, v in extra.items())
        log_line += f" ({details})"
    
    # Записываем в потоки
    for stream in _log_streams:
        _write_to_stream(stream, log_line)
    
    # Добавляем информацию об исключении, если требуется
    if exc_info:
        for stream in _log_streams:
            _write_to_stream(stream, traceback.format_exc())

def _write_to_stream(stream: TextIO, message: str):
    """
    Записывает сообщение в поток с обработкой исключений
    
    Args:
        stream (TextIO): Поток для записи
        message (str): Сообщение для записи
    """
    try:
        stream.write(message + "\n")
        stream.flush()
    except Exception:
        pass

class AppLogger:
    """
    Класс-обертка для стандартизации логирования в приложении.
    Предоставляет удобные методы для форматированного логирования различных событий.
    """
    
    # Константы для определения типов операций
    INIT = "init"            # Инициализация компонентов
    USER_ACTION = "user"     # Действия пользователя
    ADMIN_ACTION = "admin"   # Действия администратора
    DATA_LOAD = "data_load"  # Загрузка данных
    DATA_SAVE = "data_save"  # Сохранение данных
    CACHE = "cache"          # Операции с кэшем
    ERROR = "error"          # Ошибки и исключения
    STATE = "state"          # Изменения состояния
    API = "api"              # Вызовы внешнего API
    DATA_PROCESSING = "data_processing"  # Обработка данных
    
    def __init__(self, name: str):
        """
        Инициализация логгера с указанным именем
        
        Args:
            name (str): Имя логгера, обычно __name__ модуля
        """
        self.module_name = name
    
    def user_action(self, user_id: int, action: str, result: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование действий пользователя
        
        Args:
            user_id (int): ID пользователя в Telegram
            action (str): Выполненное действие
            result (Optional[str]): Результат действия
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"[USER:{user_id}] {action}"
        if result:
            msg += f" → {result}"
        
        extra = {"operation_type": self.USER_ACTION, "user_id": user_id}
        if details:
            extra.update({"details": details})
        
        _write_log(INFO, self.module_name, msg, extra)
    
    def admin_action(self, admin_id: int, action: str, result: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование действий администратора
        
        Args:
            admin_id (int): ID администратора в Telegram
            action (str): Выполненное действие
            result (Optional[str]): Результат действия
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"[ADMIN:{admin_id}] {action}"
        if result:
            msg += f" → {result}"
        
        extra = {"operation_type": self.ADMIN_ACTION, "admin_id": admin_id}
        if details:
            extra.update({"details": details})
        
        _write_log(INFO, self.module_name, msg, extra)
    
    def init(self, component: str, result: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование инициализации компонентов
        
        Args:
            component (str): Название компонента
            result (Optional[str]): Результат инициализации
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"Инициализация: {component}"
        if result:
            msg += f" → {result}"
        
        extra = {"operation_type": self.INIT, "component": component}
        if details:
            extra.update({"details": details})
        
        _write_log(INFO, self.module_name, msg, extra)
    
    def data_load(self, data_type: str, source: str, count: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование загрузки данных
        
        Args:
            data_type (str): Тип загружаемых данных
            source (str): Источник данных
            count (Optional[int]): Количество загруженных элементов
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"Загрузка {data_type} из {source}"
        if count is not None:
            msg += f" ({count} элементов)"
        
        extra = {"operation_type": self.DATA_LOAD, "data_type": data_type}
        if details:
            extra.update({"details": details})
        
        _write_log(INFO, self.module_name, msg, extra)
    
    def data_save(self, data_type: str, destination: str, count: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование сохранения данных
        
        Args:
            data_type (str): Тип сохраняемых данных
            destination (str): Место сохранения
            count (Optional[int]): Количество сохраненных элементов
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"Сохранение {data_type} в {destination}"
        if count is not None:
            msg += f" ({count} элементов)"
        
        extra = {"operation_type": self.DATA_SAVE, "data_type": data_type}
        if details:
            extra.update({"details": details})
        
        _write_log(INFO, self.module_name, msg, extra)
    
    def data_processing(self, data_type: str, action: str, duration: Optional[float] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование обработки данных
        
        Args:
            data_type (str): Тип обрабатываемых данных
            action (str): Выполняемое действие
            duration (Optional[float]): Длительность обработки в секундах
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        # Проверка и коррекция аргументов для максимальной устойчивости
        # Если action передан как duration (третий аргумент), исправляем это
        if isinstance(duration, str) and details is None:
            # Если duration - строка, а details не указан, то считаем что duration - это action_id
            details = {"action_id": duration}
            duration = None
            
        # Если в details передан action_id, сохраняем его отдельно для лога
        action_id = None
        if details and "action_id" in details:
            action_id = details.pop("action_id")
        elif details and "action" in details:
            action_id = details.pop("action")
        
        # Формируем сообщение
        msg = f"Обработка {data_type}: {action}"
        if action_id:
            msg += f" ({action_id})"
            
        # Добавляем информацию о длительности, если она указана
        if duration is not None:
            if isinstance(duration, (int, float)):
                msg += f" за {duration:.2f} сек"
            else:
                # Если duration не число, добавляем его в details
                if details is None:
                    details = {}
                details["duration_str"] = str(duration)
        
        extra = {"operation_type": self.DATA_PROCESSING, "data_type": data_type}
        if details:
            extra.update({"details": details})
        
        _write_log(INFO, self.module_name, msg, extra)
    
    def cache_hit(self, cache_type: str, key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование попадания в кэш
        
        Args:
            cache_type (str): Тип кэша
            key (Optional[str]): Ключ кэша
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"Кэш {cache_type} использован"
        if key:
            msg += f" для ключа {key}"
        
        extra = {"operation_type": self.CACHE, "cache_action": "hit"}
        if details:
            extra.update({"details": details})
        
        _write_log(DEBUG, self.module_name, msg, extra)
    
    def cache_miss(self, cache_type: str, key: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование промаха кэша
        
        Args:
            cache_type (str): Тип кэша
            key (Optional[str]): Ключ кэша
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"Кэш {cache_type} не найден"
        if key:
            msg += f" для ключа {key}"
        
        extra = {"operation_type": self.CACHE, "cache_action": "miss"}
        if details:
            extra.update({"details": details})
        
        _write_log(DEBUG, self.module_name, msg, extra)
    
    def cache_update(self, cache_type: str, key: Optional[str] = None, count: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование обновления кэша
        
        Args:
            cache_type (str): Тип кэша
            key (Optional[str]): Ключ кэша
            count (Optional[int]): Количество элементов в кэше
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"Кэш {cache_type} обновлен"
        if key:
            msg += f" для ключа {key}"
        if count is not None:
            msg += f" ({count} элементов)"
        
        extra = {"operation_type": self.CACHE, "cache_action": "update"}
        if details:
            extra.update({"details": details})
        
        _write_log(INFO, self.module_name, msg, extra)
    
    def error(self, error_type: str, exception: Optional[Exception] = None, user_id: Optional[int] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование ошибок
        
        Args:
            error_type (str): Тип ошибки
            exception (Optional[Exception]): Объект исключения
            user_id (Optional[int]): ID пользователя, связанного с ошибкой
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        user_prefix = f"[USER:{user_id}] " if user_id else ""
        msg = f"{user_prefix}Ошибка: {error_type}"
        if exception:
            msg += f" - {str(exception)}"
        
        extra = {"operation_type": self.ERROR, "error_type": error_type}
        if user_id:
            extra["user_id"] = user_id
        if details:
            extra.update({"details": details})
        
        _write_log(ERROR, self.module_name, msg, extra, exc_info=exception is not None)
    
    def state_change(self, entity: str, from_state: str, to_state: str, details: Optional[Dict[str, Any]] = None):
        """
        Логирование изменения состояния
        
        Args:
            entity (str): Сущность, изменившая состояние
            from_state (str): Предыдущее состояние
            to_state (str): Новое состояние
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"Изменение состояния {entity}: {from_state} → {to_state}"
        
        extra = {"operation_type": self.STATE, "entity": entity}
        if details:
            extra.update({"details": details})
        
        _write_log(INFO, self.module_name, msg, extra)
    
    def api_call(self, api_name: str, method: str, result: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        """
        Логирование вызова внешнего API
        
        Args:
            api_name (str): Название API
            method (str): Вызываемый метод
            result (Optional[str]): Результат вызова
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        msg = f"API {api_name}: вызов {method}"
        if result:
            msg += f" → {result}"
        
        extra = {"operation_type": self.API, "api": api_name}
        if details:
            extra.update({"details": details})
        
        _write_log(INFO, self.module_name, msg, extra)
    
    def debug(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Логирование отладочных сообщений
        
        Args:
            message (str): Сообщение для логирования
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        _write_log(DEBUG, self.module_name, message, details)
    
    def info(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Логирование информационных сообщений
        
        Args:
            message (str): Сообщение для логирования
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        _write_log(INFO, self.module_name, message, details)
    
    def warning(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Логирование предупреждений
        
        Args:
            message (str): Сообщение для логирования
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        _write_log(WARNING, self.module_name, message, details)
    
    def critical(self, message: str, details: Optional[Dict[str, Any]] = None):
        """
        Логирование критических ошибок
        
        Args:
            message (str): Сообщение для логирования
            details (Optional[Dict[str, Any]]): Дополнительные детали
        """
        _write_log(CRITICAL, self.module_name, message, details)
    
    @staticmethod
    def method_logger(log_level: int = INFO, log_args: bool = False, log_result: bool = False):
        """
        Декоратор для логирования вызовов методов
        
        Args:
            log_level: Уровень логирования
            log_args: Логировать ли аргументы функции
            log_result: Логировать ли результат функции
            
        Returns:
            Callable: Декорированная функция
        """
        
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Получаем информацию о вызываемом методе
                method_name = func.__name__
                module_name = func.__module__
                
                # Создаем логгер для модуля
                logger = AppLogger(module_name)
                
                # Логируем начало вызова
                if log_args:
                    # Пропускаем первый аргумент (self) для методов класса
                    args_str = ", ".join([str(a) for a in args[1:]]) if len(args) > 0 else ""
                    kwargs_str = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
                    args_log = f"{args_str}, {kwargs_str}" if args_str and kwargs_str else f"{args_str}{kwargs_str}"
                    _write_log(DEBUG, module_name, f"Вызов {method_name}({args_log})")
                else:
                    _write_log(DEBUG, module_name, f"Вызов {method_name}")
                
                # Замеряем время выполнения
                start_time = time.time()
                
                try:
                    # Выполняем метод
                    result = func(*args, **kwargs)
                    
                    # Вычисляем время выполнения
                    execution_time = time.time() - start_time
                    
                    # Логируем завершение вызова
                    if log_result:
                        result_str = str(result) if len(str(result)) < 100 else f"{str(result)[:100]}..."
                        _write_log(DEBUG, module_name, f"{method_name} завершен за {execution_time:.4f}с: {result_str}")
                    else:
                        _write_log(DEBUG, module_name, f"{method_name} завершен за {execution_time:.4f}с")
                    
                    return result
                except Exception as e:
                    # Вычисляем время до исключения
                    execution_time = time.time() - start_time
                    
                    # Логируем исключение
                    logger.error("method_execution", exception=e, details={
                        "method": method_name,
                        "execution_time": f"{execution_time:.4f}с",
                        "traceback": traceback.format_exc()
                    })
                    
                    # Пробрасываем исключение дальше
                    raise
            
            return wrapper
        
        return decorator


# Создаем функцию для получения логгера по имени модуля
def get_logger(name: Optional[str] = None) -> AppLogger:
    """
    Получает логгер с заданным именем или именем вызывающего модуля
    
    Args:
        name (Optional[str]): Имя логгера. Если None, определяется автоматически
        
    Returns:
        AppLogger: Настроенный логгер
    """
    if name is None:
        # Получаем имя вызывающего модуля
        frame = inspect.currentframe().f_back
        name = frame.f_globals['__name__']
    
    return AppLogger(name) 