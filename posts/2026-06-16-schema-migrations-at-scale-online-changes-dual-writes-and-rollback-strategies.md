# Schema Migrations at Scale: Online Changes, Dual Writes, and Rollback Strategies  
*Effective strategies for maintaining data integrity in high-availability systems.*

In a world where data schema changes are inevitable, especially in large-scale, high-availability systems, managing schema migrations without service interruption is crucial. This article will explore a focused scenario: migrating a user profile schema in a multi-tenant SaaS application. We will dive deep into the constraints, design decisions, and implementation strategies for online changes, dual writes, and rollback strategies.

## Constraints

### High Availability
The application must remain operational throughout the migration process, with zero downtime for end users. This requires careful planning and execution to ensure that reads and writes can occur without disruption.

### Data Integrity
Data consistency must be maintained during the migration. Any temporary inconsistencies could lead to application errors or data loss.

### Performance
Schema migrations can introduce latency. The changes must be performed in a way that minimizes the impact on overall performance, especially during peak usage hours.

### Rollback Capabilities
In the event of a failure, a seamless rollback strategy is essential to restore the application to its prior state without data loss.

## Design

The migration strategy chosen for this scenario is a dual-write approach, accompanied by an online change mechanism. This involves updating the data model in two stages:

1. **Phase 1: Introduce the new schema without removing the old one.**
2. **Phase 2: Transition to the new schema and eventually deprecate the old one.**

### New Schema Example

Assuming we are transitioning from a simple user profile schema:

```sql
CREATE TABLE user_profiles (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL
);
```

to a more complex schema that includes new fields for user preferences:

```sql
CREATE TABLE user_profiles (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL,
    preferences JSONB DEFAULT '{}'
);
```

## Implementation

### Dual Writes Setup

During Phase 1, we implement dual writes in our application code. This requires modifications to the user profile service to write to both the old and new schemas simultaneously. Below is a simplified implementation in Python using an ORM:

```python
class UserProfileService:
    def __init__(self, old_db_session, new_db_session):
        self.old_db = old_db_session
        self.new_db = new_db_session

    def create_user_profile(self, user_data):
        # Write to old schema
        old_profile = UserProfileOld(**user_data)
        self.old_db.add(old_profile)
        
        # Write to new schema
        new_profile = UserProfileNew(**user_data)
        self.new_db.add(new_profile)
        
        # Commit both transactions
        self.old_db.commit()
        self.new_db.commit()
```

### Online Schema Change

To facilitate online changes, we can leverage database features such as PostgreSQL's `ALTER TABLE ... ADD COLUMN` which allows adding new columns without locking the table. However, we must ensure that our application is aware of which schema to interact with based on the presence of new fields.

### Validating Data Consistency

During Phase 1, we will create a background job to periodically validate the data consistency between the two schemas. If discrepancies are found, alerts can be triggered for manual intervention.

```python
def validate_profiles(old_db_session, new_db_session):
    old_profiles = old_db_session.query(UserProfileOld).all()
    new_profiles = new_db_session.query(UserProfileNew).all()

    discrepancies = []
    for old, new in zip(old_profiles, new_profiles):
        if old.username != new.username or old.email != new.email:
            discrepancies.append((old, new))

    return discrepancies
```

## Failure Modes & Debugging

### Symptoms of Failure
1. **Application Errors:** Users may experience 500 errors if the application attempts to read or write to a missing or invalid field.
2. **Data Inconsistencies:** If dual writes fail due to a transient database issue, it may result in mismatched data between old and new schemas.

### Diagnosis
1. **Error Logs:** Monitor application logs for exceptions related to database operations. 
2. **Data Validation Reports:** Review the output from the data validation job for any discrepancies.

## Rollback Strategy

If issues are encountered during the migration, a rollback strategy must be in place. In the dual-write scenario, if we need to revert to the original schema, we can simply stop writing to the new schema and continue using the old one.

### Implementation of Rollback

Here’s how we can implement a rollback mechanism:

1. **Disable Dual Writes:** Update the service to stop writing to the new schema.
2. **Data Migration Back (if necessary):** If data in the new schema is valid and needed, write a migration script to move data back to the old schema.

```python
def rollback_user_profiles(new_db_session):
    new_profiles = new_db_session.query(UserProfileNew).all()
    for profile in new_profiles:
        old_profile = UserProfileOld(user_id=profile.user_id, username=profile.username, email=profile.email)
        old_db_session.add(old_profile)
    old_db_session.commit()
```

## Trade-offs

### When NOT to Use This Approach
1. **Low Traffic Applications:** For applications with low traffic, simpler migration strategies (like offline migrations) may be more efficient.
2. **Complex Relationships:** If the schema change involves complex foreign key relationships that require cascading updates, dual writes can complicate the migration process.
3. **Limited Resources:** If the team lacks the resources to monitor and validate dual writes effectively, the risk of data inconsistency increases.

## Performance & Cost

### Latency and Throughput
Assuming our application handles 100 requests per second with each user profile read/write averaging 10ms:

- **Old Schema:** Total latency for 100 writes = 100 * 10ms = 1000ms (1 second).
- **New Schema with Dual Writes:** Total latency = 100 * 2 * 10ms = 2000ms (2 seconds).

### Cloud Cost
Assuming each database write costs $0.01 and we expect 10,000 writes during the migration:

- Old Schema Cost: $0.01 * 10,000 = $100.
- New Schema Cost (Dual Writes): $0.02 * 10,000 = $200.

The additional cost for dual writes can be significant, especially in high-volume environments.

## Observability

### Metrics
1. **Database Latency:** Track the time taken for reads and writes in both schemas.
2. **Error Rates:** Monitor the percentage of failed writes or reads.
3. **
