from fastapi import FastAPI
from pydantic import BaseModel
import time
import httpx
import asyncio

app = FastAPI()
app.state.client = httpx.AsyncClient()

LOGGING_SERVICE_URL = "http://logging-service:8000"
COUNTER_SERVICE_URL = "http://counter-service:8000"

app.state.stats = {
    "logging_time_total": 0.0,
    "counter_time_total": 0.0,
    "request_count": 0
}

class TransactionRequest(BaseModel):
    user_id: str
    amount: int

@app.post("/transaction")
async def create_transaction(data: TransactionRequest):
    transaction_id = str(int(time.time() * 1000))
    payload = {"transaction_id": transaction_id, "user_id": data.user_id, "amount": data.amount}

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
    app.state.stats["logging_time_total"] += log_dur
    app.state.stats["counter_time_total"] += counter_dur
    app.state.stats["request_count"] += 1

    counter_data = counter_resp.json()
    return {"transaction_id": transaction_id, "balance": counter_data.get("balance")}
    
@app.get("/user/{user_id}")
async def get_user_info(user_id: str):
    client = app.state.client
    balance_task = client.get(f"{COUNTER_SERVICE_URL}/balance/{user_id}")
    logs_task = client.get(f"{LOGGING_SERVICE_URL}/logs/{user_id}")
    balance_resp, logs_resp = await asyncio.gather(balance_task, logs_task)

    balance_data = balance_resp.json()
    logs_data = logs_resp.json()
    return {
        "balance": balance_data.get("balance"),
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
    app.state.stats.update({"logging_time_total": 0.0, "counter_time_total": 0.0, "request_count": 0})
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