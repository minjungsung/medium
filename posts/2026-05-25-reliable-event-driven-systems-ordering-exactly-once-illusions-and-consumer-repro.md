# Reliable Event-Driven Systems: Ordering, Exactly-Once Illusions, and Consumer Reprocessing  
*Building robust architectures for high-stakes financial transactions.*

In an era where event-driven architectures are the backbone of scalable systems, the need for reliable event processing cannot be overstated. This article delves into the intricacies of designing a reliable event-driven system focused on financial transactions, addressing challenges such as message ordering, achieving exactly-once delivery, and reprocessing consumers. The goal is to provide a concrete framework that seasoned engineers can implement to ensure data integrity and reliability in their systems.

## Constraints

For our scenario, we are designing a payment processing system that handles financial transactions in real-time. This system must adhere to the following constraints:

1. **Ordering**: The order of transactions must be preserved; a transaction that credits an account must be processed before a subsequent transaction that debits it.
2. **Exactly-Once Delivery**: Each transaction event must be processed exactly once to prevent double charging or missed payments.
3. **Consumer Reprocessing**: In case of failure, the system must allow consumers to reprocess events without side effects.

Assuming we are using Apache Kafka as our message broker, we will explore how to implement these requirements effectively.

## Design

### Event Structure

Each transaction can be represented as an event with the following structure:

```json
{
  "transactionId": "unique-id-123",
  "accountId": "account-id-456",
  "amount": 100.00,
  "type": "credit", // or "debit"
  "timestamp": "2026-05-25T10:00:00Z"
}
```

### Kafka Configuration

To maintain message ordering, we will partition our Kafka topic by account ID. This ensures that all transactions for a specific account are processed sequentially. Here's how to configure the producer:

```python
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
)

def send_transaction(event):
    producer.send("transactions", key=event["accountId"].encode('utf-8'), value=event)
    producer.flush()
```

### Idempotent Consumers

To achieve exactly-once delivery, we need to ensure the consumers are idempotent. This can be accomplished by maintaining a state that tracks processed transactions. Here's an example consumer implementation:

```python
from kafka import KafkaConsumer
import json
import psycopg2

# Database connection for tracking processed transactions
conn = psycopg2.connect("dbname=transactions user=postgres password=secret")
cur = conn.cursor()

consumer = KafkaConsumer(
    "transactions",
    bootstrap_servers='localhost:9092',
    group_id="payment-processing",
    auto_offset_reset='earliest',
)

def process_transaction(event):
    transaction_id = event['transactionId']
    
    # Check if transaction has already been processed
    cur.execute("SELECT COUNT(*) FROM processed_transactions WHERE transaction_id = %s", (transaction_id,))
    if cur.fetchone()[0] > 0:
        return  # Ignore already processed transaction

    # Process the transaction logic here (update account balances, etc.)
    # ...

    # Mark transaction as processed
    cur.execute("INSERT INTO processed_transactions (transaction_id) VALUES (%s)", (transaction_id,))
    conn.commit()

for message in consumer:
    event = json.loads(message.value)
    process_transaction(event)
```

## Validation

### Testing Message Ordering

To validate that our system maintains message ordering, we can simulate concurrent transactions and check the account state after processing. Create a set of transactions for a single account and assert their final state. Use unit tests or integration tests to verify this behavior.

### Ensuring Exactly-Once Processing

We can write unit tests that attempt to re-process the same transaction and confirm that the state remains unchanged. This can be validated by inserting mock transactions and asserting that the transaction count does not increase for duplicates.

## Performance & Cost

### Latency and Throughput

With our current setup, we can expect some latency due to the database interactions for tracking processed transactions. Assume:

- Each transaction processing takes an average of 5ms.
- The consumer can handle about 200 messages per second.

The throughput can be calculated as follows:

- If we process 200 messages/second, that translates to about 1,200 transactions per minute, equating to approximately 1.7 million transactions per day.

### Cloud Costs

If deployed on a cloud provider, consider the following costs:

- **Kafka Costs**: Running a managed Kafka service could cost around $0.10 per GB of data. If each transaction is approximately 1 KB, that results in about 1.7 GB/day, costing about $0.17/day.
- **Database Costs**: Depending on your database choice, costs could vary significantly. A PostgreSQL instance could cost around $0.20/hour, leading to approximately $144/month.

## Failure Modes & Debugging

### Symptoms

1. **Message Duplication**: If consumers are processing the same transaction multiple times, check if the idempotent logic is correctly implemented.
2. **Out-of-Order Processing**: If transactions are processed out of order, verify the partitioning strategy and ensure that all transactions for an account are routed to the same partition.
3. **Database Connection Issues**: If transactions are not being marked as processed, inspect the database connection and logs for timeouts or connection errors.

### Diagnoses

- Use logs to track transaction processing and any exceptions. Set up alerting for failures or high latency in processing.
- Monitor Kafka offsets to ensure consumers are reading messages as expected. 

## Observability

### Metrics

- **Transaction Rate**: Monitor the number of transactions processed per second.
- **Error Rate**: Track the percentage of failed transactions.
- **Latency**: Measure the time taken to process each transaction.

### Logs

- Log transaction details upon processing and errors encountered.
- Use structured logging to make it easier to filter logs by transaction ID.

### Traces

- Implement distributed tracing (e.g., using OpenTelemetry) to trace the flow of transactions through the system. This helps identify bottlenecks and performance issues.

### Alerts

- Alert on high error rates or latencies exceeding a predefined threshold (e.g., >100ms) in transaction processing.
- Set up alerts for unprocessed messages in Kafka, indicating potential consumer failures.

## Trade-offs

While the approach discussed provides a robust framework for reliable event processing, it comes with trade-offs:

1. **Complexity**: Implementing exactly-once semantics and idempotency increases system complexity, making debugging and maintenance more challenging.
2. **Performance Overhead**: Maintaining state in a database for
