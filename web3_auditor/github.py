import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional

class GitManager:
    def __init__(self):
        self.temp_dir: Optional[str] = None

    def clone_repository(self, repo_url: str) -> str:
        """
        Clones a git repository into a temporary directory.
        
        Args:
            repo_url: The URL to the git repository.
            
        Returns:
            The path to the cloned repository.
        """
        self.temp_dir = tempfile.mkdtemp(prefix="web3_auditor_")
        
        try:
            print(f"Cloning {repo_url} into {self.temp_dir}...")
            # Set environment variables to prevent git from prompting for credentials
            env = os.environ.copy()
            env["GIT_TERMINAL_PROMPT"] = "0"
            
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, self.temp_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )
            return self.temp_dir
        except subprocess.CalledProcessError as e:
            self.cleanup()
            error_msg = e.stderr.decode('utf-8')
            if "terminal prompts disabled" in error_msg or "could not read Username" in error_msg:
                raise RuntimeError("Failed to clone repository: The repository might be private or require authentication. Please ensure the URL is public.")
            elif "not found" in error_msg.lower():
                raise RuntimeError(f"Failed to clone repository: Repository not found at {repo_url}. Please check the URL.")
            raise RuntimeError(f"Failed to clone repository: {error_msg}")

    def cleanup(self):
        """
        Removes the temporary directory if it exists.
        """
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
