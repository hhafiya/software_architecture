# software_architecture task 5

Protocol: [protocol](protocol5_kyrylova.pdf)


**Language**: Python 3.13
**Framework**: FastAPI
**Containerization**: Docker & Docker Compose
**Communication**: REST API

## Endpoints
User communicates with the system via facde service.
- POST /transaction — (user_id and amount).
- GET /user/{user_id}
- GET /accounts

## Usage example
```
curl -X 'POST' \
  'http://localhost:8080/transaction' \
  -H 'Content-Type: application/json' \
  -d '{
  "user_id": "client_1",
  "amount": 500
}'
```

## Deployment and Execution
```
docker-compose up --build
```

Check `http://localhost:8500`
