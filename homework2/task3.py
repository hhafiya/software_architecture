# Distributed Map
import hazelcast
import time

def run_task3():
    client = hazelcast.HazelcastClient(
            cluster_name="dev",
            cluster_members=[
                "hz-node-1:5701",
                "hz-node-2:5701",
                "hz-node-3:5701"
            ]
        )
    print("Connected to Hazelcast cluster.")
    distributed_map = client.get_map("testmap").blocking()
    distributed_map.clear()

    print("Writing 1000 values...")
    for i in range(1000):
        distributed_map.put(i, f"value-{i}")

    print(f"Done! Current map size: {distributed_map.size()}")
    client.shutdown()

if __name__ == "__main__":
    run_task3()

