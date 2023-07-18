import PySide6.QtWidgets as qw
import pandas as pd
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow

from widgets.tabs import CourseTab


# Subclass QMainWindow to customize your application's main window
class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        
        # TODO: temp
        students_df = pd.DataFrame()
        tutors_df = pd.DataFrame({
            "Name": ["Example Name", "Hello Test", "Gabe the Dog"],
            "Weight": [2, 3, 2],
        })
        
        self.tabs = qw.QTabWidget()
        # layout = QGridLayout()
        # layout.addWidget(view, 0, 0)
        # layout.addWidget(QPushButton("hello"), 1, 1)
        # layout.setContentsMargins(0, 0, 0, 0)
        # layout.setSpacing(0)
        python1_tab = CourseTab(students_df, tutors_df)
        handson2_tab = CourseTab(students_df, tutors_df)
        self.tabs.addTab(python1_tab, "Python 1")
        self.tabs.addTab(handson2_tab, "Hands-on AI II")
        
        self.setWindowTitle("JKU Students Manager")
        self.setCentralWidget(self.tabs)
        self.resize(800, 500)
        self.statusBar()  # Currently empty, but will be filled later
        
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
        action = QAction("Some action", file_menu)
        action.triggered.connect(lambda x: print(x))
        file_menu.addAction(action)
        action = QAction("Add tab", file_menu)
        action.triggered.connect(self.add_tab)
        file_menu.addAction(action)
        action = QAction("Exit", file_menu)
        action.triggered.connect(self.close)
        file_menu.addAction(action)
        
        self.tab_count = 0
    
    def add_tab(self):
        self.tab_count += 1
        self.tabs.addTab(qw.QLabel("some label"), f"dynamic tab {self.tab_count}")
