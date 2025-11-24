import redis
import psycopg2
import threading
import time
from rich.console import Console
from rich.table import Table

console = Console()

# --- Redis connection ---
r = redis.Redis(host='redis', port=6379, decode_responses=True)

# --- TimescaleDB connection ---
conn = psycopg2.connect(
    dbname="crypto_db",
    user="crypto_user",
    password="crypto_pass",
    host="timescaledb",
    port=5432
)
cur = conn.cursor()

# --- Fonction pour monitor Redis ---
def monitor_redis():
    pubsub = r.pubsub()
    pubsub.subscribe("prices")
    console.print("🔴 [bold red]Redis Pub/Sub monitoring started...[/bold red]")
    for message in pubsub.listen():
        if message['type'] == 'message':
            console.print(f"[red][Redis][/red] New ticker published: {message['data']}")

# --- Fonction pour monitor TimescaleDB ---
def monitor_timescale():
    console.print("🟢 [bold green]TimescaleDB monitoring started...[/bold green]")
    while True:
        cur.execute("SELECT symbol, last, time FROM tickers ORDER BY time DESC LIMIT 5;")
        rows = cur.fetchall()
        table = Table(title="Latest 5 Tickers in TimescaleDB")
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Last Price", style="green")
        table.add_column("Timestamp", style="magenta")
        for row in rows:
            table.add_row(str(row[0]), f"{row[1]:.2f}", str(row[2]))
        console.clear()
        console.print(table)
        time.sleep(5)

# --- Threads pour exécution parallèle ---
thread_redis = threading.Thread(target=monitor_redis, daemon=True)
thread_timescale = threading.Thread(target=monitor_timescale, daemon=True)

thread_redis.start()
thread_timescale.start()

# --- Garder le main alive ---
while True:
    time.sleep(1)
