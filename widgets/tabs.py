import PySide6.QtWidgets as qw  # TODO: maybe just import everything individually (good for auto-completion, though)
import pandas as pd
from PySide6.QtCore import Qt, QThreadPool

from splitting.split import split_submissions
from .util import get_moodle_df, get_kusss_df, merge_moodle_and_kusss_dfs, get_download_path
from .views import StudentsTableView, TutorsTableView, SubmissionsTableView, FilterableDataFrameTableView
from .workers import Worker


class CourseTab(qw.QWidget):
    
    def __init__(self, students_df, tutors_df):  # TODO: temp
        super().__init__()
        tabs = qw.QTabWidget()
        students_tab = StudentsTab(students_df)
        # TODO: submissions tab should be optional if the specific course does not have submissions (e.g., lectures)
        #  maybe include a toggle button somewhere that removes/deactivates/disables the submissions tab
        submissions_tab = SubmissionsTab(tutors_df, students_tab.students_table.model)
        grading_tab = GradingTab()
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
        self.init_ui()
    
    def init_ui(self):
        layout = qw.QVBoxLayout()
        layout.addWidget(FilterableDataFrameTableView(self.students_table))
        
        # TODO: drag and drop instead of buttons
        # TODO: probably, it's better to separate the lecture and exercises into their own course tabs. This way, we do
        #  not need to keep track of two course ID columns (VL + UE) and we also do not have problems with different
        #  study IDs (i.e., study IDs that are different for the VL and for the UE but for the same student) -> this
        #  would then also simplify to a single button "Add KUSSS participants..." (and merging would also be easier)
        add_moodle_grading_data_button = qw.QPushButton("Add Moodle participants...")
        add_moodle_grading_data_button.setMaximumWidth(160)
        add_moodle_grading_data_button.clicked.connect(self.add_moodle_grading_data_button_clicked)
        add_kusss_lecture_participants_button = qw.QPushButton("Add KUSSS lecture (VL) participants...")
        add_kusss_lecture_participants_button.setMaximumWidth(220)
        add_kusss_lecture_participants_button.clicked.connect(self.add_kusss_lecture_participants_button_clicked)
        add_kusss_exercise_participants_button = qw.QPushButton("Add KUSSS exercise (UE) participants...")
        add_kusss_exercise_participants_button.setMaximumWidth(220)
        add_kusss_exercise_participants_button.clicked.connect(self.add_kusss_exercise_participants_button_clicked)
        button_layout = qw.QHBoxLayout()
        button_layout.addWidget(add_moodle_grading_data_button)
        button_layout.addWidget(add_kusss_lecture_participants_button)
        button_layout.addWidget(add_kusss_exercise_participants_button)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def add_moodle_grading_data_button_clicked(self):
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
    
    def add_kusss_lecture_participants_button_clicked(self):
        # Returns tuple of [0] = selected files [1] = matching filter for each file
        files = qw.QFileDialog.getOpenFileNames(
            self,
            caption="Open students KUSSS lecture (VL) participants CSVs",
            dir=get_download_path(),  # TODO: temp!!
            filter="CSV files (*.csv)"
        )[0]
        if files:
            # TODO: hard-coded parameters/arguments and values should be from config file
            course_id_col = "Lecture course ID"
            kusss_df = get_kusss_df(files, course_id_col=course_id_col)
            moodle_df = self.students_table.get_df()
            df = merge_moodle_and_kusss_dfs(
                moodle_df,
                kusss_df,
                course_id_col=course_id_col,
                warn_if_not_found_in_kusss_participants=True
            )
            self.students_table.set_df(df)
    
    # TODO: code duplication
    def add_kusss_exercise_participants_button_clicked(self):
        # Returns tuple of [0] = selected files [1] = matching filters for each file
        files = qw.QFileDialog.getOpenFileNames(
            self,
            caption="Open students KUSSS exercise (UE) participants CSVs",
            dir=get_download_path(),  # TODO: temp!!
            filter="CSV files (*.csv)"
        )[0]
        if files:
            # TODO: hard-coded parameters/arguments and values should be from config file
            course_id_col = "Exercise course ID"
            kusss_df = get_kusss_df(files, course_id_col=course_id_col)
            moodle_df = self.students_table.get_df()
            df = merge_moodle_and_kusss_dfs(moodle_df, kusss_df, course_id_col=course_id_col)
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
    
    def __init__(self):
        super().__init__()
