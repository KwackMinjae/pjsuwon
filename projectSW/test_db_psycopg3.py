# test_db_psycopg3.py
import psycopg, socket

try:
    socket.create_connection(("127.0.0.1", 5433), timeout=2).close()

    with psycopg.connect(
        "hostaddr=127.0.0.1 host=localhost port=5433 dbname=hair3d user=hair3d password=kira1010825",
        client_encoding="UTF8",
        connect_timeout=3
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("select current_database(), current_user;")
            print("OK psycopg3:", cur.fetchall())
except Exception as e:
    print("FAILED psycopg3:", repr(e))
