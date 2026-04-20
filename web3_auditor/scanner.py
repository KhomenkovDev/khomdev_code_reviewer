import os
from pathlib import Path
from typing import List, Tuple

def get_source_files(target_path: str) -> List[Tuple[str, str]]:
    """
    Scans the target path for source files (.py, .sol, .js) and returns a list of (file_path, file_content).
    
    Args:
        target_path: A string path to a file or directory.
        
    Returns:
        List of tuples containing (file_path, code_content).
    """
    target = Path(target_path).resolve()
    source_files = []
    
    ignore_dirs = {'.git', 'venv', 'env', '.env', 'node_modules', '__pycache__', '.pytest_cache'}
    valid_extensions = {'.py', '.sol', '.js'}
    
    if target.is_file():
        if target.suffix in valid_extensions:
            _add_file(target, source_files)
    elif target.is_dir():
        for root, dirs, files in os.walk(target):
            # Modify dirs in-place to skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]
            
            for file in files:
                ext = Path(file).suffix
                if ext in valid_extensions:
                    file_path = Path(root) / file
                    _add_file(file_path, source_files)
    else:
        raise ValueError(f"Target path does not exist or is not a valid file/directory: {target_path}")
        
    return source_files

def _add_file(file_path: Path, file_list: List[Tuple[str, str]]):
    try:
        content = file_path.read_text(encoding='utf-8')
        file_list.append((str(file_path), content))
    except Exception as e:
        print(f"Warning: Could not read {file_path}. Error: {e}")
