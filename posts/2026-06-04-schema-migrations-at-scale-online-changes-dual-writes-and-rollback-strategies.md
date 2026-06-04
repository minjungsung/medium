# Schema Migrations at Scale: Online Changes, Dual Writes, and Rollback Strategies
*An in-depth exploration of managing schema migrations in a distributed microservice architecture.*

Managing schema migrations in a large-scale distributed system is a complex task that requires careful planning and execution. This article focuses on a specific scenario: a microservice-based e-commerce platform that needs to introduce a new payment method while ensuring zero downtime and data consistency. We will cover the constraints imposed by the existing architecture, the design choices made, the implementation details, and how to validate our migration strategy effectively.

## Constraints

In our e-commerce platform, the following constraints must be addressed:

1. **Availability**: The payment service must remain available to customers during the migration.
2. **Consistency**: Data must remain consistent across services throughout the migration process.
3. **Rollback Capability**: If something goes wrong, we need a robust rollback strategy.
4. **Performance**: The migration should not degrade system performance.

Given these constraints, we will implement a dual-write strategy to introduce the new payment method, enabling us to gradually transition users without affecting their experience.

## Design Choices

### Dual Writes

The dual-write strategy involves writing data to both the old and new schemas during the migration phase. Here’s how we will structure this approach:

- **Versioned Schemas**: We will maintain two versions of the payment schema: the existing one and the new version with the additional payment method.
- **Feature Flags**: Use feature flags to control the exposure of the new payment method to users.
- **Event Sourcing**: Implement event sourcing for payment transactions to ensure we can replay events in case of failures.

### Operational Flow

1. Deploy the new version of the payment service that can handle both old and new payment methods.
2. Update the database schema to accommodate the new payment method.
3. Implement dual writes in the payment processing logic.
4. Gradually enable the new payment method for a subset of users.
5. Monitor for issues and rollback if necessary.

## Implementation

### Database Schema Migration

Let's assume our existing payment schema looks like this:

```sql
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

We want to extend this schema to support a new payment method, let's say "Cryptocurrency". The new schema will include a `payment_method` column:

```sql
CREATE TABLE payments_v2 (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL,
    payment_method VARCHAR(20) NOT NULL, -- New column
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Dual Writes Logic

Next, we modify our payment processing logic to accommodate dual writes. Here’s an example in Python using an ORM like SQLAlchemy:

```python
from sqlalchemy import create_engine, Column, Integer, String, Numeric, DateTime, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class PaymentV1(Base):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP, default=TIMESTAMP)

class PaymentV2(Base):
    __tablename__ = 'payments_v2'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    status = Column(String(20), nullable=False)
    payment_method = Column(String(20), nullable=False)
    created_at = Column(TIMESTAMP, default=TIMESTAMP)

# Database setup
engine = create_engine('postgresql://user:password@localhost/dbname')
Session = sessionmaker(bind=engine)
session = Session()

def process_payment(user_id, amount, payment_method):
    # Write to both schemas
    payment_v1 = PaymentV1(user_id=user_id, amount=amount, status='completed')
    payment_v2 = PaymentV2(user_id=user_id, amount=amount, status='completed', payment_method=payment_method)

    session.add(payment_v1)
    session.add(payment_v2)
    session.commit()
```

### Feature Flags

To control the exposure of the new payment method, we can use a simple feature flag system. This can be implemented using environment variables or a configuration service.

```python
import os

def is_feature_enabled(feature_name):
    return os.getenv(feature_name, 'false').lower() == 'true'

if is_feature_enabled('ENABLE_CRYPTO_PAYMENTS'):
    # Allow crypto payment processing
    process_payment(user_id, amount, 'Cryptocurrency')
else:
    # Fallback to existing payment processing
    process_payment(user_id, amount, 'Credit Card')
```

## Validation Strategy

### Testing

1. **Unit Tests**: Ensure that the dual write logic is covered with unit tests.
2. **Integration Tests**: Test the entire payment flow with both schemas in a staging environment.
3. **Canary Releases**: Gradually roll out the new payment method to a small percentage of users and monitor for issues.

### Observability

To ensure we have good observability during the migration, we need to track the following metrics, logs, and traces:

- **Metrics**: Monitor the number of successful and failed payments for both schemas.
  - **Alert on**: Any significant increase in failure rates or latency in the payment processing service.
  
- **Logs**: Capture detailed logs of payment processing events, especially errors.
  
- **Traces**: Use distributed tracing to monitor the flow of payment transactions across services.

## Failure Modes & Debugging

### Symptoms

1. **Increased Error Rates**: Users report failed payments.
2. **Data Mismatch**: Inconsistencies between the two schemas.
3. **Performance Degradation**: Increased latency in payment processing.

### Diagnoses

- **Increased Error Rates**: Check logs to identify any exceptions or errors in the payment processing code. Use metrics to correlate the timing of changes to the error rates.
  
- **Data Mismatch**: Query both schemas to check for discrepancies after a payment is processed. If inconsistencies are found, check the dual write logic and transaction boundaries.

- **Performance Degradation**: Use APM tools to trace the execution time of payment processing functions. Look for bottlenecks introduced by dual writes.

##
