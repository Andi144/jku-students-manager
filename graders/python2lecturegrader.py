import numpy as np
import pandas as pd

from graders import util
from graders.grader import Grader

MAX_POINTS = 100


class Python2LectureGrader(Grader):
    
    def _create_grade_row(self, row: pd.Series) -> pd.Series:
        e1 = row["Quiz: Exam (Real)"]
        e2 = row["Quiz: Retry Exam (Real)"]
        e3 = row["Quiz: Retry Exam 2 (Real)"]
        # most recent exam takes precedence
        if not np.isnan(e3):
            points = e3
        elif not np.isnan(e2):
            points = e2
        else:
            # assert not np.isnan(e1)
            points = e1
        if np.isnan(points):
            return pd.Series([-1, "no data to create grade"])
        return util.create_grade(points, MAX_POINTS)
