from fastapi import FastAPI
from typing import Dict

app = FastAPI()

history = {}

@app.post("/log")
def log_transaction(data: Dict):
    tr_id = data.get("transaction_id")
    history[tr_id] = data
    print(f"LOG: Received transaction {tr_id}")
    return {"status": "logged"}

@app.get("/logs/{user_id}")
def get_user_logs(user_id: str):
    user_transactions = []
    for t in history.values():
        if t.get("user_id") == user_id:
            user_transactions.append(t)
    return user_transactions

@app.post("/reset")
def reset_logs():
    global history
    history = {}
    print("LOG: History has been reset")
    return {"status": "logs cleared"}