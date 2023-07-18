import inspect
import textwrap

import PySide6.QtWidgets as qw  # TODO: maybe just import everything individually (good for auto-completion, though)
import pandas as pd
from PySide6.QtCore import Qt, QThreadPool

from graders.grader import Grader
from graders.python2exercisegrader import Python2ExerciseGrader
from graders.python2lecturegrader import Python2LectureGrader
from splitting.split import split_submissions
from .util import get_moodle_df, get_kusss_df, merge_moodle_and_kusss_dfs, get_download_path
from .views import (
    StudentsTableView,
    TutorsTableView,
    SubmissionsTableView,
    FilterableDataFrameTableView,
    GradingTableView
)
from .workers import Worker


class CourseTab(qw.QWidget):
    
    def __init__(self, students_df: pd.DataFrame = None, tutors_df: pd.DataFrame = None):  # TODO: temp
        super().__init__()
        tabs = qw.QTabWidget()
        students_tab = StudentsTab(students_df)
        # TODO: submissions tab should be optional if the specific course does not have submissions (e.g., lectures)
        #  maybe include a toggle button somewhere that removes/deactivates/disables the submissions tab
        submissions_tab = SubmissionsTab(tutors_df, students_tab.students_table.model)
        grading_tab = GradingTab(students_tab.students_table.model)
        tabs.addTab(students_tab, "Students")
        tabs.addTab(submissions_tab, "Submissions")
        tabs.addTab(grading_tab, "Grading")
        layout = qw.QVBoxLayout()
        layout.addWidget(tabs)
        self.setLayout(layout)


