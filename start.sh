#!/bin/bash

# Проверяем наличие файла credentials.json
if [ ! -f "credentials.json" ]; then
    echo "Ошибка: файл credentials.json не найден"
    echo "Пожалуйста, создайте файл credentials.json с учетными данными Google API"
    exit 1
fi

# Проверяем наличие файла .env
if [ ! -f ".env" ]; then
    echo "Ошибка: файл .env не найден"
    echo "Пожалуйста, создайте файл .env с необходимыми переменными окружения"
    exit 1
fi

# Создаем директорию для логов
mkdir -p logs

# Запускаем бота в Docker
docker-compose up -d

echo "Бот запущен. Логи доступны в директории logs/" 