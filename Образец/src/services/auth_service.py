"""
Сервис для аутентификации с Yandex Cloud API
"""
import os
import time
import json
import jwt
import requests
from typing import Optional


class AuthService:
    """Сервис для работы с аутентификацией Yandex Cloud"""
    
    # URL для получения IAM токена через метаданные в Yandex Cloud
    METADATA_IAM_TOKEN_URL = "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
    
    def __init__(self):
        """Инициализация сервиса аутентификации"""
        self.api_key = os.getenv("YANDEX_API_KEY_SECRET")
        self.service_account_id = None
        self.service_account_key_id = None
        self.service_account_private_key = None
        self._use_metadata = None  # Кэш для проверки доступности метаданных
        
        if not self.api_key:
            raise ValueError("Не задан YANDEX_API_KEY_SECRET в переменных окружения")
        
        # Загружаем данные сервисного аккаунта (только для локальной разработки)
        self._load_service_account_data()
        
        # Проверяем доступность метаданных Yandex Cloud
        self._check_metadata_availability()
    
    def _load_service_account_data(self):
        """Загрузить данные сервисного аккаунта из файла (только для локальной разработки)."""
        try:
            key_file_path = os.getenv("YANDEX_SERVICE_ACCOUNT_KEY_FILE", "key.json")
            with open(key_file_path, 'r', encoding='utf-8') as f:
                key_data = json.load(f)
            
            self.service_account_id = key_data['service_account_id']
            self.service_account_key_id = key_data['id']
            self.service_account_private_key = key_data['private_key']
            
            print(f"✅ Загружен сервисный аккаунт из файла: {self.service_account_id}")
            
        except Exception as e:
            # Это нормально в контейнере Yandex Cloud - используем метаданные
            self.service_account_id = None
            self.service_account_key_id = None
            self.service_account_private_key = None
    
    def _check_metadata_availability(self) -> bool:
        """Проверить, доступны ли метаданные Yandex Cloud (Serverless Container)."""
        if self._use_metadata is not None:
            return self._use_metadata
        
        try:
            # Пробуем получить IAM токен через метаданные
            headers = {"Metadata-Flavor": "Google"}
            response = requests.get(
                self.METADATA_IAM_TOKEN_URL,
                headers=headers,
                timeout=2
            )
            if response.status_code == 200:
                self._use_metadata = True
                print("✅ Обнаружены метаданные Yandex Cloud - используем автоматическую аутентификацию")
                return True
        except Exception:
            pass
        
        self._use_metadata = False
        return False
    
    def _get_iam_token_from_metadata(self) -> str:
        """Получить IAM токен через метаданные Yandex Cloud (для Serverless Containers)."""
        headers = {"Metadata-Flavor": "Google"}
        response = requests.get(
            self.METADATA_IAM_TOKEN_URL,
            headers=headers,
            timeout=5
        )
        response.raise_for_status()
        result = response.json()
        # Пробуем разные варианты поля с токеном (зависит от формата ответа)
        return result.get("access_token") or result.get("token") or result.get("iamToken")
    
    def _create_jwt_token(self) -> str:
        """Создать JWT токен для аутентификации с сервисным аккаунтом (для локальной разработки)."""
        if not self.service_account_private_key:
            raise ValueError("Сервисный аккаунт не настроен")
            
        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': self.service_account_id,
            'iat': now,
            'exp': now + 3600  # Токен действителен 1 час
        }
        
        token = jwt.encode(
            payload,
            self.service_account_private_key,
            algorithm='PS256',
            headers={'kid': self.service_account_key_id}
        )
        return token
    
    def _get_iam_token_from_jwt(self) -> str:
        """Получить IAM токен через JWT (для локальной разработки)."""
        jwt_token = self._create_jwt_token()
        
        url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
        headers = {"Content-Type": "application/json"}
        data = {"jwt": jwt_token}
        
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        
        result = response.json()
        return result["iamToken"]
    
    def get_iam_token(self) -> str:
        """
        Получить IAM токен.
        Приоритет:
        1. Через метаданные Yandex Cloud (Serverless Containers) - автоматическая аутентификация
        2. Через JWT из файла key.json (локальная разработка)
        """
        # Сначала пробуем получить через метаданные (для контейнеров Yandex Cloud)
        if self._use_metadata:
            try:
                return self._get_iam_token_from_metadata()
            except Exception as e:
                print(f"⚠️ Не удалось получить IAM токен через метаданные: {e}")
                # Fallback к JWT, если есть файл с ключом
                if self.service_account_private_key:
                    return self._get_iam_token_from_jwt()
                raise
        
        # Для локальной разработки используем JWT из файла
        if self.service_account_private_key:
            return self._get_iam_token_from_jwt()
        
        raise ValueError("Не удалось получить IAM токен: метаданные недоступны и файл ключа не найден")
    
    def get_api_key(self) -> str:
        """Получить API ключ"""
        return self.api_key
    
    def is_service_account_configured(self) -> bool:
        """
        Проверить, настроен ли сервисный аккаунт.
        Возвращает True, если:
        - Доступны метаданные Yandex Cloud (Serverless Containers)
        - Или есть файл с ключом сервисного аккаунта (локальная разработка)
        """
        return self._use_metadata or self.service_account_id is not None
