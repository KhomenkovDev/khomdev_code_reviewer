from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Finding:
    title: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    category: str
    description: str
    file_path: str | None = None
    line_number: int | None = None
    code_snippet: str | None = None
    recommendation: str | None = None
    tool: str = "unknown"
    confidence: Literal["high", "medium", "low"] = "medium"
    cwe: str | None = None


@dataclass
class AnalyzerResult:
    findings: list[Finding] = field(default_factory=list)
    raw_output: str = ""


class BaseEngine:
    """Base class for all analysis engines (Static, Dynamic, AI)."""
    
    def name(self) -> str:
        raise NotImplementedError
        
    def analyze(self, files: list[tuple[str, str]], **kwargs) -> AnalyzerResult:
        raise NotImplementedError

