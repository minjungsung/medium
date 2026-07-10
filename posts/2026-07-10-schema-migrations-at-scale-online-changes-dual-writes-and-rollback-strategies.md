# Schema Migrations at Scale: Online Changes, Dual Writes, and Rollback Strategies  
*Transforming your database schema without downtime requires strategic planning and careful execution.*

## Thesis  
As systems evolve, the need for schema migrations becomes inevitable. However, performing schema migrations at scale, especially in high-availability environments, presents significant challenges. This article explores an effective approach to online schema changes using dual writes and rollback strategies, with a focus on a real-world scenario involving a microservices architecture that relies on a PostgreSQL database.

## Constraints and Design Considerations  
When designing a schema migration strategy, the following constraints must be considered:

1. **High Availability**: The system must remain operational during the migration.
2. **Data Consistency**: The data must remain consistent across versions.
3. **Performance Impact**: The migration must minimize latency and throughput degradation.
4. **Rollback Capability**: There should be a straightforward way to revert changes if something goes wrong.

### Design Approach  
Given these constraints, we can adopt a dual-write strategy during the migration process. This entails writing to both the old and new schema versions simultaneously until the migration is confirmed successful. 

### Example Scenario  
For illustration, consider an e-commerce application where we need to migrate the `products` table to include a new `category` column. The current schema looks like this:

```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL
);
```

Our goal is to modify it to:

```sql
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    category VARCHAR(100) NULL
);
```

## Implementation Details

### Step 1: Prepare the Migration  
Before making schema changes, we will implement a dual-write mechanism in our service layer. This requires modifying the service responsible for writing product data.

```python
class ProductService:
    def __init__(self, db_old, db_new):
        self.db_old = db_old
        self.db_new = db_new

    def add_product(self, name, price, category=None):
        # Write to the old schema
        self.db_old.execute(
            "INSERT INTO products (name, price) VALUES (%s, %s)", (name, price)
        )
        # Write to the new schema
        self.db_new.execute(
            "INSERT INTO products (name, price, category) VALUES (%s, %s, %s)",
            (name, price, category)
        )
```

### Step 2: Migrate Data  
Once the dual-write mechanism is in place, we can start the migration. For existing records, we’ll populate the new `category` column with default values:

```python
def migrate_products(db_old, db_new):
    products = db_old.execute("SELECT id, name, price FROM products")
    for product in products:
        db_new.execute(
            "INSERT INTO products (id, name, price, category) VALUES (%s, %s, %s, %s)",
            (product['id'], product['name'], product['price'], "default_category")
        )
```

### Step 3: Update the Application  
Once the migration of existing data is complete, update the application to read from the new schema. 

```python
def get_product(product_id):
    # Reading from the new schema
    result = self.db_new.execute("SELECT * FROM products WHERE id = %s", (product_id,))
    return result
```

### Step 4: Monitor and Rollback  
After the migration, monitor the system for anomalies. If issues arise, we can easily rollback to the previous version by directing all writes back to the old schema and ceasing writes to the new schema.

```python
def rollback_migration():
    # Stop writing to the new schema
    # Ensure all writes go back to the old schema
    self.write_to_old_schema_only = True
```

## Validation  
Validation of the migration process is crucial. Here’s how to ensure everything is functioning as expected:

1. **Data Consistency Checks**: Periodically compare data between old and new schemas.
2. **Performance Monitoring**: Analyze latency and throughput metrics during the migration.
3. **Error Logging**: Implement comprehensive logging around the dual-write paths to catch any discrepancies.

## Failure Modes & Debugging  
### Common Symptoms  
1. **Inconsistent Data**: Observing differences between old and new schemas indicates issues with the dual-write mechanism.
2. **Increased Latency**: A significant drop in performance metrics could signal that the migration is impacting service responsiveness.

### Diagnosis  
1. **Inconsistent Data**: Use SQL queries to compare row counts and specific fields between the two schemas. Example:

   ```sql
   SELECT COUNT(*) FROM products_old;
   SELECT COUNT(*) FROM products_new;
   ```

2. **Increased Latency**: Use APM tools to monitor request durations pre- and post-migration. Check for slow queries specifically related to the new schema.

## Trade-offs  
While dual writes are powerful, they come with trade-offs:

1. **Increased Complexity**: The service layer becomes more complex, as it must handle writing to both schemas.
2. **Potential for Data Loss**: If an error occurs after writing to one schema but not the other, data may become inconsistent. 

### When Not to Use Dual Writes  
1. **Low Traffic Applications**: For systems with low transaction volumes, a simple, sequential migration may be more efficient.
2. **Single Database Systems**: If the database cannot support concurrent writes, consider using a more traditional approach instead.

## Performance & Cost  
### Metrics  
- **Latency**: Dual writes may add 10-20 ms per write operation depending on the database load and network latency.
- **Throughput**: If the service typically handles 100 writes/second, expect a reduction to approximately 80-90 writes/second during migration.
  
### Cost Implications  
If deploying on a cloud platform, consider additional costs associated with increased read/write operations, which may lead to higher database service charges.

## Observability  
Effective observability is critical during schema migrations. Focus on the following:

1. **Metrics**: Track metrics such as query latencies, error rates, and throughput.
2. **Logs**: Log every dual write operation, including successes and failures.
3. **Traces**: Use distributed tracing to identify bottlenecks in the migration process.

### Alerting  
Set alerts for key metrics:
- Latency exceeding 100 ms
- Error rates above 1% for write operations
- Discrepancies in row counts between old and new schemas
