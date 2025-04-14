import os
from pathlib import Path
from dotenv import load_dotenv

def load_api_keys():
    """
    Попытка загрузить переменные окружения из файлов .env в разных местах:
    1. Текущая директория
    2. Родительская директория (на один уровень выше)
    3. Директория на два уровня выше
    
    Returns:
        dict: Словарь, содержащий загруженные ключи API
    """
    # Получаем текущую директорию
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    
    # Определяем пути для поиска файлов .env
    env_paths = [
        current_dir / '.env',                # Текущая директория
        current_dir.parent / '.env',         # На один уровень выше
        current_dir.parent.parent / '.env',  # На два уровня выше
    ]
    
    # Пробуем загрузить из каждого пути
    found_env_files = []
    for env_path in env_paths:
        if env_path.exists():
            print(f"Загрузка переменных окружения из {env_path}")
            load_dotenv(dotenv_path=env_path)
            found_env_files.append(str(env_path))
    
    if not found_env_files:
        print("Предупреждение: Файл .env не найден ни в одном из ожидаемых мест")
    else:
        print(f"Найдены и загружены файлы .env: {', '.join(found_env_files)}")
    
    # Возвращаем словарь с необходимыми переменными окружения
    return {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'YOUTUBE_API_KEY': os.getenv('YOUTUBE_API_KEY'),
    }