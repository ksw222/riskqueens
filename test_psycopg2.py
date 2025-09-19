# test_psycopg2.py
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database="riskqueens",
    user="postgres",
    password="0000",
)
with conn:
    with conn.cursor() as cur:
        cur.execute("select 1;")
        print("OK:", cur.fetchone())
