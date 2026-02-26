# software_architecture task 1

Protocol:
[file](Protocol-Kyrylova.pdf)

**Language**: Python 3.13
**Framework**: FastAPI
**Containerization**: Docker & Docker Compose
**Communication**: REST API
**Middleware**: Hazelcast (Cluster of 3 nodes)

Built on top of Task 1.

## Usage example
```
docker-compose exec counter-service uv run python task3.py
```
```
docker-compose exec counter-service uv run python task4.py
```
```
docker-compose exec counter-service uv run python task5.py
```
```
docker-compose exec counter-service uv run python task6.py
```
```
docker-compose exec counter-service uv run python task8.py
```

## Deployment and Execution
```
docker-compose up --build
```