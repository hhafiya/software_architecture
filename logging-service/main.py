import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from pydantic import BaseModel
import hazelcast

HZ_SERVERS = os.getenv("HZ_SERVERS", "hz-node-1:5701,hz-node-2:5701,hz-node-3:5701").split(",")

@asynccontextmanager
async def lifespan(app_: FastAPI):
    client = hazelcast.HazelcastClient(
        cluster_members=HZ_SERVERS,
        cluster_name="log"
    )
    app_.state.hz_map = client.get_map("logmap").blocking()
    app_.state.hz_client = client
    
    print("LOG: Connected to Hazelcast cluster")
    yield
    client.shutdown()

app = FastAPI(lifespan=lifespan)

class LogTransactionRequest(BaseModel):
    transaction_id: str
    user_id: str
    amount: int

@app.post("/log")
def log_transaction(data: LogTransactionRequest):
    transaction_data = {"user_id": data.user_id, "amount": data.amount}
    app.state.hz_map.put(data.transaction_id, transaction_data)
    print(f"LOG: Received transaction {data.transaction_id}")
    return {"status": "logged"}

@app.get("/logs/{user_id}")
def get_user_logs(user_id: str):
    user_transactions = []
    all_entries = app.state.hz_map.entry_set()
    for tr_id, t in all_entries:
        if t.get("user_id") == user_id:
            user_transactions.append({"transaction_id": tr_id, **t})
    return user_transactions

@app.post("/reset")
def reset_logs():
    app.state.hz_map.clear()
    print("LOG: History has been reset")
    return {"status": "logs cleared"}