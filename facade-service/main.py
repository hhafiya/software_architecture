from fastapi import FastAPI
from typing import Dict
import time
import requests

app = FastAPI()

LOGGING_SERVICE_URL = "http://logging-service:8000"
COUNTER_SERVICE_URL = "http://counter-service:8000"

@app.post("/transaction")
def create_transaction(data: Dict):
    user_id = data.get("user_id")
    amount = data.get("amount")

    transaction_id = str(int(time.time() * 1000))
    payload = {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "amount": amount,
        "timestamp": time.time()
    }
    requests.post(f"{LOGGING_SERVICE_URL}/log", json=payload)
    counter_resp = requests.post(f"{COUNTER_SERVICE_URL}/update", json=payload)
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