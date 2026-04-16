import os
import time
from google import genai
from typing import List, Tuple, Optional

class LLMChatManager:
    def __init__(self):
        # We will initialize the client dynamically when needed to grab the env var easily
        self.client: Optional[genai.Client] = None
        self.chat_session = None

    def _send_with_retry(self, message: str, retries: int = 4) -> str:
        """Helper method to send a message with exponential backoff on 503/disconnect errors."""
        delay = 2
        for attempt in range(retries):
            try:
                response = self.chat_session.send_message(message)
                return response.text
            except Exception as e:
                error_str = str(e).lower()
                is_transient = any(term in error_str for term in ["503", "disconnected", "unavailable", "demand", "500"])
                if is_transient and attempt < retries - 1:
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
            context += f"### FILE: {file_path} ###\n```python\n{content}\n```\n\n"

        prompt = f"""
{context}

You are an expert Python code reviewer. Please review the code provided above.
Your task is to provide:
1. An overview of what the codebase does.
2. Suggestions for further steps, improvements, and better ways to implement some blocks.
3. Cleaned, more advanced, and Pythonic versions of critical files.

Please structure your response strictly in Markdown format with the following headings:
## Codebase Overview
## Suggestions for Improvement
## Upgraded Code Examples
"""
        return self._send_with_retry(prompt)

    def send_message(self, message: str) -> str:
        """
        Sends a follow-up message to the chat session.
        """
        if not self.chat_session:
            raise RuntimeError("No active chat session.")
            
        return self._send_with_retry(message)
