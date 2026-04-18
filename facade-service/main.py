from fastapi import FastAPI
from pydantic import BaseModel
import time
import random
import httpx
import asyncio
from contextlib import asynccontextmanager

LOGGING_SERVICES = [
    "http://logging-service-1:8000",
    "http://logging-service-2:8000",
    "http://logging-service-3:8000"
]
COUNTER_SERVICE_URL = "http://counter-service:8000"

@asynccontextmanager
async def lifespan(app_: FastAPI):
    app_.state.client = httpx.AsyncClient()
    yield
    await app_.state.client.aclose()

app = FastAPI(lifespan=lifespan)

app.state.stats = {
    "logging_time_total": 0.0,
    "counter_time_total": 0.0,
    "request_count": 0
}

class TransactionRequest(BaseModel):
    user_id: str
    amount: float

async def log_request(payload: dict):
    urls = LOGGING_SERVICES.copy()
    random.shuffle(urls)

    start = time.perf_counter()
    for url in urls:
        try:
            resp = await app.state.client.post(f"{url}/log", json=payload, timeout=1.5)
            if resp.status_code == 200:
                return resp, time.perf_counter() - start
        except (httpx.ConnectError, httpx.TimeoutException):
            print(f"FACADE: {url} is down, trying another...")
            continue

    raise RuntimeError("All logging services are unavailable")

@app.post("/transaction")
async def create_transaction(data: TransactionRequest):
    transaction_id = str(int(time.time() * 1000))
    payload = {"transaction_id": transaction_id, "user_id": data.user_id, "amount": data.amount}

    async def counter_request():
        start = time.perf_counter()
        resp = await app.state.client.post(f"{COUNTER_SERVICE_URL}/update", json=payload)
        return resp, time.perf_counter() - start

    (log_resp, log_dur), (counter_resp, counter_dur) = await asyncio.gather(
        log_request(payload),
        counter_request()
    )
    app.state.stats["logging_time_total"] += log_dur
    app.state.stats["counter_time_total"] += counter_dur
    app.state.stats["request_count"] += 1

    counter_data = counter_resp.json()
    return {"transaction_id": transaction_id, "balance": counter_data.get("balance")}
    
@app.get("/user/{user_id}")
async def get_user_info(user_id: str):
    balance_resp = await app.state.client.get(f"{COUNTER_SERVICE_URL}/balance/{user_id}")
    urls = LOGGING_SERVICES.copy()
    random.shuffle(urls)

    logs_data = []
    for url in urls:
        try:
            resp = await app.state.client.get(f"{url}/logs/{user_id}", timeout=1.5)
            if resp.status_code == 200:
                logs_data = resp.json()
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            continue

    return {
        "balance": balance_resp.json().get("balance"),
        "transactions": logs_data
    }

@app.get("/accounts")
async def get_all_accounts():
    client = app.state.client
    resp = await client.get(f"{COUNTER_SERVICE_URL}/balances")
    data = resp.json()
    return data

@app.get("/stats")
def get_stats():
    return app.state.stats

@app.post("/stats/reset")
def reset_stats():
    app.state.stats.update({"logging_time_total": 0.0,
                            "counter_time_total": 0.0, "request_count": 0})
    return {"status": "reset"}

@app.post("/reset")
async def reset_all_systems():
    reset_stats() 
    await app.state.client.post(f"{COUNTER_SERVICE_URL}/reset")

    urls = LOGGING_SERVICES.copy()
    random.shuffle(urls)

    reset_successful = False
    for url in urls:
        try:
            resp = await app.state.client.post(f"{url}/reset", timeout=1.5)
            if resp.status_code == 200:
                reset_successful = True
                print(f"FACADE: System reset via {url}")
                break
        except (httpx.ConnectError, httpx.TimeoutException):
            print(f"FACADE: Could not reset via {url}, trying next...")
            continue

    if not reset_successful:
        return {"status": "partial reset", "error":
                "Could not reach any logging service to reset Hazelcast"}
    return {"status": "all systems reset"}
