# TODO: copy from "moodle-submission-splitter" project
import itertools
import math
import os
import os.path
import re
import shutil
import zipfile
from collections import namedtuple, defaultdict
from collections.abc import Iterable, Sequence
from glob import glob

import numpy as np
import pandas as pd
from PySide6.QtCore import Signal


# TODO: many hard-coded default values and assumptions
# TODO: handle empty tutors and submissions


def extract_exercise_number(submissions_file: str, exercise_names: Iterable[str]):
    for ex_name in exercise_names:
        match = re.search(rf"{ex_name}[\s\-_]*(\d+)", os.path.basename(submissions_file))
        if match:
            return int(match.group(1))
    raise ValueError("could not automatically infer exercise number, must specify manually via '-n'")


# TODO: unused
def extract_weighted_tutors(tutors_list: Sequence[str]):
    # Quick check to determine whether weights are specified.
    if "," in tutors_list[0]:
        rows = []
        for t in tutors_list:
            if "," not in t:
                raise ValueError(f"expected ',' in tutor entry '{t}'")
            name, weight = t.split(",", maxsplit=1)
            rows.append([name, float(weight)])
        return pd.DataFrame(rows)
    for t in tutors_list:
        if "," in t:
            raise ValueError(f"unexpected ',' in tutor entry '{t}'")
    return pd.DataFrame(tutors_list)


def handle_duplicate_names(tutors_df: pd.DataFrame):
    dup = tutors_df["name"].duplicated(keep=False)
    dup_names = tutors_df["name"][dup]
    # Create a count for each unique tutor name.
    counts = dict()
    
    def update_and_get_count(name: str):
        count = counts.get(name, 0)
        count += 1
        counts[name] = count
        return count
    
    # Change DataFrame inplace.
    tutors_df.loc[dup, "name"] = [f"{dn} ({update_and_get_count(dn)})" for dn in dup_names]


def get_submissions_df(submissions: Iterable[str], regex_cols: dict[str, str]):
    data = defaultdict(list)
    for s in submissions:
        for name, regex in regex_cols.items():
            match = re.search(regex, s)
            if match is None:
                raise ValueError(f"submission '{s}' does not contain regex pattern '{regex}' for column '{name}'")
            data[name].append(match.group())
    return pd.DataFrame(data)


def match_full_names(full_names: pd.Series, info_df: pd.DataFrame):
    # Try to match the full names (given in the submissions) to separate first and last names. This is a bit tricky,
    # since a full name is just a space-separated string that starts with the first name and ends with the last name,
    # but both the first name and the last name might be multi-names, and there is no way of knowing to which a single
    # name element belongs. So we must find out by trying to match the full names to individual first and last names.
    # The idea here is to just try all possible 2-permutations of the info_df columns, chain the elements together with
    # a space, and then checking whether these chained elements are the same as the full names. If so, the first column
    # must be the one containing first names and the second column the one containing last names. Note: The more columns
    # the info_df has, the more inefficient this heuristic becomes because of the permutations (however, we need the
    # permutations since we do not know the order of the columns in info_df). With many columns, it is this highly
    # recommended to manually provide the first name and last name columns.
    Mismatch = namedtuple("Mismatch", ["col1", "col2", "df"])
    closest_mismatch = None
    for col1, col2 in itertools.permutations(info_df.columns, 2):
        full_names_candidates = info_df[col1] + " " + info_df[col2]
        matching = full_names.isin(full_names_candidates)
        if matching.all():
            return col1, col2
        mismatching = full_names[~matching]
        if closest_mismatch is None or len(mismatching) < len(closest_mismatch.df):
            closest_mismatch = Mismatch(col1, col2, mismatching)
    raise ValueError(f"could not identify first name and last name columns; closest mismatch for columns "
                     f"'{closest_mismatch.col1}' and '{closest_mismatch.col2}':\n{closest_mismatch.df}")


