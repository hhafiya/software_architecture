from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

app.state.history = {}

class LogTransactionRequest(BaseModel):
    transaction_id: str
    user_id: str
    amount: int

@app.post("/log")
def log_transaction(data: LogTransactionRequest):
    history = app.state.history
    history[data.transaction_id] = {"user_id": data.user_id, "amount": data.amount}
    print(f"LOG: Received transaction {data.transaction_id}")
    return {"status": "logged"}

@app.get("/logs/{user_id}")
def get_user_logs(user_id: str):
    user_transactions = []
    for tr_id, t in app.state.history.items():
        if t.get("user_id") == user_id:
            user_transactions.append({"transaction_id": tr_id, **t})
    return user_transactions

@app.post("/reset")
def reset_logs():
    app.state.history = {}
    print("LOG: History has been reset")
    return {"status": "logs cleared"}