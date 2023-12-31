import re

import pandas as pd


def create_grade(points, max_points, grading: dict = None) -> pd.Series:
    """
    Creates a grade object based on the percentage of achieved points, given the
    absolute ``points`` and the absolute ``max_points``. Which grade is returned
    is determined by the ``grading`` scheme that contains lower percentage thresholds
    for each particular grade from 1 ("Sehr gut"/"Very good") to 4 ("Genügend"/
    "Sufficient"). The grading percentages are checked from best grade (1) to worst
    grade (4) in sequential order, returning the grade that matches first when checking
    whether the percentage of the achieved points is greater or equal than the grading
    percentage, or if nothing matches, the grade 5 ("Nicht genügend"/"Not sufficient")
    is returned. Example:
    
        points = 17
        max_points = 24
        grading = {1: 0.875, 2: 0.75, 3: 0.625, 4: 0.50}
        
        percentage = points / max_points = 17 / 24 = 0.7083333
        check grades from 1 to 4 and return first that matches with percentage >= grading[i],
        or return 5 if none match:
            percentage >= grading[1] ---> 0.7083333 >= 0.875 ---> no match, check next
            percentage >= grading[2] ---> 0.7083333 >= 0.75  ---> no match, check next
            percentage >= grading[3] ---> 0.7083333 >= 0.625 ---> match, return grade 3
    
    The returned object is the one required by ``grader._create_grade_row(row)``, i.e.,
    a pd.Series object with two entries, where the first entry is the grade and the
    second is the reason for this grade. The reason is always the empty string for all
    grades specified in ``grading``, i.e., there is no particular reason, and for the
    grade 5, the reason is "total threshold not reached".
    
    :param points: The absolute points that were achieved.
    :param max_points: The absolute maximum points that can be achieved.
    :param grading: A dictionary containing the grading scheme. The keys are the grades
        as integers from 1 (best grade) to 4 (worst grade), and the values are the
        corresponding lower percentage thresholds, i.e., the minimum percentage in order
        to get the respective grades. Specifying an additional key for the grade 5 is
        unnecessary, as this grade is automatically returned if none of the other grades
        match. Default: {1: 0.875, 2: 0.75, 3: 0.625, 4: 0.50}
    :return: A pd.Series object where the first entry is the grade (type: np.int64) and
        the second entry the reason (type: str, i.e., pandas object) for this grade.
    """
    # TODO: better parameterization: "grading" should be an arbitrarily sized sequence
    #  where each entry contains: [0] the grade, [1] the lower threshold, [2] the reason;
    #  this sequence is then simply checked sequentially (possibly with a parameterized
    #  default value if none of "grading" match, or, raising some exception)
    if grading is None:
        grading = {1: 0.875, 2: 0.75, 3: 0.625, 4: 0.50}
    total = points / max_points
    if total >= grading[1]:
        return pd.Series([1, ""])
    if total >= grading[2]:
        return pd.Series([2, ""])
    if total >= grading[3]:
        return pd.Series([3, ""])
    if total >= grading[4]:
        return pd.Series([4, ""])
    return pd.Series([5, "total threshold not reached"])


def check_matr_id_format(s: pd.Series):
    """
    Checks if the specified pd.Series object contains matriculation IDs in the
    following format: "k<MATR_ID>", where <MATR_ID> is an 8-digit number. No
    other leading or trailing characters are allowed. If an invalid format is
    encountered, a ValueError is raised.
    
    :param s: The pd.Series that contains matriculation IDs.
    """
    if s.dtype != object or s.apply(lambda x: re.match(r"k\d{8}$", x) is None).any():
        raise ValueError(f"series does not contain valid ('k<8-digit-matr-id>') matriculation IDs: {s}")
