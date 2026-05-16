from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, cast

from google import genai
from pydantic_settings import BaseSettings, SettingsConfigDict

from web3_auditor.engines.base import Finding

logger = logging.getLogger(__name__)


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GEMINI_")
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    max_retries: int = 5
    initial_delay: int = 4
    # Number of full-prompt re-tries when the LLM returns text that can't be
    # parsed as JSON. Cheap insurance against transient formatting drift.
    parse_retries: int = 3


@dataclass
class AuditResult:
    overview: str
    risk_score: float = 0.0
    findings: list[Finding] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    raw_json: str = ""
    # True when the model returned a response that couldn't be parsed even
    # after retries. The API serializes this via `risk_score = -1.0` so the
    # frontend can render a distinct "AUDIT FAILED" state.
    parse_failed: bool = False


SYSTEM_PROMPT = """You are an Elite Web3 Security Auditor specializing in Vyper 0.4+ and Solidity.
Analyze the provided codebase and static analysis findings for vulnerabilities, architectural flaws, and economic risks.

VOICE & TONE:
Professional, technical, editorial. Focus on high-impact vulnerabilities.

VYPER 0.4+ SPECIFICS:
1. Reentrancy: Check for @nonreentrant decorators on any external functions that perform external calls or state changes.
2. Visibility: All functions are private by default in 0.4. Check @external usage.
3. Immutables & Constants: Verify correct usage of `constant` and `immutable`.
4. Storage: In 0.4, storage layout is more explicit. Check for potential collisions or overlaps in complex structures.
5. raw_call: Flag usage of `raw_call` without sufficient return value checks or gas limits.
6. ERC20/721/1155: Ensure compatibility with standard interfaces (snekmate patterns).

INPUT:
You will receive the source code and results from static analysis tools (Slither, Bandit, Vyper compiler).
Your job is to:
1. VALIDATE the static findings (dismiss false positives, escalate critical ones).
2. DISCOVER deep semantic bugs (logic errors, price manipulation, sandwich risks).
3. SYNTHESIZE a comprehensive risk report.

Your response MUST be a single valid JSON object with:
- "overview": High-level technical summary.
- "risk_score": 0.0 to 10.0 (Float).
- "findings": Array of objects:
    - "title": Concise name.
    - "severity": "critical" | "high" | "medium" | "low" | "info".
    - "category": e.g., "Logic Error", "Reentrancy", "Access Control".
    - "description": Detailed technical explanation.
    - "file_path": Full path.
    - "line_number": int.
    - "code_snippet": Relevant code.
    - "recommendation": Specific fix steps.
    - "confidence": "high" | "medium" | "low".
- "improvements": Array of strings for general quality.

Respond ONLY with JSON."""


