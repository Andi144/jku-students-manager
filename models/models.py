from typing import Union

import numpy as np
import pandas as pd
from PySide6 import QtGui
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


class DataFrameModel(QAbstractTableModel):
    
    # TODO: empty DataFrame as default
    def __init__(self, df: pd.DataFrame = None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()
    
    def get_df(self, copy: bool = True):
        return self._df.copy() if copy else self._df
    
    def set_df(self, df: pd.DataFrame):
        # TODO: which one to choose?
        # self.layoutAboutToBeChanged.emit()
        # self.modelAboutToBeReset.emit()
        self.beginResetModel()
        self._df = df
        # self.layoutChanged.emit()
        # self.modelReset.emit()
        self.endResetModel()
    
    # TODO: very similar to method "data", but unfortunately, there is no Qt.RawDataRole entry in the Qt.ItemDataRole
    #  enum
    def get_raw_data(self, row: Union[int, slice, None] = None, col: Union[int, slice, None] = None):
        copy = self._df.copy()
        if row is not None and col is not None:
            return copy.iloc[row, col]
        if row is not None:
            return copy.iloc[row]
        if col is not None:
            return copy.iloc[:, col]
        return copy
    
    # TODO: why is it called "parent"? inconsistent with method "data" where it is (rightfully) called "index"
    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df)
    
    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._df.columns)
    
    def data(self, index: QModelIndex, role: Qt.ItemDataRole = Qt.DisplayRole):
        if not index.isValid():
            return None
        
        if role == Qt.DisplayRole:
            return str(self._df.iloc[index.row(), index.column()])
        
        if role == Qt.TextAlignmentRole:
            value = self._df.iloc[index.row(), index.column()]
            
            if isinstance(value, int) or isinstance(value, float):
                return Qt.AlignTop + Qt.AlignRight
        
        if role == Qt.ForegroundRole:  # https://doc.qt.io/qt-6/qt.html#ItemDataRole-enum
            value = self._df.iloc[index.row(), index.column()]
            if isinstance(value, float) and np.isnan(value):
                return QtGui.QColor(255, 0, 0)
        
        return None
    
    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                return str(self._df.columns[section])
            
            if orientation == Qt.Vertical:
                return str(self._df.index[section])
        
        return None
    
    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder):
        if len(self._df) > 1:
            self.layoutAboutToBeChanged.emit()
            self._df.sort_values(
                by=self._df.columns[column],
                ascending=order == Qt.AscendingOrder,
                inplace=True
            )
            self.layoutChanged.emit()
    
    # def mimeTypes(self):
    #     return ['text/plain']
    #
    # def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
    #     print("mimeData", indexes)
    #     qm = QMimeData()
    #     qm.setData("text/plain", "hello!123")
    #     return qm
    #
    # def dropMimeData(self, data, action, row, column, parent):
    #     # handle drop data
    #     print("dropMimeData", data, action, row, column, parent)
    #     return True
    #
    # def supportedDragActions(self) -> Qt.DropAction:
    #     return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction
