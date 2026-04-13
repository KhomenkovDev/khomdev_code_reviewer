import sys
from PyQt6.QtWidgets import QApplication
from ai_reviewer.gui import AICodeReviewerGUI

def main():
    app = QApplication(sys.argv)
    window = AICodeReviewerGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