class AuditEngine:
    """
    Semantic Analysis Engine powered by Gemini 2.5 Flash.
    
    This engine acts as the 'brain' of the audit. It takes the source code 
    and the results from the static analysis tools (VyperRunner, Slither, etc.) 
    to perform a deep, contextual security audit.
    """
    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or LLMSettings()
        self.client = genai.Client(api_key=self.settings.api_key)

    def analyze_codebase(
        self,
        files: list[tuple[str, str]],
        static_findings: list[Finding] | None = None
    ) -> AuditResult:
        """
        Synthesizes a full security report.

        Args:
            files: List of (filename, content) tuples.
            static_findings: Findings from SAST tools to be validated by the AI.
        """
        # Build the context string that will be sent to the LLM.
        # This includes source code and SAST results.
        context = self._build_context(files, static_findings)
        prompt = f"### CONTEXT START ###\n{context}\n### CONTEXT END ###\n\n{SYSTEM_PROMPT}"

        # Try up to N times to extract structured JSON. Each attempt sends the
        # prompt fresh — LLM stochasticity is the dominant failure mode here, so
        # a single retry often unblocks an audit that would otherwise show a
        # misleading "10/10 STABLE" fallback (see #parse-failure rendering).
        parsed: dict[str, Any] | None = None
        raw_text = ""
        for attempt in range(self.settings.parse_retries):
            raw_text = self._send_with_retry(prompt)
            parsed = self._parse_json(raw_text)
            if parsed is not None:
                break
            logger.warning(
                "LLM response could not be parsed as JSON on attempt %d/%d "
                "(response length: %d chars). Retrying...",
                attempt + 1, self.settings.parse_retries, len(raw_text),
            )

        if not parsed:
            # All retries exhausted. Return a fallback with `risk_score = -1.0`
            # as a sentinel so the frontend can render a clear "AUDIT FAILED"
            # state instead of misinterpreting the default 0.0 as a perfect score.
            return AuditResult(
                overview=(
                    "The AI returned a response that could not be parsed as "
                    "structured JSON, even after retries. The audit could not "
                    "be completed — please retry, or inspect the raw model "
                    "output for partial findings."
                ),
                risk_score=-1.0,
                parse_failed=True,
                raw_json=raw_text,
            )
            
        # Map the AI-generated findings into our Finding dataclass.
        findings = [
            Finding(
                title=f.get("title", "Untitled"),
                severity=f.get("severity", "info"),
                category=f.get("category", "General"),
                description=f.get("description", ""),
                file_path=f.get("file_path"),
                line_number=f.get("line_number"),
                code_snippet=f.get("code_snippet"),
                recommendation=f.get("recommendation"),
                tool="ai-semantic-audit",
                confidence=f.get("confidence", "medium")
            )
            for f in parsed.get("findings", [])
        ]
        
        return AuditResult(
            overview=parsed.get("overview", ""),
            risk_score=float(parsed.get("risk_score", 0.0)),
            findings=findings,
            improvements=parsed.get("improvements", []),
            raw_json=raw_text
        )

    def _build_context(self, files: list[tuple[str, str]], static_findings: list[Finding] | None) -> str:
        """
        Formats the codebase and static findings into a structured string for the LLM.
        """
        parts = []
        
        # Step 1: Add the actual Source Code
        parts.append("## SOURCE CODE")
        for path, content in files:
            ext = path.split(".")[-1] if "." in path else ""
            parts.append(f"FILE: {path}\n```{ext}\n{content}\n```")
            
        # Step 2: Add findings from static tools (Slither, Vyper, etc.)
        # This allows the AI to verify or escalate issues found by automated tools.
        if static_findings:
            parts.append("## STATIC ANALYSIS FINDINGS")
            for f in static_findings:
                parts.append(
                    f"- [{f.severity.upper()}] {f.title} in {f.file_path}:{f.line_number}\n"
                    f"  Description: {f.description}\n"
                    f"  Tool: {f.tool}"
                )
                
        return "\n\n".join(parts)

    def _send_with_retry(self, prompt: str) -> str:
        """
        Handles communication with the Gemini API with exponential backoff.
        """
        delay = self.settings.initial_delay
        for i in range(self.settings.max_retries):
            try:
                chat = self.client.chats.create(model=self.settings.model)
                response = chat.send_message(prompt)
                return cast(str, response.text)
            except Exception as e:
                if i == self.settings.max_retries - 1:
                    # If we've exhausted retries, raise the error to the caller.
                    raise
                logger.warning("LLM API Error (Attempt %d): %s. Retrying in %ds...", i+1, e, delay)
                time.sleep(delay)
                delay *= 2
        return ""

    def _parse_json(self, text: str) -> dict[str, Any] | None:
        """
        Extract a JSON object from the LLM's response.

        The model is asked to return strict JSON but in practice may wrap it
        in markdown code fences, prefix it with prose, or append a trailing
        comment. This parser tries four strategies in order of cost:

          1. Parse the entire response as JSON.
          2. Strip a leading ```json or ``` fence and try again.
          3. Find every balanced `{...}` substring in the response (using a
             stack-based scanner that respects strings and escapes) and try to
             parse each candidate, largest first. The first one that yields a
             dict with `risk_score` or `findings` is returned.

        Returns the parsed dict on success, or ``None`` if every strategy fails.
        """
        if not text:
            return None
        text = text.strip()

        # Strategy 1: whole-text parse.
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return cast(dict[str, Any], obj)
        except json.JSONDecodeError:
            pass

        # Strategy 2: strip markdown code fences.
        fenced = text
        if "```json" in fenced:
            fenced = fenced.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in fenced:
            fenced = fenced.split("```", 1)[1].split("```", 1)[0]
        fenced = fenced.strip()
        if fenced and fenced is not text:
            try:
                obj = json.loads(fenced)
                if isinstance(obj, dict):
                    return cast(dict[str, Any], obj)
            except json.JSONDecodeError:
                pass

        # Strategy 3: scan for balanced `{...}` substrings.
        candidates = self._find_balanced_json_objects(text)
        candidates.sort(key=len, reverse=True)
        for candidate in candidates:
            try:
                obj = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and (
                "risk_score" in obj or "findings" in obj or "overview" in obj
            ):
                return cast(dict[str, Any], obj)

        logger.error(
            "AI returned invalid JSON after fence-strip and balanced-brace scan. "
            "Length: %d, first 200 chars: %r",
            len(text), text[:200],
        )
        return None

    @staticmethod
    def _find_balanced_json_objects(text: str) -> list[str]:
        """
        Return every balanced `{...}` substring in `text`, respecting JSON
        string syntax (so braces inside string literals don't confuse the
        depth counter).
        """
        results: list[str] = []
        i = 0
        n = len(text)
        while i < n:
            if text[i] != "{":
                i += 1
                continue
            depth = 0
            in_string = False
            escape = False
            j = i
            while j < n:
                ch = text[j]
                if in_string:
                    if escape:
                        escape = False
                    elif ch == "\\":
                        escape = True
                    elif ch == '"':
                        in_string = False
                elif ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        results.append(text[i:j + 1])
                        break
                j += 1
            i = j + 1
        return results

