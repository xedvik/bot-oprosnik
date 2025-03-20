"""
Модуль для хранения состояний ConversationHandler
"""

# Состояния для основного опроса
WAITING_START = "WAITING_START"
CONFIRMING = "CONFIRMING"

# Состояния для редактирования вопросов
CHOOSING_QUESTION = "CHOOSING_QUESTION"
EDITING_QUESTION = "EDITING_QUESTION"
EDITING_QUESTION_TEXT = "EDITING_QUESTION_TEXT"
EDITING_OPTIONS = "EDITING_OPTIONS"

# Состояния для добавления вопросов
ADDING_QUESTION = "ADDING_QUESTION"
CHOOSING_OPTIONS_TYPE = "CHOOSING_OPTIONS_TYPE"
ADDING_OPTIONS = "ADDING_OPTIONS"

# Состояния для удаления вопросов
DELETING_QUESTION = "DELETING_QUESTION"

# Состояние для подтверждения очистки данных
CONFIRMING_CLEAR = "CONFIRMING_CLEAR"

# Динамические состояния для вопросов
# Будут генерироваться в формате QUESTION_0, QUESTION_1, ...

# Состояния для управления администраторами
ADDING_ADMIN = "ADDING_ADMIN"
ADDING_ADMIN_NAME = "ADDING_ADMIN_NAME"
ADDING_ADMIN_DESCRIPTION = "ADDING_ADMIN_DESCRIPTION"
REMOVING_ADMIN = "REMOVING_ADMIN"
RESETTING_USER = "RESETTING_USER"

# Состояния для редактирования сообщений
CHOOSING_MESSAGE_TYPE = "CHOOSING_MESSAGE_TYPE"
ENTERING_NEW_MESSAGE = "ENTERING_NEW_MESSAGE" 