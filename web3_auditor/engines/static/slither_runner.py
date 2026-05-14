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


class SlitherRunner(BaseEngine):
    """Static analysis engine for Solidity/Vyper using Slither."""

    def name(self) -> str:
        return "slither"

    def analyze(self, files: list[tuple[str, str]], **kwargs) -> AnalyzerResult:
        # Slither usually runs on a directory, so we create a temp dir
        result = AnalyzerResult()
        slither_path = shutil.which("slither")
        if slither_path is None:
            logger.warning("slither not found on PATH, skipping")
            return result

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            for path, content in files:
                # Recreate file structure in temp dir if needed, 
                # but for simple audits we just drop them in
                rel_path = Path(path).name
                (tmp_path / rel_path).write_text(content)

            try:
                proc = subprocess.run(
                    [slither_path, str(tmp_path), "--json", "-"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                result.raw_output = proc.stdout
                if proc.returncode != 0:
                    logger.warning("slither exited with code %d", proc.returncode)
                self._parse_slither_output(proc.stdout, result)
            except subprocess.TimeoutExpired:
                logger.warning("slither timed out")
            except Exception:
                logger.exception("slither runner failed")
        
        return result

    def _parse_slither_output(self, raw: str, result: AnalyzerResult) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
            
        results_data = data.get("results", {}).get("detectors", [])
        for detector in results_data:
            severity_raw: str = detector.get("impact", "medium")
            elements = detector.get("elements", [])
            file_path = None
            line_number = None
            if elements:
                source = elements[0].get("source_mapping", {})
                # Try to map back to original path if possible, otherwise use filename
                file_path = source.get("filename_relative") or source.get("filename")
                line_number = source.get("lines", [None])[0]
                
            result.findings.append(
                Finding(
                    title=detector.get("check", "Unknown"),
                    severity=self._map_slither_severity(severity_raw),
                    category=detector.get("impact", "unknown"),
                    description=detector.get("description", ""),
                    file_path=file_path,
                    line_number=line_number,
                    recommendation=detector.get("recommendation"),
                    tool=self.name(),
                    confidence=detector.get("confidence", "medium").lower()
                )
            )

    def _map_slither_severity(self, impact: str) -> Literal["critical", "high", "medium", "low", "info"]:
        mapping: dict[str, Literal["critical", "high", "medium", "low", "info"]] = {
            "high": "high",
            "medium": "medium",
            "low": "low",
            "informational": "info",
            "optimization": "info",
        }
        return mapping.get(impact.lower(), "medium")
