import os
import re
import warnings
from collections.abc import Iterable
from typing import Union

import numpy as np
import pandas as pd
from PySide6.QtCore import QModelIndex


# https://stackoverflow.com/a/48706260/8176827
def get_download_path():
    """Returns the default downloads path for linux or windows"""
    if os.name == "nt":
        import winreg
        sub_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
        downloads_guid = "{374DE290-123F-4565-9164-39C4925E467B}"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
            location = winreg.QueryValueEx(key, downloads_guid)[0]
        return location
    else:
        return os.path.join(os.path.expanduser("~"), "downloads")


def get_rectangular_selection(indexes: list[QModelIndex], squeeze: bool = True):
    """
    
    :param indexes:
    :param squeeze:
    :return:
    """
    if not indexes:
        return None
    rows, cols = set(), set()
    for index in indexes:
        assert index.isValid()
        row, col = index.row(), index.column()
        rows.add(row)
        cols.add(col)
    rows = sorted(rows)
    cols = sorted(cols)
    # Check if it is only consecutive rows without "holes"
    # max - min + 1 yields the number of elements if and only if this is the case
    # TODO: could be improved to also for for multiple rectangular selections, e.g.:
    #  ....#####........    <-- slice 1
    #  ....#####........    <-- slice 1
    #  .................
    #  ....#####........    <-- slice 2
    #  .................
    #  could be returned as a list of slices [slice 1, slice 2]
    if rows[-1] - rows[0] + 1 == len(rows):
        if squeeze and len(rows) == 1:
            row_slice = rows[0]
        else:
            row_slice = slice(rows[0], rows[-1] + 1)
        # Analogous for columns (only return slices if it is true here as well, since otherwise, it is not a rectangular
        # area that was selected)
        if cols[-1] - cols[0] + 1 == len(cols):
            if squeeze and len(cols) == 1:
                col_slice = cols[0]
            else:
                col_slice = slice(cols[0], cols[-1] + 1)
            return row_slice, col_slice
    return None


# TODO: everything below is copied from the "grading" project
# TODO: should be in different "util" (since it is not directly related to widgets, which this "util" file here
#  indicates via the package: "widgets/util")


# TODO: currently just prints to the console
def get_moodle_df(
        moodle_file: str,
        encoding: str = "utf8",
        cols_to_keep: Iterable[str] = None,
        ignore_assignment_words: Iterable[str] = None,
        ignore_quiz_words: Iterable[str] = None,
) -> pd.DataFrame:
    """
    Returns a prepared and translated Moodle DataFrame.

    :param moodle_file: The path to the CSV input file that contains the grading
        information, i.e., the points for assignments and quizzes (exported via Moodle).
    :param encoding: The encoding to use when reading ``moodle_file``. Default: "utf8"
    :param cols_to_keep: A collection of columns to keep in addition to the three mandatory
        ID columns ("First name", "Surname", "ID number") and in addition to the assignment
        and quiz columns (see `ignore_assignment_words` and ``ignore_quiz_words`` for more
        control over these two kinds of columns). Default: None = [], i.e., no column is
        kept in addition to the three ID columns and the assignment and quiz columns
    :param ignore_assignment_words: A collection of case-insensitive words that indicate
        to drop an assignment column if any word of this collection is contained within
        this column. Default: None = [], i.e., every assignment column is kept
    :param ignore_quiz_words: A collection of case-insensitive words that indicate to drop
        a quiz column if any word of this collection is contained within this column.
        Default: None = ["dummy"], i.e., every quiz column is dropped which contains
        "dummy" (case-insensitive)
    :return: A prepared and translated Moodle DataFrame.
    """
    if cols_to_keep is None:
        cols_to_keep = []
    if ignore_assignment_words is None:
        ignore_assignment_words = []
    ignore_assignment_words = [w.lower() for w in ignore_assignment_words]
    if ignore_quiz_words is None:
        ignore_quiz_words = ["dummy"]
    ignore_quiz_words = [w.lower() for w in ignore_quiz_words]
    
    df = pd.read_csv(moodle_file, na_values="-", encoding=encoding)
    print(f"original size: {df.shape}")
    df = moodle_df_to_en(df)
    
    # TODO: parameterize
    # TODO: assignment cols and quiz cols unused
    id_cols = ["First name", "Surname", "ID number", "Email address"]
    assignment_cols = [c for c in df.columns if c.startswith("Assignment:") and
                       all([w not in c.lower() for w in ignore_assignment_words])]
    quiz_cols = [c for c in df.columns if c.startswith("Quiz:") and
                 all([w not in c.lower() for w in ignore_quiz_words])]
    cols_to_keep = id_cols + assignment_cols + quiz_cols + cols_to_keep
    dropped_cols = set(df.columns) - set(cols_to_keep)
    df = df[cols_to_keep]
    print(f"size after filtering columns: {df.shape}, dropped columns: {dropped_cols}")
    print(f"identified {len(assignment_cols)} assignment columns: {assignment_cols}")
    print(f"identified {len(quiz_cols)} quiz columns: {quiz_cols}")
    
    # Check if there are invalid matriculation ID numbers (e.g., due to having manually added a student to Moodle who is
    # not a registered KUSSS student). If there are, then pandas could not convert them to np.int64 (should then be str,
    # i.e., pandas object). Also check for non-student e-mail addresses to filter out any lecturers, tutors, etc.
    if df["ID number"].dtype != np.int64:
        invalid = df[df["ID number"].str.contains(r"\D", regex=True)]
        if len(invalid) > 0:
            df.drop(invalid.index, inplace=True)
            df["ID number"] = df["ID number"].astype(np.int64)  # Should now work
            print(f"dropped {len(invalid)} entries due to invalid matriculation IDs; new size: {df.shape}")
            warnings.warn(f"the following entries were dropped due to invalid matriculation IDs:\n{invalid[id_cols]}")
        # TODO: does not exclude tutors that still registered via their student account
        non_students = df[~df["Email address"].str.contains("@students.jku.at")]
        if len(non_students) > 0:
            df.drop(non_students.index, inplace=True)
            warnings.warn(f"the following entries were dropped due to non-student e-mail addresses:\n"
                          f"{non_students[id_cols]}")
    
    # Transform the integer ID to a string with exactly 8 characters (with leading zeros)
    df["ID number"] = df["ID number"].apply(lambda x: f"{x:08d}")
    
    # Basic DataFrame is now finished at this point
    return df


