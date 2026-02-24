from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

app.state.balances = {}

class UpdateRequest(BaseModel):
    user_id: str
    amount: int

@app.post("/update")
def update_balance(data: UpdateRequest):
    balances = app.state.balances
    current_balance = balances.get(data.user_id, 0)
    new_balance = current_balance + data.amount
    balances[data.user_id] = new_balance

    return {"user_id": data.user_id, "balance": new_balance}

@app.get("/balance/{user_id}")
def get_balance(user_id: str):
    return {"user_id": user_id, "balance": app.state.balances.get(user_id, 0)}

@app.get("/balances")
def get_all_balances():
    return app.state.balances

@app.post("/reset")
def reset():
    app.state.balances = {}
    return {"status": "reset"}