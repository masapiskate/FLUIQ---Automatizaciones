# Lista de columnas que deben estar en los archivos generados
REQUIRED_COLUMNS = ["Fecha Concertación", "Nº de cuenta", "Nombre Comitente", "Compra/Venta",
                    "CCL/MEP/CANJE/INSTRUMENTO", "BVI/Byma/Acsu/MAE", "VN", "Monto ($)", "Monto (U$)", "Px Productor",
                    "Px Cliente", "Nombre Productor", "P&L Bruto AP", "% Productor", "P&L AP", "Moneda P&L", "TC",
                    "Total P&L Productor Bruto Moneda Legal"]

# Lista de columnas a sumar en la hoja "Totales"
SUM_COLUMNS = ["P&L Bruto AP", "Total P&L Productor Bruto Moneda Legal", "Total P&L Productor Bruto Moneda Legal", "Total P&L Productor Bruto Moneda Legal"]

# Lista de columnas a mostrar en la hoja "Totales"
COLUMN_NAMES_TOTALES = ["Producto", "Arancel Neto", "Monotributista", "Neto Productor RI", "Total Responsable Inscripto"]

# Columna por la cual se va a particionar
PARTITION_COLUMN = "Nombre Productor"

# Columna de tipo fecha
DATE_COLUMN = "Fecha Concertación"

# Nombre de la carpeta creada
FOLDER_NAME = "Comerciales"

# Prefijo de los archivos generados por partición
FILE_PREFIX = "INTERMEDIACION"

# Nombre del archivo de totales
FILE_NAME_TOTALES = "TOTALES ACUMULADO COM - INTERMEDIACION"

# Nombre de la hoja de Soporte
SOPORTE_SHEET = "Soporte"

# Fórmula para la fila "Total a facturar" en la hoja Totales (columna D = índice 3)
TOTAL_FORMULA = "=D2"
