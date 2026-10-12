
import os
import psycopg

connection = psycopg.connect(
    host=os.environ.get("DB_HOST", "localhost"),
    dbname=os.environ.get("DB_NAME", "library_management_system"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ["DB_PASSWORD"],
    port=int(os.environ.get("DB_PORT", "5432"))
)



# .\venv\Scripts\Activate.ps1
# python library_app.py
# http://127.0.0.1:5000
