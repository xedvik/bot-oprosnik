"""
Пакет с утилитами для бота
"""

# Инициализация синглтона при загрузке пакета
from utils.questions_cache import QuestionsCache
questions_cache = QuestionsCache()

# Импортируем основные модули для обеспечения их загрузки
# Это гарантирует, что все методы будут корректно добавлены
import utils.sheets
import utils.sheets_questions 