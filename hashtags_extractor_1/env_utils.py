import os
from pathlib import Path
from dotenv import load_dotenv

def load_api_keys():
    """
    Attempts to load environment variables from .env files in different locations:
    1. Current directory
    2. Parent directory (one level up)
    3. Two levels up directory
    
    Returns:
        dict: Dictionary containing the loaded API keys
    """
    # Get current directory
    current_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    
    # Define paths to search for .env files
    env_paths = [
        current_dir / '.env',                # Current directory
        current_dir.parent / '.env',         # One level up
        current_dir.parent.parent / '.env',  # Two levels up
    ]
    
    # Try to load from each path
    found_env_files = []
    for env_path in env_paths:
        if env_path.exists():
            print(f"Loading environment variables from {env_path}")
            load_dotenv(dotenv_path=env_path)
            found_env_files.append(str(env_path))
    
    if not found_env_files:
        print("Warning: No .env file found in any of the expected locations")
    else:
        print(f"Found and loaded .env files: {', '.join(found_env_files)}")
    
    # Return dictionary with necessary environment variables
    return {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    }