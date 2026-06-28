# Schema Migrations at Scale: Online Changes, Dual Writes, and Rollback Strategies  
*Optimizing database schema evolution in a high-traffic e-commerce platform.*

## Introduction

In the realm of scalable applications, especially within high-traffic e-commerce platforms, the need for effective schema migration strategies is paramount. When dealing with millions of transactions, the ability to evolve the database schema without downtime becomes a critical requirement. This article explores a focused scenario where an online retailer needs to migrate its customer order schema while maintaining high availability and data integrity.

## Problem Constraints

Our scenario involves the following constraints:

1. **High Availability**: The application must remain online during the migration process.
2. **Data Integrity**: All customer orders and their associated metadata must remain consistent.
3. **Performance**: The migration should have minimal impact on the system's latency and throughput.
4. **Rollback Capability**: If the migration fails, we must revert to the previous schema without data loss.

## Migration Design

Given these constraints, we adopt a dual-write strategy coupled with online schema changes. The plan consists of the following steps:

1. **Preparation**: Introduce a new schema version alongside the existing one.
2. **Dual Writes**: For a defined period, write to both the old and new schema.
3. **Read Adaptation**: Adapt reads to handle both schemas, ensuring that legacy and new data are integrated seamlessly.
4. **Migration**: Gradually migrate existing data to the new schema.
5. **Validation**: Monitor the system for discrepancies and performance.
6. **Finalization**: Switch all writes to the new schema and decommission the old one.

### Implementation Steps

#### Step 1: Schema Preparation

Assume our existing `orders` table looks like this:

```sql
CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT,
    total_amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT NOW()
);
```

We want to introduce a new `status` column and a `shipped_at` timestamp:

```sql
CREATE TABLE orders_v2 (
    order_id INT PRIMARY KEY,
    customer_id INT,
    total_amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'pending',
    shipped_at TIMESTAMP NULL
);
```

#### Step 2: Implement Dual Writes

To implement dual writes, we modify the order processing logic to write to both tables. Below is a simplified example in Python using an ORM:

```python
def create_order(customer_id, total_amount):
    order_id = generate_order_id()
    created_at = datetime.now()

    # Write to the old schema
    old_order = Order(order_id=order_id, customer_id=customer_id, total_amount=total_amount, created_at=created_at)
    old_order.save()

    # Write to the new schema
    new_order = OrderV2(order_id=order_id, customer_id=customer_id, total_amount=total_amount, created_at=created_at)
    new_order.save()
    
    return order_id
```

#### Step 3: Adapt Reads

For reading orders, we need to fetch data from both schemas. We can implement a function that checks the existence of the new schema first:

```python
def fetch_order(order_id):
    # Try to fetch from the new schema
    order = OrderV2.query.filter_by(order_id=order_id).first()
    
    if order:
        return order
    # Fallback to the old schema if not found
    return Order.query.filter_by(order_id=order_id).first()
```

#### Step 4: Migration of Existing Data

For existing records, we need to migrate data from `orders` to `orders_v2`. This can be done in batches to minimize load:

```python
def migrate_orders(batch_size=1000):
    offset = 0
    while True:
        old_orders = Order.query.offset(offset).limit(batch_size).all()
        if not old_orders:
            break
        
        for old_order in old_orders:
            new_order = OrderV2(
                order_id=old_order.order_id,
                customer_id=old_order.customer_id,
                total_amount=old_order.total_amount,
                created_at=old_order.created_at
            )
            new_order.save()
        
        offset += batch_size
```

#### Step 5: Validation

During the migration, we need to validate that both schemas are consistent. We can use checksums or counts to ensure data integrity:

```python
def validate_data():
    old_count = Order.query.count()
    new_count = OrderV2.query.count()
    
    if old_count != new_count:
        raise ValueError("Data count mismatch: old={}, new={}".format(old_count, new_count))
```

#### Step 6: Finalization

Once we confirm successful migration and data integrity, we can stop writing to the old schema and clean up:

```python
def finalize_migration():
    # Stop writing to old schema
    # Drop the old table if safe
    db.execute("DROP TABLE orders;")
```

## Failure Modes & Debugging

### Symptoms

1. **Data Inconsistency**: If reads from the new schema return records that do not match the old schema, this indicates a synchronization issue.
2. **Performance Degradation**: If the migration leads to increased latency or decreased throughput, it could signal that the dual-write mechanism or migration process is overwhelming the database.

### Diagnosis

- **Data Inconsistency**: Use logging during writes to track failures. Check for exceptions in the dual-write logic.
- **Performance Issues**: Monitor system metrics such as query latency and load average. Compare these metrics before and during the migration.

## Trade-offs

While this approach allows for zero downtime, it introduces complexity:

1. **Increased Write Latency**: Writing to two tables doubles the write workload, which can affect performance.
2. **Complexity**: The need to maintain logic for dual writes and read adaptations increases code complexity.
3. **Temporary Storage**: The new schema will temporarily require additional storage, which can lead to increased cloud costs.

Therefore, this approach is best suited for systems where high availability is a stringent requirement and where the operations team is equipped to handle the increased complexity.

## Performance & Cost

Let's quantify the performance impact:

- **Latency**: Assume the average write time for a single order is 10ms. With dual writes, it becomes 20ms.
- **Throughput**: If the system initially handles 100 orders per second, dual writes could reduce this to 50 orders per second during migration.
- **Cloud Cost**: If the average storage cost is $0.023/GB/month, and if the new schema requires