# TODO: hard-coded (should probably be in config file)
MOODLE_DE_TO_EN_FULL = {
    "Vorname": "First name",
    "Nachname": "Surname",
    "ID-Nummer": "ID number",
    "E-Mail-Adresse": "Email address",
    "Zuletzt aus diesem Kurs geladen": "Last downloaded from this course"
}

MOODLE_DE_TO_EN_START = {
    "Aufgabe": "Assignment",
    "Test": "Quiz",
    "Kurs gesamt": "Course total",
}

MOODLE_DE_TO_EN_END = {
    "Punkte": "Real",
    "Prozentsatz": "Percentage",
}


def moodle_df_to_en(df: pd.DataFrame):
    # Quick check if it is already English
    for c in df.columns:
        if c in MOODLE_DE_TO_EN_FULL.values():
            return df
    
    new_columns = []
    for c in df.columns:
        # For whatever reason, Moodle inserts non-breaking spaces when exporting in German
        c = c.replace("\xa0", " ")
        original_c = c
        
        if c in MOODLE_DE_TO_EN_FULL:
            # Direct replacement
            c = MOODLE_DE_TO_EN_FULL[c]
        else:
            # Partial replacement
            for start_de, start_en in MOODLE_DE_TO_EN_START.items():
                if c.startswith(start_de):
                    c = c.replace(start_de, start_en, 1)
            for end_de, end_en in MOODLE_DE_TO_EN_END.items():
                c = re.sub(rf"\({end_de}\)$", f"({end_en})", c)
        
        if c == original_c:
            raise ValueError(f"could not translate column '{c}' into English")
        else:
            new_columns.append(c)
    
    assert len(df.columns) == len(new_columns)
    new_df = df.copy()
    new_df.columns = new_columns
    return new_df


def get_kusss_df(
        kusss_participants_files: Union[str, Iterable[str]],
        sep: str = ";",
        matr_id_col: str = "Matrikelnummer",
        study_id_col: str = "SKZ",
        encoding: str = "ANSI",
        course_id_col: str = "Course ID"
):
    # TODO: hard-coded parameters should be from config file
    if isinstance(kusss_participants_files, str):
        kusss_participants_files = [kusss_participants_files]
    dfs = []
    for f in kusss_participants_files:
        df = pd.read_csv(f, sep=sep, usecols=[matr_id_col, study_id_col], encoding=encoding, dtype=str)
        course_id = re.search(r"\d{3}\.\d{3}|\d{6}", f).group()  # TODO: hard-coded assumption
        if "." in course_id:
            course_id = course_id.replace(".", "")
        df[course_id_col] = course_id
        dfs.append(df)
    
    # Check duplicate entries (students who are found multiple times)
    full_df = pd.concat(dfs, ignore_index=True)
    ids = full_df[matr_id_col]
    if ids.dtype != object or ids.apply(lambda x: re.match(r"k\d{8}$", x) is None).any():
        raise ValueError(f"series does not contain valid ('k<8-digit-matr-id>') matriculation IDs: {ids}")
    full_df[matr_id_col] = ids.str.slice(start=1)
    df = full_df.copy().drop_duplicates()
    diff = full_df[full_df.duplicated()].drop_duplicates()
    if len(diff) > 0:
        warnings.warn(f"the following {len(diff)} duplicate entries were dropped (might be OK, e.g., if a "
                      f"student was unregistered from one course but the export still contains an entry):\n{diff}")
    
    # TODO: hard-coded
    return df.rename(columns={
        matr_id_col: "ID number",
        study_id_col: "Study ID"
    })


