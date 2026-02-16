import time
import asyncio
import httpx

FACADE_URL = "http://localhost:8080/transaction"

CLIENTS = 10
REQUESTS_PER_CLIENT = 10000

async def print_stats(client):
    stats = (await client.get("http://localhost:8080/stats")).json()
    print("\nService contribution:")
    print("Logging total time:", stats["logging_time_total"])
    print("Counter total time:", stats["counter_time_total"])
    print("Request count:", stats["request_count"])

async def print_balances(client):
    balances = (await client.get("http://localhost:8080/accounts")).json()

    print("\nFinal balances:")
    print(balances)

async def reset_system(client):
    print("\nResetting system...")
    await client.post("http://localhost:8080/reset")

async def scenario1():
    # 10 accounts × 10K requests each
    async with httpx.AsyncClient() as client:
        async def worker(client_id):
            user_id = f"user_{client_id}"
            for _ in range(REQUESTS_PER_CLIENT):
                payload = {
                    "user_id": user_id,
                    "amount": 1
                }
                await client.post(FACADE_URL, json=payload)
        start = time.perf_counter()
        await asyncio.gather(*[worker(i) for i in range(CLIENTS)])
        end = time.perf_counter()

        total_requests = CLIENTS * REQUESTS_PER_CLIENT
        total_time = end - start

        print("10 clients 10 accounts scenario")
        print("Total time:", total_time)
        print("Requests/sec:", total_requests / total_time)

        await print_stats(client)
        await print_balances(client)
        await reset_system(client)

async def scenario2():
    # 1 account, 10 clients × 10K requests each
    async with httpx.AsyncClient() as client:
        async def worker():
            for _ in range(REQUESTS_PER_CLIENT):
                payload = {
                    "user_id": "shared_user",
                    "amount": 1
                }
                await client.post(FACADE_URL, json=payload)
        start = time.perf_counter()
        await asyncio.gather(*[worker() for _ in range(CLIENTS)])
        end = time.perf_counter()

        total_requests = CLIENTS * REQUESTS_PER_CLIENT
        total_time = end - start

        print("10 clients 1 account scenario")
        print("Total time:", total_time)
        print("Requests/sec:", total_requests / total_time)

        await print_stats(client)
        await print_balances(client)
        await reset_system(client)


async def main():
    await scenario1()
    await scenario2()


asyncio.run(main())