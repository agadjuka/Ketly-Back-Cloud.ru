"""
Сервис для чтения данных об услугах
Поддерживает чтение из файла проекта и из облачного хранилища
"""
import os
import json
from pathlib import Path
from typing import Dict, Optional
from functools import lru_cache


class ServicesDataLoader:
    """Загрузчик данных об услугах с поддержкой разных источников"""
    
    def __init__(self):
        """Инициализация загрузчика"""
        self.data_source = os.getenv('SERVICES_DATA_SOURCE', 'file')  # 'file' или 'storage'
        self.file_path = os.getenv('SERVICES_FILE_PATH', 'services.json')
        self.storage_bucket = os.getenv('YC_BUCKET_NAME')
        self.storage_path = os.getenv('SERVICES_STORAGE_PATH', 'services.json')
    
    @lru_cache(maxsize=1)
    def load_data(self) -> Dict:
        """
        Загрузка данных об услугах
        
        Returns:
            Словарь с данными об услугах
            
        Raises:
            FileNotFoundError: если файл не найден
            json.JSONDecodeError: если ошибка парсинга JSON
        """
        if self.data_source == 'storage':
            return self._load_from_storage()
        else:
            return self._load_from_file()
    
    def _load_from_file(self) -> Dict:
        """Загрузка из файла проекта"""
        project_root = Path(__file__).parent.parent.parent.parent
        file_path = project_root / self.file_path
        
        if not file_path.exists():
            raise FileNotFoundError(f"Файл {file_path} не найден")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_from_storage(self) -> Dict:
        """Загрузка из Object Storage"""
        try:
            import boto3
        except ImportError:
            raise ImportError("Для работы с Object Storage установите boto3: pip install boto3")
        
        session = boto3.Session(
            aws_access_key_id=os.getenv('YC_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('YC_SECRET_ACCESS_KEY')
        )
        s3 = session.client(
            service_name='s3',
            endpoint_url='https://storage.yandexcloud.net'
        )
        
        if not self.storage_bucket:
            raise ValueError("Не задан YC_BUCKET_NAME для работы с хранилищем")
        
        response = s3.get_object(Bucket=self.storage_bucket, Key=self.storage_path)
        content = response['Body'].read().decode('utf-8')
        return json.loads(content)
    
    def reload(self):
        """Принудительная перезагрузка данных (очистка кэша)"""
        self.load_data.cache_clear()


# Глобальный экземпляр загрузчика
_data_loader = ServicesDataLoader()

