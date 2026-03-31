# Lista de columnas que deben estar en los archivos generados
REQUIRED_COLUMNS = [
    "fecha", "producto", "cuenta", "nombre_comitentes",
    "tipo_operacion", "importe_ingreso", "moneda_operacion_abr",
    "productor_nombre", "productor_canal", "productor_total",
    "productor_porcentaje", "importe_ingreso_moneda_lgl"
]

# Lista de columnas a sumar en la hoja "Totales"
SUM_COLUMNS = ["productor_total", "importe_ingreso_moneda_lgl"]

# Lista de columnas a mostrar en la hoja "Totales"
COLUMN_NAMES_TOTALES = ["Producto", "Productor Total", "Importe Moneda Legal"]

# Columna por la cual se va a particionar
PARTITION_COLUMN = "productor_nombre"

# Columna de tipo fecha
DATE_COLUMN = "fecha"

# Nombre de la carpeta creada
FOLDER_NAME = "Agregados"

# Prefijo de los archivos generados por partición
FILE_PREFIX = "AGREGADOS"

# Nombre del archivo de totales
FILE_NAME_TOTALES = "TOTALES ACUMULADO - AGREGADOS"

# Nombre de la hoja de Soporte
SOPORTE_SHEET = "Soporte"

# Fórmula para la fila "Total a facturar" en la hoja Totales (columna C = índice 2)
TOTAL_FORMULA = "=C2"
