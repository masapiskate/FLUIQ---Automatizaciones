from Config import GlobalsAgregados as g
from Common import Utils as u
import pandas as pd
import os


"""
Escribe los datos en un archivo Excel con dos hojas:
1. "Totales": Con formato de tabla, cuenta con sumas de la hoja de "Soporte".
2. "Soporte": Con formato de tabla.
"""
def write_excel_with_format(output_file, selected_columns):
    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        workbook = writer.book

        # ------ Hoja 2: "Soporte" ------
        worksheet = workbook.add_worksheet("Soporte")
        writer.sheets["Soporte"] = worksheet

        # Escribir los datos
        selected_columns.to_excel(writer, sheet_name="Soporte", index=False, startrow=1, header=False)

        # Aplicar formato de tabla
        column_settings = [{"header": col} for col in selected_columns.columns]
        worksheet.add_table(0, 0, selected_columns.shape[0], selected_columns.shape[1] - 1,
                            {"columns": column_settings, "style": "Table Style Medium 9"})

        # Ajustar ancho de columnas
        for i, col in enumerate(selected_columns.columns):
            max_length = max(selected_columns[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.set_column(i, i, max_length)

        # Aplicar formato de fecha usando la función de Utils
        u.apply_excel_date_format(worksheet, selected_columns, g.DATE_COLUMN, workbook)

        # ------ Hoja 1: "Totales" ------
        money_format                = workbook.add_format({"num_format": "$ #,##0.00"})
        worksheet_totales           = workbook.add_worksheet("Totales")
        writer.sheets["Totales"]    = worksheet_totales

        # Escribir encabezados
        headers = g.COLUMN_NAMES_TOTALES
        worksheet_totales.write_row(0, 0, headers)

        # Escribir la primera fila ("Trading") con sumas
        worksheet_totales.write(1, 0, "Trading")  # Primera columna = "Producto"

        # Escribir la tercera fila ("Total a facturar")
        worksheet_totales.write(3, 0, "Total a facturar")  # Primera columna = "Producto"

        worksheet_totales.add_table(0, 0, 3, len(g.SUM_COLUMNS),
            {"columns": [{"header": h} for h in headers], "style": "Table Style Medium 9"})

        for col_idx, col_name in enumerate(g.SUM_COLUMNS, start=1):
            formula = f"=SUM(Table1[{col_name}])"
            worksheet_totales.write_formula(1, col_idx, formula, money_format)

        worksheet_totales.write_formula(3, len(g.SUM_COLUMNS), g.TOTAL_FORMULA, money_format)

        # Ajustar ancho de columnas
        for i, col in enumerate(headers):
            worksheet_totales.set_column(i, i, len(col) + 5)


"""
Genera archivos separados a partir de la columna de partición y solo con las columnas seleccionadas.
No genera archivos si la clave de partición está vacía.
"""
def save_partitions(df_sheet, column_name, exit_folder, report=None):
    log = (report or (lambda *_: None))
    df = df_sheet.copy()

    # Quitar NaN, recortar espacios y filtrar vacíos
    df = df.loc[df[column_name].notna()].copy()
    df[column_name] = df[column_name].astype(str).str.strip()
    df = df.loc[df[column_name].ne('')].copy()

    for filtered_value, rows in df.groupby(column_name):
        output_file = os.path.join(exit_folder, f"{g.FILE_PREFIX} - {filtered_value}.xlsx")
        log(f"Generando archivo {output_file}")

        # Filtrar solo las columnas requeridas
        selected_columns = rows[g.REQUIRED_COLUMNS].copy()
        u.format_date(selected_columns, g.DATE_COLUMN)

        # Llamar a la función que escribe el Excel con el formato adecuado
        write_excel_with_format(output_file, selected_columns)


"""
Función principal que maneja el proceso de partición de un archivo Excel, para el caso de "Agregados Manuales".
"""
def split_excel(df_sheet, file_route, obtener_totales, months_to_filter=None, report=None):
    log = (report or (lambda *_: None))
    log("Validando columnas requeridas y preparando carpeta de salida")
    u.validate_required_columns(df_sheet, g.REQUIRED_COLUMNS)
    exit_folder = u.prepare_output_folder(file_route, g.FOLDER_NAME)

    # Si se especificaron meses a filtrar, filtramos
    if months_to_filter:
        log("Filtrando meses")
        df_sheet = u.filter_months(df_sheet, g.DATE_COLUMN, months_to_filter)

    save_partitions(df_sheet, g.PARTITION_COLUMN, exit_folder, report)

    if obtener_totales == True:
        log("Generando archivo de totales")
        u.get_totals(exit_folder, g.FILE_NAME_TOTALES, g.SOPORTE_SHEET, g.COLUMN_NAMES_TOTALES, g.SUM_COLUMNS)
