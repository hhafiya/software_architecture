from fastapi import FastAPI
from collections import defaultdict

app = FastAPI()
# {"service_name": ["http://ip1:port", ...]}
registry = defaultdict(list)

@app.post("/register")
async def register(service_name: str, address: str):
    if address not in registry[service_name]:
        registry[service_name].append(address)
    print(f"Registered {address} as {service_name}")
    return {"status": "ok"}

@app.get("/nodes/{service_name}")
async def get_nodes(service_name: str):
    return {"nodes": registry.get(service_name, [])}
