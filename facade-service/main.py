from contextlib import asynccontextmanager
import os, time, random, httpx, hazelcast
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

CONFIG_SERVER_URL = os.getenv("CONFIG_SERVER_URL", "http://config-server:8000")
HZ_SERVERS = os.getenv("HZ_SERVERS", "hz-node-1:5701,hz-node-2:5701,hz-node-3:5701").split(",")

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

async def get_service_url(service_name: str):
    try:
        resp = await app.state.http_client.get(
            f"{CONFIG_SERVER_URL}/nodes/{service_name}",
            timeout=2.0
        )
        nodes = resp.json().get("nodes", [])
        if not nodes:
            raise HTTPException(status_code=503, detail=f"No active nodes for {service_name}")
        return random.choice(nodes)
    except httpx.HTTPError as e:
        print(f"FACADE: Error discovery for {service_name}: {e}")
        raise HTTPException(
            status_code=503, detail=
            f"Config Server unavailable or {service_name} not registered") from e
    except ValueError as e:
        print(f"FACADE: Invalid response from config server for {service_name}: {e}")
        raise HTTPException(
            status_code=503, detail=
            f"Config Server unavailable or {service_name} not registered") from e

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
        log_url = await get_service_url("logging-service")
        await app.state.http_client.post(f"{log_url}/log", json=payload, timeout=1.5)
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
        c_url = await get_service_url("counter-service")
        l_url = await get_service_url("logging-service")

        balance_resp = await app.state.http_client.get(f"{c_url}/balance/{user_id}")
        logs_resp = await app.state.http_client.get(f"{l_url}/logs/{user_id}")

        return {
            "balance": balance_resp.json().get("balance"),
            "transactions": logs_resp.json()
        }
    except (HTTPException, httpx.HTTPError, ValueError) as e:
        return {"balance": None, "transactions": [], "error": str(e)}

@app.get("/accounts")
async def get_all_accounts():
    c_url = await get_service_url("counter-service")
    resp = await app.state.http_client.get(f"{c_url}/balances")
    return resp.json()

@app.get("/stats")
def get_stats():
    return app.state.stats

@app.post("/reset")
async def reset_all_systems():
    app.state.stats.update({"logging_time_total": 0.0, "request_count": 0})

    try:
        c_url = await get_service_url("counter-service")
        await app.state.http_client.post(f"{c_url}/reset")
    except (HTTPException, httpx.HTTPError):
        pass

    try:
        l_url = await get_service_url("logging-service")
        await app.state.http_client.post(f"{l_url}/reset")
    except (HTTPException, httpx.HTTPError):
        pass

    return {"status": "reset request sent"}
