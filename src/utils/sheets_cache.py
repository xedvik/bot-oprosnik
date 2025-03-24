"""
Модуль для кэширования данных из Google Sheets
"""

import time
from typing import Dict, List, Any, Optional, Callable
import threading
import asyncio
from datetime import datetime

from utils.logger import get_logger

# Получаем логгер для модуля
logger = get_logger()

class SheetsCache:
    """Синглтон-класс для кэширования данных из Google Sheets"""
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SheetsCache, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Инициализация кэшей и настроек
        self._users_cache = {}  # Кэш пользователей: {telegram_id: user_data}
        self._users_cache_time = 0
        self._users_cache_ttl = 300  # 5 минут
        
        self._messages_cache = {}  # Кэш сообщений: {message_type: message_data}
        self._messages_cache_time = 0
        self._messages_cache_ttl = 600  # 10 минут
        
        self._posts_cache = []  # Кэш постов
        self._posts_cache_time = 0
        self._posts_cache_ttl = 600  # 10 минут
        
        self._admins_cache = []  # Кэш администраторов
        self._admins_cache_time = 0
        self._admins_cache_ttl = 300  # 5 минут
        
        # Счетчик запросов
        self._requests_count = 0
        self._requests_time = time.time()
        self._requests_limit = 60  # Лимит запросов в минуту
        self._requests_queue = []  # Очередь отложенных запросов
        
        self._initialized = True
        logger.init("SheetsCache", "Инициализирован синглтон кэша для Sheets API")
    
    async def _process_queue(self):
        """Обрабатывает очередь отложенных запросов"""
        while self._requests_queue:
            # Проверяем, можем ли выполнить запрос
            current_time = time.time()
            if current_time - self._requests_time >= 60:
                # Прошла минута, сбрасываем счетчик
                self._requests_count = 0
                self._requests_time = current_time
            
            if self._requests_count < self._requests_limit:
                # Можем выполнить запрос
                func, args, kwargs, future = self._requests_queue.pop(0)
                try:
                    self._requests_count += 1
                    result = func(*args, **kwargs)
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
            else:
                # Нужно подождать до сброса счетчика
                wait_time = 60 - (current_time - self._requests_time)
                logger.warning("rate_limit", f"Достигнут лимит запросов к API, ожидание {wait_time:.2f}с")
                await asyncio.sleep(wait_time)
    
    async def execute_with_rate_limit(self, func, *args, **kwargs):
        """Выполняет функцию с учетом ограничения на количество запросов"""
        with self._lock:
            current_time = time.time()
            if current_time - self._requests_time >= 60:
                # Прошла минута, сбрасываем счетчик
                self._requests_count = 0
                self._requests_time = current_time
            
            if self._requests_count < self._requests_limit:
                # Можем выполнить запрос немедленно
                self._requests_count += 1
                return func(*args, **kwargs)
            else:
                # Ставим запрос в очередь
                future = asyncio.Future()
                self._requests_queue.append((func, args, kwargs, future))
                
                # Запускаем обработку очереди, если она еще не запущена
                asyncio.create_task(self._process_queue())
                
                # Ждем результата
                return await future
    
    def get_user(self, telegram_id: int, fetch_function: Callable) -> dict:
        """Получает данные пользователя из кэша или через fetch_function"""
        with self._lock:
            current_time = time.time()
            
            # Проверяем наличие пользователя в кэше
            if (telegram_id in self._users_cache and 
                current_time - self._users_cache_time < self._users_cache_ttl):
                logger.cache_hit("users", details={"telegram_id": telegram_id})
                return self._users_cache[telegram_id]
            
            # Запрашиваем данные у API
            logger.cache_miss("users", details={"telegram_id": telegram_id})
            user_data = fetch_function(telegram_id)
            
            # Обновляем кэш
            self._users_cache[telegram_id] = user_data
            self._users_cache_time = current_time
            logger.cache_update("users", details={"telegram_id": telegram_id})
            
            return user_data
    
    def is_user_exists(self, telegram_id: int, fetch_function: Callable) -> bool:
        """Проверяет существование пользователя через кэш или fetch_function"""
        with self._lock:
            # Если пользователь есть в кэше, значит он существует
            if telegram_id in self._users_cache:
                logger.cache_hit("users_exists", details={"telegram_id": telegram_id})
                return True
            
            # Иначе проверяем через API
            logger.cache_miss("users_exists", details={"telegram_id": telegram_id})
            exists = fetch_function(telegram_id)
            
            # Если пользователь существует, добавляем пустую запись в кэш
            if exists:
                self._users_cache[telegram_id] = {"exists": True}
                logger.cache_update("users_exists", details={"telegram_id": telegram_id, "exists": True})
            
            return exists
    
    def get_message(self, message_type: str, fetch_function: Callable) -> dict:
        """Получает сообщение из кэша или через fetch_function"""
        with self._lock:
            current_time = time.time()
            
            # Проверяем наличие сообщения в кэше
            if (message_type in self._messages_cache and 
                current_time - self._messages_cache_time < self._messages_cache_ttl):
                logger.cache_hit("messages", details={"message_type": message_type})
                return self._messages_cache[message_type]
            
            # Запрашиваем данные у API
            logger.cache_miss("messages", details={"message_type": message_type})
            message_data = fetch_function(message_type)
            
            # Обновляем кэш
            self._messages_cache[message_type] = message_data
            self._messages_cache_time = current_time
            logger.cache_update("messages", details={"message_type": message_type})
            
            return message_data
    
    def get_admins(self, fetch_function: Callable) -> list:
        """Получает список администраторов из кэша или через fetch_function"""
        with self._lock:
            current_time = time.time()
            
            # Проверяем актуальность кэша
            if (self._admins_cache and 
                current_time - self._admins_cache_time < self._admins_cache_ttl):
                logger.cache_hit("admins", details={"count": len(self._admins_cache)})
                return self._admins_cache.copy()
            
            # Запрашиваем данные у API
            logger.cache_miss("admins")
            admins = fetch_function()
            
            # Обновляем кэш
            self._admins_cache = admins
            self._admins_cache_time = current_time
            logger.cache_update("admins", details={"count": len(admins)})
            
            return admins.copy()
    
    def get_posts(self, fetch_function: Callable) -> list:
        """Получает список постов из кэша или через fetch_function"""
        with self._lock:
            current_time = time.time()
            
            # Проверяем актуальность кэша
            if (self._posts_cache and 
                current_time - self._posts_cache_time < self._posts_cache_ttl):
                logger.cache_hit("posts", details={"count": len(self._posts_cache)})
                return self._posts_cache.copy()
            
            # Запрашиваем данные у API
            logger.cache_miss("posts")
            posts = fetch_function()
            
            # Обновляем кэш
            self._posts_cache = posts
            self._posts_cache_time = current_time
            logger.cache_update("posts", details={"count": len(posts)})
            
            return posts.copy()
    
    def invalidate_user_cache(self, telegram_id: int = None):
        """Сбрасывает кэш пользователя или всех пользователей"""
        with self._lock:
            if telegram_id is not None:
                if telegram_id in self._users_cache:
                    del self._users_cache[telegram_id]
                    logger.cache_update("users", details={"action": "invalidate", "telegram_id": telegram_id})
            else:
                self._users_cache = {}
                self._users_cache_time = 0
                logger.cache_update("users", details={"action": "invalidate_all"})
    
    def invalidate_messages_cache(self, message_type: str = None):
        """Сбрасывает кэш сообщения или всех сообщений"""
        with self._lock:
            if message_type is not None:
                if message_type in self._messages_cache:
                    del self._messages_cache[message_type]
                    logger.cache_update("messages", details={"action": "invalidate", "message_type": message_type})
            else:
                self._messages_cache = {}
                self._messages_cache_time = 0
                logger.cache_update("messages", details={"action": "invalidate_all"})
    
    def invalidate_posts_cache(self):
        """Сбрасывает кэш постов"""
        with self._lock:
            self._posts_cache = []
            self._posts_cache_time = 0
            logger.cache_update("posts", details={"action": "invalidate"})
    
    def invalidate_admins_cache(self):
        """Сбрасывает кэш администраторов"""
        with self._lock:
            self._admins_cache = []
            self._admins_cache_time = 0
            logger.cache_update("admins", details={"action": "invalidate"})
    
    def invalidate_all_caches(self):
        """Сбрасывает все кэши"""
        with self._lock:
            self.invalidate_user_cache()
            self.invalidate_messages_cache()
            self.invalidate_posts_cache()
            self.invalidate_admins_cache()
            logger.cache_update("all", details={"action": "invalidate_all"})

# Глобальный экземпляр кэша
sheets_cache = SheetsCache() 