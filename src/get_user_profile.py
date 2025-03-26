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
        chat = await bot.get_chat(user_id)
        
        # Формируем базовую информацию
        user_info = {
            'id': chat.id,
            'type': chat.type,
        }
        
        # Добавляем информацию, которая может быть доступна в зависимости от типа чата
        if hasattr(chat, 'first_name'):
            user_info['first_name'] = chat.first_name
        
        if hasattr(chat, 'last_name'):
            user_info['last_name'] = chat.last_name
            
        if hasattr(chat, 'username'):
            user_info['username'] = chat.username
            
        if hasattr(chat, 'bio'):
            user_info['bio'] = chat.bio
            
        if hasattr(chat, 'full_name'):
            user_info['full_name'] = chat.full_name
        else:
            # Формируем full_name из first_name и last_name если доступны
            full_name = user_info.get('first_name', '')
            if user_info.get('last_name'):
                full_name += ' ' + user_info.get('last_name')
            if full_name:
                user_info['full_name'] = full_name
                
        if hasattr(chat, 'description'):
            user_info['description'] = chat.description
        
        if hasattr(chat, 'invite_link'):
            user_info['invite_link'] = chat.invite_link
            
        # Пробуем получить дополнительную информацию через get_chat_member
        try:
            chat_member = await bot.get_chat_member(
                chat_id=user_id,
                user_id=user_id
            )
            
            member_info = {
                'status': chat_member.status,
            }
            
            # Добавляем информацию о пользователе из chat_member
            if hasattr(chat_member, 'user'):
                user = chat_member.user
                if hasattr(user, 'is_bot'):
                    member_info['is_bot'] = user.is_bot
                if hasattr(user, 'language_code'):
                    member_info['language_code'] = user.language_code
            
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