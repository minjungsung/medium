# Designing Idempotent APIs Under At-Least-Once Delivery  
*An exploration of retries, deduplication keys, and failure semantics in a microservices architecture.*

In a distributed system where message delivery is not guaranteed to be exactly-once, designing idempotent APIs becomes crucial for maintaining consistency and reliability. This article will focus on a payment processing system that interacts with multiple microservices, emphasizing how to ensure idempotency while supporting at-least-once delivery semantics. 

## Constraints

### System Requirements
1. **High Availability**: The payment processing system must be able to handle multiple requests simultaneously and remain operational even if some services fail.
2. **At-Least-Once Delivery**: External services may retry requests, leading to potential duplicate requests.
3. **Consistency**: The system must maintain a consistent state after processing requests, regardless of the number of times a request is received.
4. **Scalability**: The API should scale horizontally with an increasing number of transactions.

### Assumptions
- The API client can generate unique deduplication keys for each request.
- The payment processing service can maintain state in a persistent datastore.
- The system will utilize a message broker (like Kafka or RabbitMQ) to handle requests asynchronously.

## Design

### Idempotency Strategy
To ensure idempotency, we will use a combination of deduplication keys and a state machine. Each API request will include a unique deduplication key that identifies the transaction. This key will be stored in a database alongside the transaction state.

#### State Machine
The payment processing workflow can be modeled with the following states:
- **Pending**: The initial state after the request is received.
- **Completed**: The transaction has been successfully processed.
- **Failed**: An error occurred during processing.

### API Design
The payment API will have the following endpoint:

```http
POST /api/payments
Content-Type: application/json

{
  "amount": 100.00,
  "currency": "USD",
  "deduplication_key": "unique-key-12345"
}
```

### Implementation

#### Data Model
We will create a SQL table to track payment transactions:

```sql
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    deduplication_key VARCHAR(255) UNIQUE NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    currency VARCHAR(3) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Payment Processing Logic
The following is a simplified implementation of the payment processing service in Python using Flask:

```python
from flask import Flask, request, jsonify
from sqlalchemy import create_engine, Column, String, Integer, Numeric, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

app = Flask(__name__)
Base = declarative_base()
engine = create_engine('postgresql://user:password@localhost/mydatabase')
Session = sessionmaker(bind=engine)
session = Session()

class Payment(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    deduplication_key = Column(String, unique=True, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

@app.route('/api/payments', methods=['POST'])
def create_payment():
    data = request.json
    deduplication_key = data.get("deduplication_key")
    amount = data.get("amount")
    currency = data.get("currency")

    existing_payment = session.query(Payment).filter_by(deduplication_key=deduplication_key).first()

    if existing_payment:
        return jsonify({"status": existing_payment.status}), 200

    new_payment = Payment(deduplication_key=deduplication_key, amount=amount, currency=currency, status='Pending')
    session.add(new_payment)
    session.commit()

    # Simulate processing the payment
    # TODO: Integrate with billing system
    new_payment.status = 'Completed'
    session.commit()

    return jsonify({"status": new_payment.status}), 201

if __name__ == '__main__':
    app.run()
```

### Validation

#### Testing for Idempotency
To validate the idempotency of the API, we can perform the following tests:

1. **Single Request Test**: Send a request to create a payment and verify that it returns a "Completed" status.
2. **Duplicate Request Test**: Send the same request again with the same deduplication key and verify that it returns the same "Completed" status without creating a duplicate entry.

```bash
# Test 1: Initial payment request
curl -X POST http://localhost:5000/api/payments -H "Content-Type: application/json" -d '{"amount": 100.00, "currency": "USD", "deduplication_key": "unique-key-12345"}'

# Test 2: Duplicate payment request
curl -X POST http://localhost:5000/api/payments -H "Content-Type: application/json" -d '{"amount": 100.00, "currency": "USD", "deduplication_key": "unique-key-12345"}'
```

## Failure Modes & Debugging

### Common Symptoms
1. **Duplicate Transactions**: If the API is not properly handling deduplication keys, clients may experience multiple transactions for the same request.
2. **Unexpected Status**: Clients might receive an unexpected status code (e.g., 500 Internal Server Error) when processing a request.
3. **Transaction Not Found**: When querying for a transaction by deduplication key, it may not exist if the insert failed.

### Diagnosis
- **Logs**: Monitor application logs for errors during transaction processing.
- **Database Constraints**: Check for violations of unique constraints on the deduplication key in the database.

## Trade-offs

### When NOT to Use This Approach
- **Low Throughput Services**: If your service does not require high availability or can handle at-most-once delivery, the complexity of implementing an idempotent API may not be justified.
- **Simple Microservices**: For microservices with a straightforward request-response model and no external retries, a typical REST API without deduplication may suffice.

## Performance & Cost

### Latency and Throughput
Using a relational database with unique constraints may introduce additional latency due to index management. For instance, inserting a payment could take approximately 10ms, but querying for an existing transaction to check for duplication could add another 5ms. 

If
