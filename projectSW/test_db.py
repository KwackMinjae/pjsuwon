import psycopg2
try:
    conn = psycopg2.connect(
      host="127.0.0.1",  # <-- localhost 대신
      port=5433,
      user="hair3d",
      password="kira1010825",
      dbname="hair3d"
)
    conn.set_client_encoding('UTF8')
    print("OK")
    conn.close()
except Exception as e:
    print("FAILED:", repr(e))
