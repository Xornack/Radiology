from PyQt6.QtWidgets import QMainWindow, QTextEdit, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

class MainWindow(QMainWindow):
    """
    Main Floating Window for the AI Dictation App.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Dictation Platform")
        
        # Set Windows Flags: Stay on Top and Frameless
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint
        )
        
        # Core Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Task 2.1: Add a QTextEdit (Read-Only for now)
        self.editor = QTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setPlaceholderText("Ready for dictation...")
        self.layout.addWidget(self.editor)
        
        # Optional: Set a default size for better initial visibility
        self.resize(400, 150)
