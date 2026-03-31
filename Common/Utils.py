import pandas as pd
import os
import glob as glob_module


def validate_required_columns(df, required_columns):
    """Verifica que todas las columnas requeridas estén presentes en el DataFrame."""
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Columnas faltantes en el archivo: {missing}")


def prepare_output_folder(file_route, folder_name):
    """Crea y retorna la carpeta de salida junto al archivo fuente."""
    base_dir = os.path.dirname(os.path.abspath(file_route))
    output_folder = os.path.join(base_dir, folder_name)
    os.makedirs(output_folder, exist_ok=True)
    return output_folder


def filter_months(df, date_column, months_to_filter):
    """Filtra el DataFrame para conservar solo las filas cuyo mes esté en months_to_filter."""
    df = df.copy()
    df[date_column] = pd.to_datetime(df[date_column], dayfirst=True, errors="coerce")
    return df[df[date_column].dt.month.isin(months_to_filter)].copy()


def format_date(df, date_column):
    """Convierte la columna de fecha a tipo datetime en el DataFrame."""
    if date_column in df.columns:
        df[date_column] = pd.to_datetime(df[date_column], dayfirst=True, errors="coerce")


def apply_excel_date_format(worksheet, df, date_column, workbook):
    """Aplica formato de fecha dd/mm/yyyy a la columna de fecha en la hoja de Excel."""
    if date_column not in df.columns:
        return
    col_idx = df.columns.get_loc(date_column)
    date_format = workbook.add_format({"num_format": "dd/mm/yyyy"})
    col_width = max(df[date_column].astype(str).apply(len).max(), len(date_column)) + 2
    worksheet.set_column(col_idx, col_idx, col_width, date_format)


def get_totals(exit_folder, file_name, soporte_sheet, column_names_totales, sum_columns):
    """
    Lee todos los archivos de partición, combina las hojas de Soporte
    y genera un archivo de totales acumulado.
    """
    all_files = glob_module.glob(os.path.join(exit_folder, "*.xlsx"))

    dfs = []
    for f in all_files:
        if file_name in os.path.basename(f):
            continue
        try:
            df = pd.read_excel(f, sheet_name=soporte_sheet)
            dfs.append(df)
        except Exception:
            pass

    if not dfs:
        return

    combined = pd.concat(dfs, ignore_index=True)
    output_file = os.path.join(exit_folder, f"{file_name}.xlsx")

    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        workbook = writer.book
        money_format = workbook.add_format({"num_format": "$ #,##0.00"})

        worksheet = workbook.add_worksheet("Totales")
        writer.sheets["Totales"] = worksheet

        worksheet.write_row(0, 0, column_names_totales)
        worksheet.write(1, 0, "Trading")
        worksheet.write(3, 0, "Total a facturar")

        worksheet.add_table(0, 0, 3, len(sum_columns),
            {"columns": [{"header": h} for h in column_names_totales], "style": "Table Style Medium 9"})

        for col_idx, col_name in enumerate(sum_columns, start=1):
            if col_name in combined.columns:
                total = pd.to_numeric(combined[col_name], errors="coerce").sum()
                worksheet.write(1, col_idx, total, money_format)

        for i, col in enumerate(column_names_totales):
            worksheet.set_column(i, i, len(col) + 5)