def merge_moodle_and_kusss_dfs(
        moodle_df: pd.DataFrame,
        kusss_df: pd.DataFrame,
        matr_id_col: str = "ID number",
        study_id_col: str = "Study ID",
        course_id_col: str = "Course ID",
        warn_if_not_found_in_kusss_participants: bool = False
) -> pd.DataFrame:
    # Remove duplicate columns after merging, but special treatment for existing course ID column, where we need to keep
    # the original and merge the new data into it
    if study_id_col in moodle_df.columns or course_id_col in moodle_df.columns:
        df = moodle_df.copy()
        if course_id_col not in moodle_df.columns:
            df[course_id_col] = np.nan
        # TODO: should be vectorized
        for _, kusss_entry in kusss_df.iterrows():
            moodle_entry = df.loc[df[matr_id_col] == kusss_entry[matr_id_col], :]
            # Can only be 1 or 0 in case there is a KUSSS entry but no Moodle entry (e.g., due to drop out)
            if len(moodle_entry) > 1:
                raise ValueError(f"multiple matches for single matriculation ID {kusss_entry[matr_id_col]}:\n"
                                 f"{moodle_entry}")
            if len(moodle_entry) == 1:
                moodle_entry = moodle_entry.iloc[0]
                if not pd.isna(moodle_entry[study_id_col]) and moodle_entry[study_id_col] != kusss_entry[study_id_col]:
                    # TODO: this case is in fact possible (e.g., lecture with study ID 123 and exercise with study ID
                    #  456) --> should support this (need to make separate "Study ID" columns for each course_id_col)
                    raise ValueError(f"student with different study IDs:\n{moodle_entry}\n{kusss_entry}")
                if not pd.isna(moodle_entry[course_id_col]):
                    # TODO: assertion fails if the same file is added (which, of course, means the study IDs are equal)
                    # assert moodle_entry[course_id_col] != kusss_entry[course_id_col]
                    # TODO: this can theoretically happen (students is registered for multiple exercise classes), but
                    #  this is then actually an error that should be corrected in KUSSS
                    raise ValueError(f"student already has an assigned '{course_id_col}':\n"
                                     f"{moodle_entry}\n{kusss_entry}")
                df.loc[df[matr_id_col] == kusss_entry[matr_id_col], [study_id_col, course_id_col]] = kusss_entry[
                    study_id_col], kusss_entry[course_id_col]
    else:
        df = moodle_df.merge(kusss_df, on=matr_id_col, how="left", suffixes=("", "_y"))
        df.drop(df.filter(regex="_y$").columns, axis=1, inplace=True)
    
    print(f"size after merging with KUSSS participants {kusss_df.shape}: {df.shape}")
    diff = kusss_df[~kusss_df[matr_id_col].isin(df[matr_id_col])]
    if len(diff) > 0:
        warnings.warn(
            f"the following {len(diff)} KUSSS participants were not part of the main Moodle participants "
            f"(might be OK, e.g., if students dropped out/are no longer active):\n{diff}")
    # TODO: not really necessary since the following are just the nan-entries after merging "left"
    if warn_if_not_found_in_kusss_participants:
        diff = moodle_df[~moodle_df[matr_id_col].isin(kusss_df[matr_id_col])]
        if len(diff) > 0:
            warnings.warn(
                f"the following {len(diff)} entries were not part of the KUSSS participants, so they cannot "
                f"be graded (might be OK, e.g., if there is both a lecture and exercise, or multiple "
                f"mutually exclusive exercise groups, with a joint Moodle page, and these students "
                f"deliberately only registered for one of the two):\n{diff}")
    # Reorder columns
    df.insert(4, study_id_col, df.pop(study_id_col))  # TODO: hard-coded insertion index
    # TODO: what about "Lecture course ID" and "Exercise course ID" columns? they are dynamic...
    return df
