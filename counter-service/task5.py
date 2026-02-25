# pessimistic locking
import hazelcast
import multiprocessing
import time

def worker(client_id):
    client = hazelcast.HazelcastClient(
        cluster_name="dev",
        cluster_members=[
            "hz-node-1:5701",
            "hz-node-2:5701",
            "hz-node-3:5701"
        ]
    )

    distributed_map = client.get_map("testmap").blocking()
    distributed_map.put_if_absent("key", 0)

    print(f"Client {client_id} started")

    start_time = time.time()

    for k in range(10_000):
        distributed_map.lock("key")
        try:
            value = distributed_map.get("key")
            value += 1
            distributed_map.put("key", value)
        finally:
            distributed_map.unlock("key")

    end_time = time.time()

    print(f"Client {client_id} finished in {end_time - start_time:.2f} seconds")

    client.shutdown()


if __name__ == "__main__":
    processes = []

    total_start = time.time()

    for i in range(3):
        p = multiprocessing.Process(target=worker, args=(i,))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    total_end = time.time()

    client = hazelcast.HazelcastClient(
        cluster_name="dev",
        cluster_members=[
            "hz-node-1:5701",
            "hz-node-2:5701",
            "hz-node-3:5701"
        ]
    )

    distributed_map = client.get_map("testmap").blocking()
    print("FINAL VALUE:", distributed_map.get("key"))
    print("TOTAL EXECUTION TIME:", round(total_end - total_start, 2), "seconds")

    client.shutdown()