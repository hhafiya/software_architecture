from fastapi import FastAPI
from typing import Dict

app = FastAPI()

balances = {}

@app.post("/update")
def update_balance(data: Dict):
    user_id = data.get("user_id")
    amount = data.get("amount", 0)
    current_balance = balances.get(user_id, 0)
    new_balance = current_balance + amount
    balances[user_id] = new_balance

    return {"user_id": user_id, "balance": new_balance}

@app.get("/balance/{user_id}")
def get_balance(user_id: str):
    return {"user_id": user_id, "balance": balances.get(user_id, 0)}

@app.get("/balances")
def get_all_balances():
    return balances

@app.post("/reset")
def reset():
    global balances
    balances = {}
    return {"status": "reset"}