def weighted_chunks(df: pd.DataFrame, weights: Iterable):
    # Scale weights to sum = 1.
    weights = np.array(weights, dtype=float) / sum(weights)
    chunk_sizes = [math.floor(len(df) * w) for w in weights]
    # Distribute the remaining elements evenly. Just repeatedly increase each chunk size by 1 until we distributed all
    # remaining elements.
    remainder_size = len(df) - sum(chunk_sizes)
    idx = 0
    while remainder_size > 0:
        chunk_sizes[idx] += 1
        idx = (idx + 1) % len(chunk_sizes)
        remainder_size -= 1
    assert sum(chunk_sizes) == len(df)
    # Chunk sizes are all set, now simply collect each chunk from "df".
    chunks = []
    idx = 0
    for chunk_size in chunk_sizes:
        chunks.append(df.iloc[idx:idx + chunk_size].copy())
        idx += chunk_size
    assert sum([len(c) for c in chunks]) == len(df)
    return chunks


def get_file_path(path: str, absolute: bool):
    return os.path.abspath(path) if absolute else os.path.basename(path)


def split_submissions(
        submissions_file: str,
        tutors_df: pd.DataFrame,
        exercise_names: Iterable[str] = ("Assignment", "Exercise", "UE", "Übung", "Aufgabe"),
        number: int = None,
        full_name_col: str = "full_name",
        moodle_id_col: str = "moodle_id",
        submission_col: str = "Submission file",
        print_abs_paths: bool = False,
        info_df: pd.DataFrame = None,
        sorting_keys: Sequence[str] = ("Surname", "First name"),
        submission_renaming_keys: Sequence[str] = ("First name", "Surname", "ID number"),
        submission_renaming_separator: str = "_",
        info_df_first_name_col: str = "First name",
        info_df_last_name_col: str = "Surname",
        drop_columns: list[str] = None,
        progress_callback: Signal = None,
) -> pd.DataFrame:
    # If the number of the exercise is specified, use it. Otherwise, try to extract/infer it from the submission
    # filename.
    exercise_num = number if number is not None else extract_exercise_number(submissions_file, exercise_names)
    
    assert len(tutors_df.columns) == 1 or len(tutors_df.columns) == 2
    # Assign equal default weights if only tutor names were specified to ensure we have a weight column.
    if len(tutors_df.columns) == 1:
        tutors_df[1] = 1
    tutors_df.columns = ["name", "weight"]  # TODO: hard-coded assumption! should be parameterized
    tutors_df["name"] = np.roll(tutors_df["name"], exercise_num)
    tutors_df["weight"] = np.roll(tutors_df["weight"], exercise_num)
    # Handle duplicate tutor names by simply adding increasing numbers after the name.
    handle_duplicate_names(tutors_df)
    
    unzip_dir = submissions_file + "_UNZIPPED"
    print(f"extracting submissions ZIP file to '{get_file_path(unzip_dir, print_abs_paths)}'")
    with zipfile.ZipFile(submissions_file, "r") as f:
        f.extractall(unzip_dir)
    # To extract data, the following format is assumed for each submission (correct at the time of writing this code):
    # <full student name>_<7-digit moodle ID>_<rest of submission string>
    # where <full student name> is a space-separated list of strings that holds the full student name, i.e., all first
    # names and all last names (however, we do not know which parts belong to first names and which to last names),
    # <7-digit moodle ID> is an ID with 7 digits generated by Moodle, and <rest of submission string> can be an
    # arbitrary string (at the time of writing this code, this is the string "assignsubmission_file_").
    # TODO: create params for all these columns and regex patterns in case the Moodle format changes (currently, this
    #  would require code modification right here)
    submissions_df = get_submissions_df(os.listdir(unzip_dir), regex_cols={
        full_name_col: r".+(?=_\d{7})",  # Extract the full name according to the above format.
        moodle_id_col: r"\d{7}",  # Extract the 7-digit Moodle ID according to the above format.
        submission_col: r".+",  # This is simply the entire submission (no specific extraction of a pattern).
    })
    if info_df is not None:
        first_name_col = info_df_first_name_col
        last_name_col = info_df_last_name_col
        if first_name_col is None:
            first_name_col, last_name_col = match_full_names(submissions_df[full_name_col], info_df)
            print(f"identified '{first_name_col}' as first name column and '{last_name_col}' as last name column")
        info_df[full_name_col] = info_df[first_name_col] + " " + info_df[last_name_col]
        merged_df = pd.merge(submissions_df, info_df, on=full_name_col, how="inner")
        if len(submissions_df) != len(merged_df):
            no_duplicates = merged_df.drop_duplicates(subset=full_name_col, keep=False)
            duplicates = merged_df.loc[~merged_df.index.isin(no_duplicates.index)]
            if len(duplicates) > 0:
                raise ValueError(f"duplicate names detected:\n{duplicates}")
            else:
                not_in_info = submissions_df[~submissions_df[full_name_col].isin(info_df[full_name_col])]
                raise ValueError("the following entries were part of the submissions but not the info_df (wrong "
                                 f"course? submissions and info inconsistent (check download date)?):\n{not_in_info}")
        if sorting_keys:
            print(f"sorting submissions according to: {', '.join(sorting_keys)}")
            merged_df.sort_values(by=list(sorting_keys), inplace=True)
        submissions_df = merged_df
    else:
        submissions_df.sort_values(submission_col, inplace=True)
    
    if submission_renaming_keys:
        name_format = submission_renaming_separator.join(f"<{k}>" for k in submission_renaming_keys)
        print(f"renaming submissions according to the following format: {name_format}")
    
    print(f"distributing {len(submissions_df)} submissions among the following {len(tutors_df)} tutors:")
    print(tutors_df)
    chunk_dfs = []
    submission_counter = 0
    for i, chunk_df in enumerate(weighted_chunks(submissions_df, tutors_df["weight"])):
        new_names = []
        chunk_file = f"{submissions_file[:-4]}_{tutors_df['name'][i]}.zip"
        with zipfile.ZipFile(chunk_file, "w") as f:
            # Write all files from the submission directory to the tutors ZIP file. Must exclude directories, since glob
            # includes them. Also specify the relative path as name in the ZIP file (arcname), as otherwise, the full
            # absolute path would be stored in the ZIP file.
            for _, entry in chunk_df.iterrows():
                name = submission_renaming_separator.join(entry[k] for k in submission_renaming_keys)
                new_names.append(name)
                for file in glob(os.path.join(unzip_dir, entry[submission_col], "**"), recursive=True):
                    if os.path.isfile(file):
                        if submission_renaming_keys:
                            name = os.path.join(name, os.path.basename(file))
                        else:
                            name = file[len(unzip_dir) + 1:]
                        f.write(file, arcname=name)
                if progress_callback is not None:
                    submission_counter += 1
                    progress_callback.emit(int(100 * submission_counter / len(submissions_df)))
        
        chunk_df[["Tutor name", "Tutor weight"]] = tutors_df[["name", "weight"]].iloc[i]
        chunk_df["Tutor file"] = chunk_file
        chunk_df[f"New {submission_col.lower()}"] = new_names
        chunk_dfs.append(chunk_df)
        
        print(f"[{i + 1}/{len(tutors_df)}] {len(chunk_df):3d} submissions ---> "
              f"{get_file_path(chunk_file, print_abs_paths)}")
    
    print(f"deleting extracted submissions directory '{get_file_path(unzip_dir, print_abs_paths)}'")
    shutil.rmtree(unzip_dir, ignore_errors=True)  # TODO: should be done in try-finally
    
    df = pd.concat(chunk_dfs)
    if drop_columns is None:
        drop_columns = [full_name_col, moodle_id_col]
    df.drop(columns=drop_columns, inplace=True)
    df.insert(len(df.columns) - 2, submission_col, df.pop(submission_col))
    return df
