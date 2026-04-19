import os
from pathlib import Path
from typing import List, Tuple

def get_python_files(target_path: str) -> List[Tuple[str, str]]:
    """
    Scans the target path for Python files and returns a list of (file_path, file_content).
    
    Args:
        target_path: A string path to a file or directory.
        
    Returns:
        List of tuples containing (file_path, code_content).
    """
    target = Path(target_path).resolve()
    python_files = []
    
    ignore_dirs = {'.git', 'venv', 'env', '.env', 'node_modules', '__pycache__', '.pytest_cache'}
    
    if target.is_file():
        if target.suffix == '.py':
            _add_file(target, python_files)
    elif target.is_dir():
        for root, dirs, files in os.walk(target):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = Path(root) / file
                    _add_file(file_path, python_files)
    else:
        raise ValueError(f"Target path does not exist or is not a valid file/directory: {target_path}")
        
    return python_files

def _add_file(file_path: Path, file_list: List[Tuple[str, str]]):
    try:
        content = file_path.read_text(encoding='utf-8')
        file_list.append((str(file_path), content))
    except Exception as e:
        print(f"Warning: Could not read {file_path}. Error: {e}")