class StudentsTab(qw.QWidget):
    
    def __init__(self, df: pd.DataFrame):
        super().__init__()
        self.students_table = StudentsTableView(df)
        layout = qw.QVBoxLayout()
        layout.addWidget(FilterableDataFrameTableView(self.students_table))
        
        # TODO: drag and drop instead of buttons
        # TODO: probably, it's better to separate the lecture and exercises into their own course tabs. This way, we do
        #  not need to keep track of two course ID columns (VL + UE) and we also do not have problems with different
        #  study IDs (i.e., study IDs that are different for the VL and for the UE but for the same student) -> this
        #  would then also simplify to a single button "Add KUSSS participants..." (and merging would also be easier)
        self.add_moodle_participants_button = qw.QPushButton("Add Moodle participants...")
        self.add_moodle_participants_button.setMaximumWidth(180)
        self.add_moodle_participants_button.clicked.connect(self.add_moodle_participants_button_clicked)
        self.merge_kusss_participants_button = qw.QPushButton("Merge KUSSS participants...")
        self.merge_kusss_participants_button.setMaximumWidth(160)
        self.merge_kusss_participants_button.clicked.connect(self.merge_kusss_participants_button_clicked)
        self.merge_kusss_participants_button.setEnabled(False)
        button_layout = qw.QHBoxLayout()
        button_layout.addWidget(self.add_moodle_participants_button)
        button_layout.addWidget(self.merge_kusss_participants_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def add_moodle_participants_button_clicked(self):
        # Returns tuple of [0] = selected file [1] = matching filter
        file = qw.QFileDialog.getOpenFileName(
            self,
            caption="Open Moodle participants CSV",
            dir=get_download_path(),  # TODO: temp!!
            filter="CSV files (*.csv)"
        )[0]
        if file:
            # TODO: copy from "grading" project
            # TODO: hard-coded (default) parameters should be from config file
            df = get_moodle_df(file)
            self.students_table.set_df(df)
            self.add_moodle_participants_button.setText("Replace Moodle participants...")
            self.merge_kusss_participants_button.setEnabled(True)
    
    # TODO: code duplication
    def merge_kusss_participants_button_clicked(self):
        # Returns tuple of [0] = selected files [1] = matching filters for each file
        files = qw.QFileDialog.getOpenFileNames(
            self,
            caption="Open KUSSS participants CSVs",
            dir=get_download_path(),  # TODO: temp!!
            filter="CSV files (*.csv)"
        )[0]
        if files:
            # TODO: hard-coded parameters/arguments and values should be from config file
            kusss_df = get_kusss_df(files)
            moodle_df = self.students_table.get_df()
            df = merge_moodle_and_kusss_dfs(moodle_df, kusss_df)
            self.students_table.set_df(df)


class SubmissionsTab(qw.QWidget):
    
    def __init__(self, tutors_df, students_model):
        super().__init__()
        # TODO: model vs tableView vs df? (currently: model, but it is not consistent)
        self.students_model = students_model
        self.tutors_table = TutorsTableView(tutors_df)
        self.submissions_table = SubmissionsTableView()
        
        layout = qw.QVBoxLayout()
        
        tutors_widget = qw.QWidget()
        tutors_layout = qw.QVBoxLayout()
        tutors_layout.setContentsMargins(0, 0, 0, 0)
        tutors_layout.addWidget(qw.QLabel("Tutors"))
        tutors_layout.addWidget(FilterableDataFrameTableView(self.tutors_table))
        tutors_widget.setLayout(tutors_layout)
        
        submissions_widget = qw.QWidget()
        submissions_layout = qw.QVBoxLayout()
        submissions_layout.setContentsMargins(0, 0, 0, 0)
        submissions_layout.addWidget(qw.QLabel("Submissions"))
        submissions_layout.addWidget(FilterableDataFrameTableView(self.submissions_table))
        submissions_widget.setLayout(submissions_layout)
        
        splitter = qw.QSplitter(Qt.Vertical)
        splitter.addWidget(tutors_widget)
        splitter.addWidget(submissions_widget)
        layout.addWidget(splitter)
        
        self.split_submissions_button = qw.QPushButton("Split submissions...")
        self.split_submissions_button.setMaximumWidth(150)
        self.split_submissions_button.clicked.connect(self.split_submissions_button_clicked)
        button_layout = qw.QHBoxLayout()
        button_layout.addWidget(self.split_submissions_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def split_submissions_button_clicked(self):
        # Returns tuple of [0] = selected file [1] = matching filter
        file = qw.QFileDialog.getOpenFileName(
            self,
            caption="Open Moodle submissions ZIP",
            dir=get_download_path(),  # TODO: temp!!
            filter="ZIP files (*.zip)"
        )[0]
        if file:
            # TODO: copy from "moodle-submission-splitter" project
            # TODO: hard-coded (default) parameters should be from config file
            # TODO: long-running operation (should not be run on GUI thread)
            # df = split_submissions(
            #     submissions_file=file,
            #     # TODO: inconsistent: table.get_df vs model.get_df
            #     tutors_df=self.tutors_table.get_df(),
            #     info_df=self.students_model.get_df()
            # )
            # self.submissions_table.set_df(df)
            self.split_submissions_button.setEnabled(False)
            
            progress_bar = qw.QProgressBar()
            progress_bar.setMaximumHeight(15)
            progress_bar.setValue(0)  # To initially display 0% (instead of nothing)
            # TODO: not sure about this; is it always guaranteed that the returned value supports .statusBar? I guess
            #  not, since only QMainWindow has this method (maybe need to pass the QMainWindow instance or its status
            #  bar instance into the submissions tab view here to make it more clean); how does the .setStatusTip work?
            #  maybe with some sort of status events, and then, the status bar just accepts the events (not useful here)
            status_bar: qw.QStatusBar = self.window().statusBar()
            status_bar.addPermanentWidget(progress_bar)
            
            worker = Worker(
                func=split_submissions,
                use_progress_callback=True,
                submissions_file=file,
                tutors_df=self.tutors_table.get_df(),
                info_df=self.students_model.get_df()
            )
            worker.result.connect(self.submissions_table.set_df)
            worker.error.connect(self.open_error_dialog)
            worker.progress.connect(progress_bar.setValue)
            
            def remove_progress_bar():
                status_bar.removeWidget(progress_bar)
                progress_bar.deleteLater()
                self.split_submissions_button.setEnabled(True)
            
            worker.finished.connect(remove_progress_bar)
            QThreadPool.globalInstance().start(worker)
    
    def open_error_dialog(self, ex: Exception):
        dialog = qw.QDialog(self)
        dialog.setWindowTitle("An error occurred")
        
        button_box = qw.QDialogButtonBox(qw.QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        
        layout = qw.QVBoxLayout()
        message = qw.QLabel(str(ex))  # TODO: very basic
        layout.addWidget(message)
        layout.addWidget(button_box)
        dialog.setLayout(layout)
        dialog.exec()


class GradingTab(qw.QWidget):
    
    def __init__(self, students_model):
        super().__init__()
        # TODO: model vs tableView vs df? (currently: model, but it is not consistent)
        self.students_model = students_model
        self.grading_table = GradingTableView()
        self.graders = {  # TODO: temp
            "Python 2 Exercise Grader": Python2ExerciseGrader(),
            "Python 2 Lecture Grader": Python2LectureGrader(),
        }
        self.merged_df = None
        
        actions_layout = qw.QHBoxLayout()
        actions_layout.addWidget(qw.QLabel("Grader:"))
        self.grader_combo_box = qw.QComboBox()
        self.grader_combo_box.addItems(list(self.graders.keys()))
        self.grader_combo_box.currentTextChanged.connect(self.grader_combo_box_text_changed)
        actions_layout.addWidget(self.grader_combo_box)
        manage_graders_button = qw.QPushButton("Manage graders...")
        manage_graders_button.clicked.connect(self.manage_graders_button_clicked)
        actions_layout.addWidget(manage_graders_button)
        # Add (arbitrary) stretch as last element to place all previous widgets from left to right regardless of
        # resizing the window
        actions_layout.addStretch()
        
        add_moodle_grading_data_button = qw.QPushButton("Add Moodle grading data...")
        add_moodle_grading_data_button.setMaximumWidth(160)
        add_moodle_grading_data_button.clicked.connect(self.add_moodle_grading_data_button_clicked)
        
        layout = qw.QVBoxLayout()
        layout.addLayout(actions_layout)
        layout.addWidget(FilterableDataFrameTableView(self.grading_table))
        layout.addWidget(add_moodle_grading_data_button)
        self.setLayout(layout)
    
    def grader_combo_box_text_changed(self, text):
        if self.merged_df is not None:
            grader = self.graders[text]
            grader.set_df(self.merged_df)
            grading_df = grader.create_grading_file()
            self.grading_table.set_df(grading_df)
    
    def manage_graders_button_clicked(self):
        dialog = qw.QDialog(self)
        dialog.setWindowTitle("Graders")
        dialog.accepted.connect(lambda: print("ACC"))
        dialog.rejected.connect(lambda: print("REJ"))
        
        # button_box = qw.QDialogButtonBox(qw.QDialogButtonBox.StandardButton.Ok)
        # button_box.accepted.connect(dialog.accept)
        # button_box.rejected.connect(dialog.reject)
        
        dialog_grader_combo_box = qw.QComboBox()
        dialog_grader_text_edit = qw.QTextEdit()
        
        def dialog_grader_combo_box_text_changed(text):
            # grader = self.graders[text]
            # TODO: get source code for the grader "text
            source_code = f"TODO: source code for grader {text}"
            dialog_grader_text_edit.setText(source_code)
        
        def dialog_grader_text_edit_text_changed():
            grader = self.graders[dialog_grader_combo_box.currentText()]
            
            # TODO: extremely hacky
            try:
                # method _create_grade_row(self, row: pd.Series) -> pd.Series must be created
                # TODO: actually, it does not necessarily have to be "_create_grade_row" (could be any valid method
                #  name, but we would need to extract this somehow (maybe parse new locals for callables...))
                source_code = dialog_grader_text_edit.toPlainText()
                # TODO: save source code to file
                exec(source_code)
                # after exec, should be part of locals
                if "_create_grade_row" in locals():
                    _create_grade_row_method = locals()["_create_grade_row"]
                    grader._create_grade_row = _create_grade_row_method.__get__(grader, Grader)
            except Exception as ex:
                print(type(ex), ex)  # TODO
        
        dialog_grader_text_edit.textChanged.connect(dialog_grader_text_edit_text_changed)
        
        dialog_grader_combo_box.addItems(list(self.graders.keys()))
        dialog_grader_combo_box.currentTextChanged.connect(dialog_grader_combo_box_text_changed)
        
        def add_new_grader_button_clicked():
            grader_name = "debug"  # TODO: get name from dialog or QLineEdit
            if grader_name in self.graders:
                print("already exists")  # TODO: error dialog or something like that
            else:
                grader = Grader()  # Abstract, must set abstract methods!
                self.graders[grader_name] = grader
                dialog_grader_combo_box.addItems([grader_name])
                dialog_grader_combo_box.setCurrentText(grader_name)
                self.grader_combo_box.addItems([grader_name])
        
        add_new_grader_button = qw.QPushButton("Add new grader...")
        add_new_grader_button.clicked.connect(add_new_grader_button_clicked)
        button_layout = qw.QHBoxLayout()
        button_layout.addWidget(add_new_grader_button)
        
        layout = qw.QVBoxLayout()
        layout.addWidget(dialog_grader_combo_box)
        layout.addWidget(dialog_grader_text_edit)
        layout.addLayout(button_layout)
        # layout.addWidget(message)
        # layout.addWidget(button_box)
        dialog.setLayout(layout)
        dialog.exec()
    
    # TODO: code duplication
    def add_moodle_grading_data_button_clicked(self):
        # Returns tuple of [0] = selected file [1] = matching filter
        file = qw.QFileDialog.getOpenFileName(
            self,
            caption="Open Moodle grading CSV",
            dir=get_download_path(),  # TODO: temp!!
            filter="CSV files (*.csv)"
        )[0]
        if file:
            # TODO: hard-coded (default) parameters should be from config file
            # TODO: inconsistent handling and naming of students_model.get_df (one time "info_df", another time
            #  "kusss_df" --> choose best fitting, common name)
            moodle_df = get_moodle_df(file)
            kusss_df = self.students_model.get_df(copy=False)
            self.merged_df = merge_moodle_and_kusss_dfs(moodle_df, kusss_df)
            self.grading_table.set_df(self.merged_df)
