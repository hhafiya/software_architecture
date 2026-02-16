from fastapi import FastAPI
from typing import Dict
import time
import httpx
import asyncio

app = FastAPI()
app.state.client = httpx.AsyncClient()

LOGGING_SERVICE_URL = "http://logging-service:8000"
COUNTER_SERVICE_URL = "http://counter-service:8000"

stats = {
    "logging_time_total": 0.0,
    "counter_time_total": 0.0,
    "request_count": 0
}

@app.post("/transaction")
async def create_transaction(data: Dict):
    user_id = data.get("user_id")
    amount = data.get("amount")
    transaction_id = str(int(time.time() * 1000))
    payload = {"transaction_id": transaction_id, "user_id": user_id, "amount": amount}

    client = app.state.client
    async def log_request():
        start = time.perf_counter()
        resp = await client.post(f"{LOGGING_SERVICE_URL}/log", json=payload)
        return resp, time.perf_counter() - start

    async def counter_request():
        start = time.perf_counter()
        resp = await client.post(f"{COUNTER_SERVICE_URL}/update", json=payload)
        return resp, time.perf_counter() - start

    (log_resp, log_dur), (counter_resp, counter_dur) = await asyncio.gather(
        log_request(), 
        counter_request()
    )
    stats["logging_time_total"] += log_dur
    stats["counter_time_total"] += counter_dur
    stats["request_count"] += 1

    return {"transaction_id": transaction_id, "balance": counter_resp.json().get("balance")}
    
@app.get("/user/{user_id}")
async def get_user_info(user_id: str):
    client = app.state.client
    balance_task = client.get(f"{COUNTER_SERVICE_URL}/balance/{user_id}")
    logs_task = client.get(f"{LOGGING_SERVICE_URL}/logs/{user_id}")
    balance_resp, logs_resp = await asyncio.gather(balance_task, logs_task)
    return {
        "balance": balance_resp.json().get("balance"),
        "transactions": logs_resp.json()
    }

@app.get("/accounts")
async def get_all_accounts():
    client = app.state.client
    resp = await client.get(f"{COUNTER_SERVICE_URL}/balances")
    return resp.json()

@app.get("/stats")
def get_stats():
    return stats

@app.post("/stats/reset")
def reset_stats():
    global stats
    stats.update({"logging_time_total": 0.0, "counter_time_total": 0.0, "request_count": 0})
    return {"status": "reset"}

@app.post("/reset")
async def reset_all_systems():
    client = app.state.client
    reset_stats() 
    await asyncio.gather(
        client.post(f"{COUNTER_SERVICE_URL}/reset"),
        client.post(f"{LOGGING_SERVICE_URL}/reset")
    )
    return {"status": "all systems reset"}