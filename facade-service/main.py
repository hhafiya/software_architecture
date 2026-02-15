from fastapi import FastAPI
from typing import Dict
import time
import requests

app = FastAPI()

LOGGING_SERVICE_URL = "http://logging-service:8000"
COUNTER_SERVICE_URL = "http://counter-service:8000"

stats = {
    "logging_time_total": 0.0,
    "counter_time_total": 0.0,
    "request_count": 0
}

@app.post("/transaction")
def create_transaction(data: Dict):
    user_id = data.get("user_id")
    amount = data.get("amount")

    transaction_id = str(int(time.time() * 1000))
    payload = {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "amount": amount,
    }
    start_log = time.perf_counter()
    requests.post(f"{LOGGING_SERVICE_URL}/log", json=payload)
    stats["logging_time_total"] += (time.perf_counter() - start_log)

    start_counter = time.perf_counter()
    counter_resp = requests.post(f"{COUNTER_SERVICE_URL}/update", json=payload)
    stats["counter_time_total"] += (time.perf_counter() - start_counter)

    stats["request_count"] += 1

    balance = counter_resp.json().get("balance")
    return {"transaction_id": transaction_id, "balance": balance}

@app.get("/user/{user_id}")
def get_user_info(user_id: str):
    balance_resp = requests.get(f"{COUNTER_SERVICE_URL}/balance/{user_id}")
    logs_resp = requests.get(f"{LOGGING_SERVICE_URL}/logs/{user_id}")
    return {
        "balance": balance_resp.json().get("balance"),
        "transactions": logs_resp.json()
    }

@app.get("/accounts")
def get_all_accounts():
    resp = requests.get(f"{COUNTER_SERVICE_URL}/balances")
    return resp.json()

@app.get("/stats")
def get_stats():
    return stats

@app.post("/stats/reset")
def reset_stats():
    global stats
    stats = {"logging_time_total": 0.0, "counter_time_total": 0.0, "request_count": 0}
    return {"status": "reset"}