import sys
import os
import markdown
from typing import List, Tuple
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTextBrowser, QTextEdit, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from .scanner import get_python_files
from .github import GitManager
from .llm_chat import LLMChatManager

class LoadWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, mode, target, llm_manager):
        super().__init__()
        self.mode = mode
        self.target = target
        self.llm_manager = llm_manager
        self.git_manager = GitManager()

    def run(self):
        try:
            files = []
            if self.mode == "github":
                repo_path = self.git_manager.clone_repository(self.target)
                files = get_python_files(repo_path)
            elif self.mode == "local":
                files = get_python_files(self.target)
            
            if not files:
                self.error.emit("No Python files found in the target.")
                return

            review_output = self.llm_manager.start_session(files)
            self.finished.emit(review_output)
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.git_manager.cleanup()

class ChatWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, message, llm_manager):
        super().__init__()
        self.message = message
        self.llm_manager = llm_manager

    def run(self):
        try:
            response = self.llm_manager.send_message(self.message)
            self.finished.emit(response)
        except Exception as e:
            self.error.emit(str(e))

class DropLabel(QLabel):
    fileDropped = pyqtSignal(str)

    def __init__(self, text):
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #aaa;
                border-radius: 5px;
                padding: 20px;
                background-color: #2b2b2b;
                color: #ccc;
            }
        """)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self.fileDropped.emit(file_path)

class AICodeReviewerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Code Reviewer")
        self.resize(900, 700)
        self.setStyleSheet("background-color: #1e1e1e; color: #ffffff;")
        
        # Managers
        from dotenv import load_dotenv
        # Ensure we load the env file correctly located right next to this project
        if getattr(sys, 'frozen', False):
            env_path = os.path.join(sys._MEIPASS, '.env')
        else:
            env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        load_dotenv(env_path)
        
        self.llm_manager = LLMChatManager()
        
        self.setup_ui()
        
    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # TOP AREA: Inputs
        top_layout = QHBoxLayout()
        
        self.github_input = QLineEdit()
        self.github_input.setPlaceholderText("Paste GitHub Repository URL here...")
        self.github_input.setStyleSheet("padding: 8px; background-color: #333; border: 1px solid #555;")
        
        self.load_btn = QPushButton("Load GitHub")
        self.load_btn.setStyleSheet("padding: 8px; background-color: #007acc; color: white;")
        self.load_btn.clicked.connect(self.load_github)
        
        top_layout.addWidget(self.github_input)
        top_layout.addWidget(self.load_btn)
        
        # Drag Drop Area
        drop_layout = QHBoxLayout()
        self.drop_label = DropLabel("Drag and Drop Local Folder or .py File Here")
        self.drop_label.fileDropped.connect(self.load_local_file)
        
        browse_layout = QVBoxLayout()
        self.browse_file_btn = QPushButton("Browse File...")
        self.browse_dir_btn = QPushButton("Browse Folder...")
        self.browse_file_btn.setStyleSheet("padding: 10px; background-color: #4CAF50; color: white; border-radius: 5px;")
        self.browse_dir_btn.setStyleSheet("padding: 10px; background-color: #008CBA; color: white; border-radius: 5px;")
        self.browse_file_btn.clicked.connect(self.browse_file)
        self.browse_dir_btn.clicked.connect(self.browse_dir)
        
        browse_layout.addWidget(self.browse_file_btn)
        browse_layout.addWidget(self.browse_dir_btn)
        
        drop_layout.addWidget(self.drop_label)
        drop_layout.addLayout(browse_layout)

        
        # CHAT AREA
        self.chat_display = QTextBrowser()
        self.chat_display.setStyleSheet("background-color: #252526; padding: 10px; font-size: 14px;")
        self.chat_display.setOpenExternalLinks(True)
        self.append_to_chat("System", "Welcome! Drag a file/folder or paste a GitHub URL to begin the code review.")
        
        # INPUT AREA
        bottom_layout = QHBoxLayout()
        self.message_input = QTextEdit()
        self.message_input.setFixedHeight(60)
        self.message_input.setPlaceholderText("Ask AI about the code or request upgrades...")
        self.message_input.setStyleSheet("background-color: #333; padding: 5px;")
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedHeight(60)
        self.send_btn.setStyleSheet("background-color: #007acc; padding: 10px;")
        self.send_btn.clicked.connect(self.send_message)
        
        bottom_layout.addWidget(self.message_input)
        bottom_layout.addWidget(self.send_btn)
        
        # Assembly
        layout.addLayout(top_layout)
        layout.addLayout(drop_layout)
        layout.addWidget(self.chat_display)
        layout.addLayout(bottom_layout)

    def load_github(self):
        url = self.github_input.text().strip()
        if not url:
            return
        self.start_loading("github", url)

    def load_local_file(self, file_path):
        self.start_loading("local", file_path)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Python File", "", "Python Files (*.py);;All Files (*)")
        if path:
            self.load_local_file(path)
            
    def browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder", "")
        if path:
            self.load_local_file(path)

    def start_loading(self, mode, target):
        self.append_to_chat("System", f"Loading code from {target}... Please wait (This might take a minute).")
        self.load_btn.setEnabled(False)
        
        self.load_worker = LoadWorker(mode, target, self.llm_manager)
        self.load_worker.finished.connect(self.on_load_finished)
        self.load_worker.error.connect(self.on_error)
        self.load_worker.start()

    def on_load_finished(self, review_text):
        self.load_btn.setEnabled(True)
        self.append_to_chat("AI Reviewer", review_text)

    def send_message(self):
        msg = self.message_input.toPlainText().strip()
        if not msg:
            return
        
        if not self.llm_manager.chat_session:
            QMessageBox.warning(self, "Warning", "Please load code (GitHub or Local File) first before chatting.")
            return

        self.append_to_chat("You", msg)
        self.message_input.clear()
        self.send_btn.setEnabled(False)
        
        self.chat_worker = ChatWorker(msg, self.llm_manager)
        self.chat_worker.finished.connect(self.on_chat_finished)
        self.chat_worker.error.connect(self.on_error)
        self.chat_worker.start()

    def on_chat_finished(self, response_text):
        self.send_btn.setEnabled(True)
        self.append_to_chat("AI Reviewer", response_text)

    def on_error(self, error_msg):
        self.load_btn.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.append_to_chat("Error", f"<font color='red'>{error_msg}</font>")

    def append_to_chat(self, sender, text):
        html_text = markdown.markdown(text, extensions=['fenced_code', 'codehilite'])
        
        color = "#569cd6" if sender == "You" else "#4ec9b0"
        if sender == "System" or sender == "Error":
             color = "#d4d4d4"
             
        message = f"<b><font size='4' color='{color}'>{sender}:</font></b><br>{html_text}<br><hr>"
        self.chat_display.append(message)
