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
            subprocess.run(
                ["git", "clone", repo_url, self.temp_dir],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            return self.temp_dir
        except subprocess.CalledProcessError as e:
            self.cleanup()
            raise RuntimeError(f"Failed to clone repository: {e.stderr.decode('utf-8')}")

    def cleanup(self):
        """
        Removes the temporary directory if it exists.
        """
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
