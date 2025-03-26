#!/usr/bin/env python3
"""
Скрипт для получения профиля пользователя Telegram по ID
"""
import asyncio
import logging
import sys

from telegram import Bot
from config import BOT_TOKEN

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def get_user_info(user_id: int) -> dict:
    """
    Получение информации о пользователе Telegram
    
    Args:
        user_id (int): ID пользователя в Telegram
        
    Returns:
        dict: Словарь с информацией о пользователе
    """
    try:
        # Создаем экземпляр бота
        bot = Bot(BOT_TOKEN)
        
        # Пробуем получить информацию через get_chat
        user = await bot.get_chat(user_id)
        
        # Формируем базовую информацию
        user_info = {
            'id': user.id,
            'first_name': user.first_name,
            'last_name': user.last_name if hasattr(user, 'last_name') else None,
            'username': user.username if hasattr(user, 'username') else None,
            'full_name': user.full_name,
            'is_bot': user.is_bot,
            'language_code': user.language_code if hasattr(user, 'language_code') else None,
            'bio': user.bio if hasattr(user, 'bio') else None,
            'description': user.description if hasattr(user, 'description') else None,
        }
        
        # Пробуем получить дополнительную информацию через get_chat_member
        try:
            chat_member = await bot.get_chat_member(
                chat_id=user_id,
                user_id=user_id
            )
            
            member_info = {
                'status': chat_member.status,
            }
            
            # Добавляем опциональные поля, которые могут быть доступны
            if hasattr(chat_member, 'joined_date'):
                member_info['joined_date'] = chat_member.joined_date
                
            if hasattr(chat_member, 'can_send_messages'):
                member_info['can_send_messages'] = chat_member.can_send_messages
                
            if hasattr(chat_member, 'can_send_media_messages'):
                member_info['can_send_media_messages'] = chat_member.can_send_media_messages
                
            user_info.update(member_info)
            
        except Exception as e:
            logger.warning(f"Не удалось получить дополнительную информацию: {e}")
        
        return user_info
            
    except Exception as e:
        logger.error(f"Ошибка при получении информации о пользователе: {e}")
        return {
            'id': user_id,
            'error': str(e)
        }

async def main():
    """Основная функция"""
    if len(sys.argv) < 2:
        print("Использование: python get_user_profile.py <user_id>")
        return
        
    try:
        user_id = int(sys.argv[1])
    except ValueError:
        print(f"Ошибка: {sys.argv[1]} не является корректным ID пользователя")
        return
        
    print(f"Получение профиля пользователя с ID {user_id}...")
    
    user_info = await get_user_info(user_id)
    
    print("\nИнформация о пользователе:")
    print("=" * 50)
    
    if 'error' in user_info:
        print(f"Ошибка: {user_info['error']}")
    else:
        for key, value in user_info.items():
            if value is not None:
                print(f"{key}: {value}")
    
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main()) 