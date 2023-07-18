import os.path
import subprocess
from typing import Union

import pandas as pd
from PySide6.QtCore import Qt, QModelIndex, QSortFilterProxyModel
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QTableView, QApplication, QWidget, QVBoxLayout, QLineEdit, QLabel, QHBoxLayout

from models import DataFrameModel
from widgets.util import get_rectangular_selection


class DataFrameTableView(QTableView):
    
    def __init__(self, df: pd.DataFrame, sort_by: Union[str, int] = 0, parent: QWidget = None):
        super().__init__(parent)
        self.sort_col_index = df.columns.get_loc(sort_by) if isinstance(sort_by, str) else sort_by
        # TODO: model probably needs to be more specific (e.g., StudentsModel that extends DataFrameModel)
        # TODO: (global remark) move all models outside the view classes?
        if len(df) > 0:
            df = df.sort_values(by=df.columns[self.sort_col_index], ignore_index=True)
        self.model = DataFrameModel(df)
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setFilterKeyColumn(-1)  # Search all columns.
        self.proxy_model.setSourceModel(self.model)
        # TODO: extremely hacky and probably wrong, but otherwise, (proxy) sorting is very slow
        self.proxy_model.sort = self.model.sort
        self.setModel(self.proxy_model)
        self.setAlternatingRowColors(True)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSortingEnabled(True)
        self.sortByColumn(self.sort_col_index, Qt.AscendingOrder)
        self.copy_shortcut = QShortcut(QKeySequence.Copy, self)
        # Default is ShortcutContext.WindowShortcut which would fire the activatedAmbiguously signal in case there are
        # more widgets with the same QKeySequence.Copy shortcut
        self.copy_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self.copy_shortcut.activated.connect(self.handle_copy_shortcut)
    
    def handle_copy_shortcut(self):
        indexes = self.selectedIndexes()
        if indexes:
            cb = QApplication.clipboard()
            if len(indexes) == 1:
                result = self.model.get_raw_data(indexes[0].row(), indexes[0].column())
                cb.setText(str(result))
            else:
                rect_selection = get_rectangular_selection(indexes, squeeze=False)
                if rect_selection is not None:
                    row_slice, col_slice = rect_selection
                    result_df = self.model.get_raw_data(row_slice, col_slice)
                    cb.setText(result_df.to_csv(index=False, header=False))
                else:
                    results = [str(self.model.get_raw_data(index.row(), index.column())) for index in indexes]
                    cb.setText(",".join(results))
    
    # TODO: check where this is needed (and in turn, if a copy is required)
    def get_df(self):
        return self.model.get_df()
    
    def set_df(self, df: pd.DataFrame, sort_by: Union[str, int] = 0):
        self.sort_col_index = df.columns.get_loc(sort_by) if isinstance(sort_by, str) else sort_by
        if len(df) > 0:
            df = df.sort_values(by=df.columns[self.sort_col_index], ignore_index=True)
        self.model.set_df(df)
        # Trigger sorting to adjust for new model data TODO: slight code duplication (maybe extract to helper method)
        self.sortByColumn(self.sort_col_index, Qt.AscendingOrder)


class FilterableDataFrameTableView(QWidget):
    
    def __init__(self, data_frame_table_view: DataFrameTableView, parent: QWidget = None):
        super().__init__(parent)
        self.data_frame_table_view = data_frame_table_view
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        filter_label = QLabel("Filter:")
        self.search_edit = QLineEdit()
        self.search_edit.setStatusTip("This tip is shown on the/a statusbar")  # TODO
        self.search_edit.setPlaceholderText("[column name:]regex")
        self.search_edit_original_style_sheet = self.search_edit.styleSheet()
        # Boolean flag to avoid having to constantly change the style sheet
        self.search_edit_has_error = False
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.search_edit)
        layout.addLayout(filter_layout)
        layout.addWidget(self.data_frame_table_view)
        self.search_edit.textChanged.connect(self.search_edit_text_changed)
        self.setLayout(layout)
    
    def search_edit_text_changed(self, text: str):
        parts = text.split(":", maxsplit=1)
        if len(parts) == 2:
            filter_col, text = parts
            df = self.data_frame_table_view.model.get_df(copy=False)  # Read-only access, so no copy required
            if filter_col not in df.columns:
                if not self.search_edit_has_error:
                    self.search_edit.setStyleSheet("color: red;")
                self.search_edit_has_error = True
            else:
                if self.search_edit_has_error:
                    self.search_edit.setStyleSheet(self.search_edit_original_style_sheet)
                    self.search_edit_has_error = False
                filter_col_index = df.columns.get_loc(filter_col)
                self.data_frame_table_view.proxy_model.setFilterKeyColumn(filter_col_index)
                self.data_frame_table_view.proxy_model.setFilterRegularExpression(text)
        else:
            if self.search_edit_has_error:
                self.search_edit.setStyleSheet(self.search_edit_original_style_sheet)
                self.data_frame_table_view.proxy_model.setFilterKeyColumn(-1)
                self.search_edit_has_error = False
            self.data_frame_table_view.proxy_model.setFilterRegularExpression(text)

 
class StudentsTableView(DataFrameTableView):
    
    def __init__(self, df: pd.DataFrame, sort_by: Union[str, int] = 0, parent: QWidget = None):
        super().__init__(df, sort_by, parent)
        self.doubleClicked.connect(self.double_clicked)
    
    def double_clicked(self, index: QModelIndex):
        assert index.isValid()
        result = self.model.get_raw_data(index.row(), index.column())
        # TODO: this does not seem to be the way to go
        if isinstance(result, str) and "@" in result:
            print(f"TEMP: copied '{result}' to clipboard")
            # TODO: QtGui.QGuiApplication.clipboard() also works and is also part of the official documentation
            cb = QApplication.clipboard()
            cb.setText(result)
            # TODO: maybe call mail client with selected e-mail (otherwise, this callback is not really useful, since
            #  we already have the copy&paste keyboard shortcut)


class TutorsTableView(DataFrameTableView):
    
    def __init__(self, df: pd.DataFrame, sort_by: Union[str, int] = 0, parent: QWidget = None):
        super().__init__(df, sort_by, parent)


# TODO: there can be name changes where the (initially added) student names then no longer match with the Moodle
#  submissions. Possible work-around options: 1) store multiple student names with the same matriculation ID. This would
#  however complicate things, since many things are currently based solely on the student ID. 2) Use the Moodle ID from
#  the submission, and with this Moodle ID, somehow obtain the students matriculation ID. Name changes, however, would
#  then not be reflected at all. 3) Just always use the most recent student names. However, splitting old submissions
#  (containing the old names) then no longer works
class SubmissionsTableView(DataFrameTableView):
    
    def __init__(self, df: pd.DataFrame = None, sort_by: Union[str, int] = 0, parent: QWidget = None):
        super().__init__(df if df is not None else pd.DataFrame(), sort_by, parent)
        self.doubleClicked.connect(self.double_clicked)
    
    def double_clicked(self, index: QModelIndex):
        assert index.isValid()
        result = self.model.get_raw_data(index.row(), index.column())
        # TODO: this does not seem to be the way to go
        if os.path.isfile(result):
            # https://stackoverflow.com/a/281911/8176827
            result = result.replace("/", "\\")
            subprocess.Popen(fr'explorer /select,"{result}"')  # TODO: Windows only
