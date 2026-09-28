import psycopg2

# Pega aquí la URL que copiaste del botón "Connect"
DATABASE_URL = "postgresql://neondb_owner:npg_WoaOmnX1QIt5@ep-polished-bonus-b53dg423-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# Conexión a Neon en la nube
conexion = psycopg2.connect(DATABASE_URL)
cursor = conexion.cursor()