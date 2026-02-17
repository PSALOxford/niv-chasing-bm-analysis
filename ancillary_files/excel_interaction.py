import os
import glob
import re
import datetime

import pandas as pd

def get_excel_filepaths(
    folder: str
) -> list[str]:
    xlsx_pattern = os.path.join(folder, "*.xlsx")
    excel_files = glob.glob(xlsx_pattern)
    
    xls_pattern = os.path.join(folder, "*.xls")
    excel_files.extend(glob.glob(xls_pattern))
    
    return excel_files

def get_csv_filepaths(
    folder: str
) -> list[str]:
    csv_pattern = os.path.join(folder, "*.csv")
    csv_files = glob.glob(csv_pattern)
    
    return csv_files

def create_filepath_dict(
    filepaths: list[str]
) -> dict[str, str]:
    pattern = re.compile(r'MR1B_(\d{4}_\d{2})\.xlsx$', re.IGNORECASE)
    filepath_dict = {}
    for filepath in filepaths:
        filename = os.path.basename(filepath)
        match = pattern.search(filename)
        if match:
            key = match.group(1)  # Extracts the 'YYYY-MM' part.
            filepath_dict[key] = filepath
        else:
            print(f"Filename '{filename}' does not match the expected pattern.")
    return filepath_dict

def dataframes_to_excel(
    dataframes: list[pd.DataFrame], 
    file_directory: str, 
    file_name : str, 
    sheet_names: list = None
) -> None:
    file_name = file_name + '.xlsx'
    file_path = create_filepath(file_directory, file_name)
    
    if not sheet_names or len(sheet_names) != len(dataframes):
        sheet_names = [f"Sheet{i+1}" for i in range(len(dataframes))]
    
    with pd.ExcelWriter(file_path, engine='xlsxwriter') as writer:
        for df, sheet_name in zip(dataframes, sheet_names):
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    print(f"Excel file successfully saved to {file_path} with {len(dataframes)} sheet(s).")

def create_filepath(
    file_directory: str, 
    file_name: str
) -> str:
    file_directory = file_directory.rstrip('/')
    file_path = os.path.join(file_directory, file_name)
    if os.path.exists(file_path):
        file_name = file_name.replace('.xlsx', "")
        file_name += f"_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        file_name = file_name + '.xlsx'
        file_path = create_filepath(file_directory, file_name)
        
    return file_path

def process_df_for_output(
    df: pd.DataFrame,
    missing_data: set[tuple[str, int]]
) -> pd.DataFrame:
    ordered_df = order_by_settlement_date_and_period(df)
    df_without_missing_data = drop_missing_data_rows(ordered_df, missing_data)
    
    return df_without_missing_data

def order_by_settlement_date_and_period(
    df: pd.DataFrame
) -> pd.DataFrame:
    df_copy = df.copy()
    if 'settlement_date' not in df.columns:
        return df
    df_copy["settlement_date"] = pd.to_datetime(df_copy["settlement_date"], errors="coerce")
    df_copy.sort_values(by=["settlement_date", "settlement_period"], inplace=True)
    df_copy.reset_index(drop=True, inplace=True)
    
    return df_copy

def drop_missing_data_rows(
    ordered_df: pd.DataFrame,
    missing_data: set[tuple[str, int]]
) -> pd.DataFrame:
    ordered_df_copy = ordered_df.copy()
    ordered_df_copy['settlement_date_str'] = ordered_df_copy['settlement_date'].dt.strftime('%Y-%m-%d')

    mask = ~ordered_df_copy.apply(
        lambda row: (row['settlement_date_str'], row['settlement_period']) in missing_data, 
        axis=1
    )

    filtered_df = ordered_df_copy[mask].drop('settlement_date_str', axis=1)
    return filtered_df

def create_dict_from_excel(
    filepath: str,
    key_column: str,
    value_column: str
) -> dict:
    df = pd.read_excel(filepath)
    df.dropna()
    dictionary = df.set_index(key_column).to_dict()[value_column]
    
    return dictionary

def aggregate_results_to_one_file(
    folder: str,
    output_directory: str,
    output_filename: str
) -> None:
    filepaths = get_excel_filepaths(folder)
    if not filepaths:
        print("No Excel files found in the specified folder.")
        return
    
    aggregate_excel_files(filepaths, output_directory, output_filename)

def aggregate_excel_files(
    filepaths: list[str],
    output_directory: str,
    output_filename: str
) -> None:
    first_file_sheets = pd.read_excel(filepaths[0], sheet_name=None)
    sheet_names = list(first_file_sheets.keys())
    combined_sheets = {sheet_name: [] for sheet_name in sheet_names}
    
    for filepath in filepaths:
        try:
            file_sheets = pd.read_excel(filepath, sheet_name=None)
            for sheet_name in sheet_names:
                if sheet_name in file_sheets:
                    combined_sheets[sheet_name].append(file_sheets[sheet_name])
                else:
                    print(f"Warning: Sheet '{sheet_name}' not found in {filepath}")
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
    
    final_dataframes = []
    final_sheet_names = []
    
    for sheet_name, dfs in combined_sheets.items():
        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            ordered_combined_df = order_by_settlement_date_and_period(combined_df)
            final_dataframes.append(ordered_combined_df)
            final_sheet_names.append(sheet_name)
    
    dataframes_to_excel(final_dataframes, output_directory, output_filename, final_sheet_names)