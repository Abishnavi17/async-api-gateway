import asyncio
import os
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse


DATABASE_FILE = "gateway.db"
API_KEY = os.getenv("API_GATEWAY_KEY", "demo-key")

RATE_LIMIT_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 20

request_history = defaultdict(deque)
rate_limit_lock = asyncio.Lock()

app = FastAPI(title="Simple API Gateway")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_db_connection():
    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def init_database():
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                value REAL NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS traffic_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT NOT NULL,
                path TEXT NOT NULL,
                client_ip TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


def save_metric(name, value):
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO metrics (name, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (name, value, utc_now()),
        )
        connection.commit()


def read_metrics():
    with get_db_connection() as connection:
        rows = connection.execute(
            "SELECT name, value, updated_at FROM metrics ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]


def save_traffic_log(method, path, client_ip, status_code):
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO traffic_logs (method, path, client_ip, status_code, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (method, path, client_ip, status_code, utc_now()),
        )
        connection.commit()


def read_recent_traffic_logs(limit=20):
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT method, path, client_ip, status_code, created_at
            FROM traffic_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def require_api_key(request):
    sent_key = request.headers.get("x-api-key")
    if sent_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def check_rate_limit(client_ip):
    now = time.time()

    async with rate_limit_lock:
        timestamps = request_history[client_ip]

        while timestamps and now - timestamps[0] > RATE_LIMIT_SECONDS:
            timestamps.popleft()

        if len(timestamps) >= MAX_REQUESTS_PER_WINDOW:
            return False

        timestamps.append(now)
        return True


@app.middleware("http")
async def gateway_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"

    allowed = await check_rate_limit(client_ip)
    if not allowed:
        response = JSONResponse(
            status_code=429,
            content={"error": "Too many requests. Please try again later."},
        )
        await asyncio.to_thread(
            save_traffic_log,
            request.method,
            request.url.path,
            client_ip,
            response.status_code,
        )
        return response

    response = await call_next(request)

    await asyncio.to_thread(
        save_traffic_log,
        request.method,
        request.url.path,
        client_ip,
        response.status_code,
    )

    return response


@app.get("/")
async def home():
    return {
        "message": "API Gateway is running",
        "endpoints": ["/health", "/metrics", "/traffic"],
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "time": utc_now()}


@app.get("/metrics")
async def get_metrics():
    metrics = await asyncio.to_thread(read_metrics)
    return {"count": len(metrics), "metrics": metrics}


@app.post("/metrics")
async def update_metric(request: Request):
    require_api_key(request)

    data = await request.json()
    name = data.get("name")
    value = data.get("value")

    if not name or value is None:
        raise HTTPException(
            status_code=400,
            detail="Request body must contain 'name' and 'value'",
        )

    try:
        value = float(value)
    except ValueError:
        raise HTTPException(status_code=400, detail="'value' must be a number")

    await asyncio.to_thread(save_metric, name, value)

    return {
        "message": "Metric saved successfully",
        "metric": {"name": name, "value": value},
    }


@app.get("/traffic")
async def get_traffic_logs(request: Request, limit: int = 20):
    require_api_key(request)

    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")

    logs = await asyncio.to_thread(read_recent_traffic_logs, limit)
    return {"count": len(logs), "logs": logs}


init_database()
