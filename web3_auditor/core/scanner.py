from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

VALID_EXTENSIONS = {".py", ".sol", ".js", ".ts", ".vy"}
IGNORE_DIRS = {".git", "venv", "env", ".env", "node_modules", "__pycache__", ".pytest_cache", ".venv", "dist", "build"}
MAX_FILE_SIZE = 500_000  # 500KB


class CodeScanner:
    @staticmethod
    def get_source_files(target_path: str | Path) -> list[tuple[str, str]]:
        target = Path(target_path).resolve()
        source_files: list[tuple[str, str]] = []
        
        if target.is_file():
            if target.suffix in VALID_EXTENSIONS:
                CodeScanner._read_and_add(target, source_files)
        elif target.is_dir():
            for root, dirs, files in os.walk(target):
                # In-place filter directories
                dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
                for file in sorted(files):
                    file_path = Path(root) / file
                    if file_path.suffix in VALID_EXTENSIONS:
                        CodeScanner._read_and_add(file_path, source_files)
        
        return source_files

    @staticmethod
    def _read_and_add(file_path: Path, file_list: list[tuple[str, str]]) -> None:
        try:
            # Check size
            if file_path.stat().st_size > MAX_FILE_SIZE:
                logger.warning("Skipping %s: File too large (%d bytes)", file_path, file_path.stat().st_size)
                return
                
            content = file_path.read_text(encoding="utf-8")
            file_list.append((str(file_path), content))
        except Exception as e:
            logger.warning("Failed to read %s: %s", file_path, e)

