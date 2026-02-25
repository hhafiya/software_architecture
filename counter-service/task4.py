# no locking
import hazelcast
import multiprocessing

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

    for k in range(10_000):
        value = distributed_map.get("key")
        value += 1
        distributed_map.put("key", value)

    print(f"Client {client_id} finished")

    client.shutdown()


if __name__ == "__main__":
    processes = []
    for i in range(3):
        p = multiprocessing.Process(target=worker, args=(i,))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

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
    client.shutdown()