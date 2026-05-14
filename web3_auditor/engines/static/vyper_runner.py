from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from web3_auditor.engines.base import AnalyzerResult, BaseEngine, Finding


class VyperRunner(BaseEngine):
    """
    Static analysis engine specifically tuned for Vyper 0.4+.
    
    This runner performs two main tasks:
    1. It uses the actual 'vyper' compiler to validate syntax and types.
    2. It applies security heuristics (regex) to catch common Vyper pitfalls.
    """

    def name(self) -> str:
        return "vyper-static"

    def analyze(self, files: list[tuple[str, str]], **kwargs) -> AnalyzerResult:
        """
        Orchestrates the analysis of Vyper files.
        Processes each file through the compiler and then through heuristic checks.
        """
        findings: list[Finding] = []
        raw_outputs = []

        for path, content in files:
            # We only care about Vyper files here
            if not path.endswith(".vy"):
                continue

            # Step 1: Run the actual Vyper compiler to ensure the code is valid.
            # This catches syntax errors, type mismatches, and 0.4+ breaking changes.
            compiler_findings, compiler_raw = self._run_compiler_check(path, content)
            findings.extend(compiler_findings)
            raw_outputs.append(compiler_raw)

            # Step 2: Run heuristic checks for security red flags.
            # This is where we look for missing decorators or dangerous patterns.
            heuristic_findings = self._run_heuristic_checks(path, content)
            findings.extend(heuristic_findings)

        return AnalyzerResult(findings=findings, raw_output="\n---\n".join(raw_outputs))

    def _run_compiler_check(self, path: str, content: str) -> tuple[list[Finding], str]:
        """
        Saves the content to a temp file and runs 'vyper' against it.
        If compilation fails, we report it as a CRITICAL finding.
        """
        with tempfile.NamedTemporaryFile(suffix=".vy", mode="w", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Running the compiler with capture_output to get error messages
            result = subprocess.run(
                ["vyper", tmp_path],
                capture_output=True,
                text=True,
                check=False
            )
            
            if result.returncode != 0:
                # The compiler failed. This is usually a major issue in the contract structure.
                return [Finding(
                    title="Compiler Error",
                    severity="critical",
                    category="Syntax",
                    description=f"Vyper compiler failed to process the contract:\n{result.stderr.strip()}",
                    file_path=path,
                    tool=self.name(),
                    confidence="high"
                )], result.stderr
            
            return [], "Compilation successful"
        finally:
            # Clean up the temp file to keep the system tidy
            Path(tmp_path).unlink(missing_ok=True)

    def _run_heuristic_checks(self, path: str, content: str) -> list[Finding]:
        """
        Performs pattern matching for known Vyper security risks.
        Focuses on reentrancy, selfdestruct, and sensitive data visibility.
        """
        findings = []
        
        # Check 1: Missing @nonreentrant on state-changing calls.
        # In Vyper 0.4+, protection is explicit. If we see a raw_call but no lock, it's a risk.
        external_funcs = re.findall(r"@external\n(?:    .*\n)*def\s+(\w+)\(.*\):", content)
        for func in external_funcs:
            # Heuristic: Check if the function uses raw_call but lacks the reentrancy lock
            if "raw_call" in content and "@nonreentrant" not in content:
                 findings.append(Finding(
                    title="Potential Missing Reentrancy Lock",
                    severity="high",
                    category="Reentrancy",
                    description=f"Function '{func}' performs a raw_call but does not use the @nonreentrant decorator. "
                                "This is dangerous if the function modifies state.",
                    file_path=path,
                    tool=self.name(),
                    confidence="medium",
                    recommendation="Apply @nonreentrant('lock_name') to any external function that makes external calls."
                ))

        # Check 2: selfdestruct usage.
        # While sometimes necessary, selfdestruct is a common target for governance attacks.
        if "selfdestruct" in content:
            findings.append(Finding(
                title="Use of selfdestruct",
                severity="critical",
                category="Access Control",
                description="The 'selfdestruct' opcode was detected. This can lead to permanent loss of contract state.",
                file_path=path,
                tool=self.name(),
                confidence="high",
                recommendation="Ensure selfdestruct is only callable by the owner and consider using 'stop_contract' patterns instead."
            ))

        # Check 3: Sensitive variable naming in public storage.
        # Vyper public variables generate getters. Secrets should never be public.
        if re.search(r"\w+: public\(.*\)", content) and re.search(r"password|secret|key", content, re.I):
             findings.append(Finding(
                title="Sensitive Data Visibility",
                severity="medium",
                category="Information Exposure",
                description="Storage variables containing 'password' or 'secret' should not be marked as 'public'.",
                file_path=path,
                tool=self.name(),
                confidence="low",
                recommendation="Mark sensitive storage variables as private and manage access via restricted functions."
            ))

        return findings

