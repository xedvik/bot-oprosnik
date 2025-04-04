"""
Модуль для хранения состояний ConversationHandler
"""

# Состояния для основного опроса
WAITING_START = "WAITING_START"
CONFIRMING = "CONFIRMING"

# Состояния для вложенных вариантов ответов
SUB_OPTIONS = "SUB_OPTIONS"
QUESTION_SUB = "QUESTION_SUB"

# Состояния для редактирования вопросов
CHOOSING_QUESTION = "CHOOSING_QUESTION"
EDITING_QUESTION = "EDITING_QUESTION"
EDITING_QUESTION_TEXT = "EDITING_QUESTION_TEXT"
EDITING_OPTIONS, EDITING_SUB_OPTIONS = map(chr, range(17, 19))
ADDING_SUB_OPTION, REMOVING_SUB_OPTION, ADDING_FREE_TEXT_PROMPT = map(chr, range(19, 22))
SELECTING_OPTION_TO_EDIT = chr(22)  # Состояние выбора варианта для редактирования
EDITING_OPTION_TEXT = chr(23)  # Состояние ввода нового текста для варианта

# Состояния для добавления вопросов
ADDING_QUESTION = "ADDING_QUESTION"
CHOOSING_OPTIONS_TYPE = "CHOOSING_OPTIONS_TYPE"
ADDING_OPTIONS = "ADDING_OPTIONS"
ADDING_NESTED_OPTIONS = "ADDING_NESTED_OPTIONS"

# Состояния для удаления вопросов
DELETING_QUESTION = "DELETING_QUESTION"

# Состояние для подтверждения очистки данных
CONFIRMING_CLEAR = "CONFIRMING_CLEAR"

# Динамические состояния для вопросов
# Будут генерироваться в формате QUESTION_0, QUESTION_1, ...
# Для вложенных вариантов: QUESTION_0_SUB, QUESTION_1_SUB, ...

# Состояния для управления администраторами
ADDING_ADMIN = "ADDING_ADMIN"
ADDING_ADMIN_NAME = "ADDING_ADMIN_NAME"
ADDING_ADMIN_DESCRIPTION = "ADDING_ADMIN_DESCRIPTION"
REMOVING_ADMIN = "REMOVING_ADMIN"
RESETTING_USER = "RESETTING_USER"

# Состояния для редактирования сообщений
CHOOSING_MESSAGE_TYPE = "CHOOSING_MESSAGE_TYPE"
ENTERING_NEW_MESSAGE = "ENTERING_NEW_MESSAGE"
ASKING_ADD_IMAGE = "ASKING_ADD_IMAGE"
UPLOADING_MESSAGE_IMAGE = "UPLOADING_MESSAGE_IMAGE"

# Состояние для просмотра списка пользователей
BROWSING_USERS = "BROWSING_USERS"


# Состояния для создания и отправки постов
CREATING_POST = "CREATING_POST"  # Ввод названия поста
ENTERING_POST_TEXT = "ENTERING_POST_TEXT"  # Ввод текста поста
ADDING_POST_IMAGE = "ADDING_POST_IMAGE"
ADDING_URL_BUTTON = "ADDING_URL_BUTTON"
CONFIRM_POST_SENDING = "CONFIRM_POST_SENDING"
ENTERING_BUTTON_TEXT = "ENTERING_BUTTON_TEXT"  # Ввод текста кнопки
ENTERING_BUTTON_URL = "ENTERING_BUTTON_URL"    # Ввод URL кнопки
CONFIRMING_POST = "CONFIRMING_POST"            # Подтверждение поста
CONFIRMING_SEND_TO_ALL = "CONFIRMING_SEND_TO_ALL"  # Подтверждение отправки всем
SELECTING_POST_ACTION = "SELECTING_POST_ACTION"    # Выбор действия с постом
CONFIRMING_POST_DELETE = "CONFIRMING_POST_DELETE"  # Подтверждение удаления поста

