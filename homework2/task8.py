import hazelcast
from multiprocessing import Process
import time


def create_client():
    return hazelcast.HazelcastClient(
        cluster_name="dev",
        cluster_members=[
            "hz-node-1:5701",
            "hz-node-2:5701",
            "hz-node-3:5701"
        ]
    )

def producer():
    client = create_client()
    queue = client.get_queue("bounded_queue").blocking()

    for i in range(1, 101):
        print(f"Producing {i}")
        queue.put(i)
        print(f"Inserted {i}")

    queue.put(-1)
    queue.put(-1)

    print("Producer finished")
    client.shutdown()


def consumer(client_id):
    client = create_client()
    queue = client.get_queue("bounded_queue").blocking()

    while True:
        item = queue.take()
        if item == -1:
            break
        print(f"Consumer {client_id} consumed: {item}")

    print(f"Consumer {client_id} finished")
    client.shutdown()


if __name__ == "__main__":
    p_prod = Process(target=producer)
    c1 = Process(target=consumer, args=(1,))
    c2 = Process(target=consumer, args=(2,))

    p_prod.start()
    c1.start()
    c2.start()

    p_prod.join()
    c1.join()
    c2.join()

    print("\n--- Part 1 finished ---")

    print("\nPart 2, maxed queue")
    
    p_prod_v2 = Process(target=producer)
    c1_v2 = Process(target=consumer, args=(1,))
    c2_v2 = Process(target=consumer, args=(2,))

    print("Producer started, waiting for 20 sec...")
    p_prod_v2.start()
    
    time.sleep(20)
    
    print("Consumers starting now!")
    c1_v2.start()
    c2_v2.start()

    p_prod_v2.join()
    c1_v2.join()
    c2_v2.join()

    print("All processes finished")