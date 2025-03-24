# Документация по системе логирования

В проекте реализована расширенная система логирования, которая предоставляет структурированный и унифицированный подход к логированию различных событий приложения. Система построена на стандартной библиотеке `logging` с дополнительными возможностями и удобствами.

## Основные компоненты

1. **AppLogger** - класс-обертка для логирования, предоставляющий методы для различных типов событий
2. **Структурированные логи** - возможность вывода логов в формате JSON
3. **Конфигурируемые уровни логирования** - для разных модулей могут быть установлены различные уровни

## Использование AppLogger

### Получение логгера

```python
from utils.logger import get_logger

# Получение логгера для текущего модуля
logger = get_logger()

# Или можно указать имя явно
logger = get_logger('custom_module_name')
```

### Логирование разных типов событий

#### Инициализация компонентов

```python
logger.init("ComponentName", "Инициализация компонента")
logger.init("Database", "Соединение установлено", details={"host": "localhost"})
```

#### Действия пользователя

```python
logger.user_action(user_id=123456789, action="Нажатие кнопки", result="Открыт список вопросов")
logger.user_action(user_id=123456789, action="Ответ на вопрос", details={"question_id": 1, "answer": "Вариант 1"})
```

#### Действия администратора

```python
logger.admin_action(admin_id=987654321, action="Добавление вопроса", result="Вопрос создан")
logger.admin_action(admin_id=987654321, action="Редактирование сообщения", details={"message_type": "welcome"})
```

#### Загрузка данных

```python
logger.data_load("вопросы", "Google Sheets", count=10)
logger.data_load("пользователи", "база данных", details={"filter": "active=true"})
```

#### Сохранение данных

```python
logger.data_save("ответы", "Google Sheets", count=5)
logger.data_save("настройки", "конфигурационный файл")
```

#### Работа с кэшем

```python
logger.cache_hit("questions")
logger.cache_miss("users", key="user_123")
logger.cache_update("posts", count=15)
```

#### Ошибки

```python
try:
    # Код, который может вызвать исключение
    result = some_function()
except Exception as e:
    logger.error("validation_error", e, user_id=123456789)
```

#### Изменение состояния

```python
logger.state_change("опрос", "waiting_start", "question_1", details={"user_id": 123456789})
```

#### Вызовы API

```python
logger.api_call("Telegram", "sendMessage", result="успешно")
```

#### Стандартные методы

```python
logger.debug("Отладочное сообщение")
logger.info("Информационное сообщение")
logger.warning("Предупреждение")
logger.critical("Критическая ошибка")
```

### Декоратор для логирования методов

```python
from utils.logger import AppLogger

@AppLogger.method_logger(log_args=True, log_result=True)
def some_function(arg1, arg2):
    # Функция будет автоматически логировать начало выполнения, аргументы,
    # результат выполнения и время выполнения
    return arg1 + arg2
```

## Конфигурация

Настройка логирования выполняется в файле `config.py`. Основные параметры:

- `LOG_LEVEL` - общий уровень логирования
- `LOG_FILE` - путь к файлу журнала
- `LOG_JSON` - использование JSON формата для структурированного логирования
- `MODULE_LOG_LEVELS` - индивидуальные уровни для разных модулей

## JSON формат логов

Если включен режим `LOG_JSON=true`, логи будут выводиться в следующем формате:

```json
{
  "timestamp": "2023-03-24 10:15:30",
  "name": "utils.sheets",
  "level": "INFO",
  "message": "Загрузка вопросы из Google Sheets (4 элементов)",
  "operation_type": "data_load",
  "data_type": "вопросы",
  "details": {
    "options_count": 12
  }
}
```

## Уровни логирования

- **DEBUG** - детальная отладочная информация
- **INFO** - подтверждение нормальной работы
- **WARNING** - индикация потенциальных проблем
- **ERROR** - ошибки, не прерывающие работу программы
- **CRITICAL** - критические ошибки, ведущие к остановке программы

## Рекомендации

1. Используйте методы `AppLogger` вместо стандартных методов логирования
2. Включайте полезную информацию в поле `details`
3. Для пользовательских действий всегда указывайте `user_id`
4. Используйте уровень `DEBUG` для информации, необходимой только при отладке
5. Логируйте ошибки с полной информацией об исключении 