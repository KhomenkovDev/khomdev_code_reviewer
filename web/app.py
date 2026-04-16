import os
import uuid
import uuid
import tempfile
import markdown
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from dotenv import load_dotenv

from ai_reviewer.github import GitManager
from ai_reviewer.scanner import get_python_files
from ai_reviewer.llm_chat import LLMChatManager

# Load env variables
load_dotenv()

app = FastAPI(title="KhomDev Code Reviewer Web App")

# Mount static and templates (handle paths elegantly for execution anywhere)
BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

# In-memory session store for lightweight cloud usage
sessions: Dict[str, LLMChatManager] = {}

def get_session(session_id: str) -> LLMChatManager:
    if session_id not in sessions:
        sessions[session_id] = LLMChatManager()
    return sessions[session_id]

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main frontend UI."""
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/load-github")
async def load_github(repo_url: str = Form(...)):
    """Clone a GitHub repository, scan for Python, and initialize review."""
    session_id = str(uuid.uuid4())
    manager = get_session(session_id)
    git_manager = GitManager()
    
    try:
        repo_path = git_manager.clone_repository(repo_url)
        files = get_python_files(repo_path)
        
        if not files:
            git_manager.cleanup()
            return JSONResponse({"status": "error", "message": "No Python files found."}, status_code=400)
            
        review_output = manager.start_session(files)
        
        # Render the markdown securely
        html_review = markdown.markdown(review_output, extensions=['fenced_code', 'codehilite'])
        return {"status": "success", "session_id": session_id, "html_review": html_review, "raw_review": review_output}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        git_manager.cleanup()

@app.post("/api/load-local")
async def load_local(files: List[UploadFile] = File(...)):
    """Upload local files, initialize review."""
    session_id = str(uuid.uuid4())
    manager = get_session(session_id)
    
    temp_dir = tempfile.mkdtemp(prefix="ai_reviewer_web_upload_")
    python_files = []
    
    try:
        for uf in files:
            # We only process python files
            if uf.filename.endswith(".py"):
                content = await uf.read()
                try:
                    text_content = content.decode("utf-8")
                    python_files.append((uf.filename, text_content))
                except UnicodeDecodeError:
                    continue # Skip binary
                    
        if not python_files:
            shutil.rmtree(temp_dir)
            return JSONResponse({"status": "error", "message": "No Python files found in upload."}, status_code=400)
            
        review_output = manager.start_session(python_files)
        html_review = markdown.markdown(review_output, extensions=['fenced_code', 'codehilite'])
        
        return {"status": "success", "session_id": session_id, "html_review": html_review, "raw_review": review_output}
        
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@app.post("/api/chat")
async def chat(session_id: str = Form(...), message: str = Form(...)):
    """Send follow-up chat messages."""
    if not session_id or session_id not in sessions:
         return JSONResponse({"status": "error", "message": "Session expired or invalid. Please reload the code."}, status_code=400)
         
    manager = sessions[session_id]
    
    try:
        response_output = manager.send_message(message)
        html_response = markdown.markdown(response_output, extensions=['fenced_code', 'codehilite'])
        return {"status": "success", "html_response": html_response, "raw_response": response_output}
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), reload=True)
