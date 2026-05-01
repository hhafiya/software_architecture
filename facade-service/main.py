from contextlib import asynccontextmanager
import os, time, random, httpx, hazelcast
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

LOGGING_SERVICE_URL = "http://logging-service"
COUNTER_SERVICE_URL = "http://counter-service"
HZ_SERVERS = os.getenv("HZ_SERVERS", "hz-service:5701").split(",")

@asynccontextmanager
async def lifespan(app_: FastAPI):
    hz_client = hazelcast.HazelcastClient(cluster_members=HZ_SERVERS, cluster_name="log")
    app_.state.queue = hz_client.get_queue("counter-queue").blocking()
    app_.state.http_client = httpx.AsyncClient()
    app_.state.stats = {
        "logging_time_total": 0.0,
        "request_count": 0
    }
    yield
    hz_client.shutdown()
    await app_.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)

class TransactionRequest(BaseModel):
    user_id: str
    amount: float

@app.post("/transaction")
async def create_transaction(data: TransactionRequest):
    transaction_id = str(int(time.time() * 1000))
    payload = {
        "transaction_id": transaction_id, 
        "user_id": data.user_id, 
        "amount": data.amount
    }

    start_log = time.perf_counter()
    try:
        await app.state.http_client.post(f"{LOGGING_SERVICE_URL}/log", json=payload, timeout=2.0)
        app.state.stats["logging_time_total"] += (time.perf_counter() - start_log)
    except (HTTPException, httpx.HTTPError) as e:
        print(f"FACADE: Logging failed: {e}")

    try:
        app.state.queue.put(payload)
    except hazelcast.errors.HazelcastError as e:
        raise HTTPException(status_code=500, detail=f"Message Queue error: {e}") from e

    app.state.stats["request_count"] += 1
    return {"transaction_id": transaction_id, "status": "accepted"}

@app.get("/user/{user_id}")
async def get_user_info(user_id: str):
    try:
        balance_resp = await app.state.http_client.get(f"{COUNTER_SERVICE_URL}/balance/{user_id}")
        logs_resp = await app.state.http_client.get(f"{LOGGING_SERVICE_URL}/logs/{user_id}")

        return {
            "balance": balance_resp.json().get("balance"),
            "transactions": logs_resp.json()
        }
    except (HTTPException, httpx.HTTPError, ValueError) as e:
        return {"balance": None, "transactions": [], "error": str(e)}

@app.get("/accounts")
async def get_all_accounts():
    try:
        resp = await app.state.http_client.get(f"{COUNTER_SERVICE_URL}/balances", timeout=2.0)
        return resp.json()
    except (httpx.HTTPError, HTTPException) as e:
        print(f"FACADE: Cannot fetch accounts: {e}")
        return {"error": "Counter service unavailable", "accounts": []}

@app.get("/stats")
def get_stats():
    return app.state.stats

@app.post("/reset")
async def reset_all_systems():
    app.state.stats.update({"logging_time_total": 0.0, "request_count": 0})

    try:
        await app.state.http_client.post(f"{COUNTER_SERVICE_URL}/reset")
    except (HTTPException, httpx.HTTPError):
        pass

    try:
        await app.state.http_client.post(f"{LOGGING_SERVICE_URL}/reset")
    except (HTTPException, httpx.HTTPError):
        pass

    return {"status": "reset request sent"}
