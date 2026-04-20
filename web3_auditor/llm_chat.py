import os
import time
from google import genai
from typing import List, Tuple, Optional

class LLMChatManager:
    def __init__(self):
        # We will initialize the client dynamically when needed to grab the env var easily
        self.client: Optional[genai.Client] = None
        self.chat_session = None

    def _send_with_retry(self, message: str, retries: int = 6) -> str:
        """Helper method to send a message with exponential backoff on 503/disconnect errors."""
        delay = 4
        for attempt in range(retries):
            try:
                response = self.chat_session.send_message(message)
                return response.text
            except Exception as e:
                error_str = str(e).lower()
                is_transient = any(term in error_str for term in ["503", "disconnected", "unavailable", "demand", "500"])
                if is_transient and attempt < retries - 1:
                    print(f"Transient error: {error_str}. Retrying in {delay}s... (Attempt {attempt + 1}/{retries})")
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                    continue
                raise e

    def start_session(self, files: List[Tuple[str, str]]) -> str:
        """
        Starts a new chat session with the provided code context and returns the initial review.
        """
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        
        self.client = genai.Client(api_key=api_key)
        self.chat_session = self.client.chats.create(model='gemini-2.5-flash')

        # Construct the massive context string
        context = "Here are the files for the codebase we will be discussing:\n\n"
        for file_path, content in files:
            ext = file_path.split('.')[-1] if '.' in file_path else ''
            context += f"### FILE: {file_path} ###\n```{ext}\n{content}\n```\n\n"

        prompt = f"""
{context}

You are an expert Web3 Security Auditor and Senior Python Engineer. Please review the codebase provided above.
Your task is to provide:
1. An overview of what the codebase does (Smart Contracts, Logic, Infrastructure).
2. Deep Security Audit: Identify vulnerabilities (e.g., Reentrancy, Overflow, Logic errors in Sol or Security flaws in Python).
3. Suggestions for Improvement: Optimization (Gas optimization for Solidity, Pythonic improvements).
4. Upgraded Code Examples: Provide more secure or efficient versions of critical functions.

Please structure your response strictly in Markdown format with the following headings:
## Codebase & Architecture Overview
## Security Audit Results
## Performance & Logic Improvements
## Secure Code Upgrades
"""
        return self._send_with_retry(prompt)

    def send_message(self, message: str) -> str:
        """
        Sends a follow-up message to the chat session.
        """
        if not self.chat_session:
            raise RuntimeError("No active chat session.")
            
        return self._send_with_retry(message)
