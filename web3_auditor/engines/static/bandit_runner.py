from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from web3_auditor.engines.base import AnalyzerResult, BaseEngine, Finding

logger = logging.getLogger(__name__)


class BanditRunner(BaseEngine):
    """Static analysis engine for Python using Bandit."""

    def name(self) -> str:
        return "bandit"

    def analyze(self, files: list[tuple[str, str]], **kwargs) -> AnalyzerResult:
        result = AnalyzerResult()
        bandit_path = shutil.which("bandit")
        if bandit_path is None:
            logger.warning("bandit not found on PATH, skipping")
            return result

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            has_py = False
            for path, content in files:
                if path.endswith(".py"):
                    rel_path = Path(path).name
                    (tmp_path / rel_path).write_text(content)
                    has_py = True
            
            if not has_py:
                return result

            try:
                proc = subprocess.run(
                    [bandit_path, "-r", str(tmp_path), "-f", "json"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                result.raw_output = proc.stdout
                if proc.returncode not in (0, 1):
                    logger.warning("bandit exited with code %d", proc.returncode)
                self._parse_bandit_output(proc.stdout, result)
            except subprocess.TimeoutExpired:
                logger.warning("bandit timed out")
            except Exception:
                logger.exception("bandit runner failed")
        
        return result

    def _parse_bandit_output(self, raw: str, result: AnalyzerResult) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        for issue in data.get("results", []):
            severity_raw: str = issue.get("issue_severity", "MEDIUM")
            result.findings.append(
                Finding(
                    title=issue.get("test_name", "Unknown"),
                    severity=self._map_bandit_severity(severity_raw),
                    category="Security",
                    description=issue.get("issue_text", ""),
                    file_path=issue.get("filename"),
                    line_number=issue.get("line_number"),
                    code_snippet=issue.get("code"),
                    tool=self.name(),
                    confidence=issue.get("issue_confidence", "MEDIUM").lower()
                )
            )

    def _map_bandit_severity(self, severity: str) -> Literal["critical", "high", "medium", "low", "info"]:
        mapping: dict[str, Literal["critical", "high", "medium", "low", "info"]] = {
            "HIGH": "high",
            "MEDIUM": "medium",
            "LOW": "low",
        }
        return mapping.get(severity.upper(), "medium")
