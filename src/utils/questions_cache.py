"""
Модуль с классом-синглтоном для кэша вопросов
"""

import time
from typing import Dict, List, Any, Optional, Callable

from utils.logger import get_logger

# Получаем логгер для модуля
logger = get_logger()

class QuestionsCache:
    """Синглтон-класс для хранения и управления кэшем вопросов"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QuestionsCache, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Инициализация кэша и настроек
        self._questions_cache: Optional[Dict[str, List[Any]]] = None
        self._questions_cache_time: float = 0
        self._questions_cache_ttl: int = 30  # время жизни кэша в секундах
        self._initialized = True
        logger.init("QuestionsCache", "Инициализирован синглтон")
    
    def get_questions(self, fetch_function: Callable[[], Dict[str, List[Any]]]) -> Dict[str, List[Any]]:
        """
        Получает вопросы из кэша или через функцию fetch_function если кэш устарел
        
        Args:
            fetch_function: Функция для получения вопросов из источника данных
            
        Returns:
            Dict[str, List[Any]]: Словарь с вопросами и вариантами ответов
        """
        current_time = time.time()
        
        # Проверка наличия актуального кэша
        if (self._questions_cache is not None and 
            current_time - self._questions_cache_time < self._questions_cache_ttl):
            # Сообщаем о кэше только при debug-уровне логирования
            questions_count = len(self._questions_cache) if self._questions_cache else 0
            logger.cache_hit("questions", details={"count": questions_count})
            return self._questions_cache.copy()
        
        # Запрашиваем новые данные
        logger.cache_miss("questions")
        questions = fetch_function()
        
        # Обновляем кэш
        self._questions_cache = questions
        self._questions_cache_time = current_time
        questions_count = len(questions) if questions else 0
        logger.cache_update("questions", count=questions_count)
        
        return questions.copy()
    
    def invalidate_cache(self):
        """Сбрасывает кэш вопросов, чтобы при следующем вызове данные были загружены заново"""
        self._questions_cache = None
        self._questions_cache_time = 0
        logger.cache_update("questions", details={"action": "reset"})
    
    def update_cache(self, questions: Dict[str, List[Any]]):
        """Принудительное обновление кэша новыми данными"""
        self._questions_cache = questions
        self._questions_cache_time = time.time()
        questions_count = len(questions) if questions else 0
        logger.cache_update("questions", count=questions_count, details={"forced": True}) 