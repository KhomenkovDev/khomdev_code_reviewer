import sys
from PyQt6.QtWidgets import QApplication
from web3_auditor.gui import AICodeReviewerGUI

def main():
    """Entry point for the AI Code Reviewer application."""
    app = QApplication(sys.argv)
    window = AICodeReviewerGUI()
    window.show()
    
    # Handle clean exit
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
