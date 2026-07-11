# Making Microservices Survivable: Timeouts, Hedged Requests, Circuit Breakers, and Fallbacks  
*Strategies for enhancing resilience in distributed systems.*

## Thesis

In a microservices architecture, ensuring service survivability is paramount for maintaining user experience and system reliability. By implementing timeouts, hedged requests, circuit breakers, and fallbacks, we can create a robust framework that mitigates the cascading failures often seen in distributed systems. We will focus on a real-world scenario involving a payment processing microservice that communicates with various external services, demonstrating how these strategies can be effectively applied.

## Constraints and Design Considerations

### Constraints
1. **Network latency**: External service calls can introduce unpredictable delays, affecting overall responsiveness.
2. **Service reliability**: Third-party payment providers may experience outages or slowdowns.
3. **User experience**: Any delay in processing payments can lead to a poor user experience, risking abandonment of transactions.

### Design
Given these constraints, our design will incorporate the following components:
- **Timeouts**: To avoid waiting indefinitely for responses from external services.
- **Hedged requests**: To send parallel requests to multiple services, reducing the chance of failure.
- **Circuit Breakers**: To prevent the system from making requests to a service that's likely to fail.
- **Fallbacks**: To provide a graceful degradation of functionality when services are unavailable.

## Implementation

### Timeouts
To implement timeouts, we will set a maximum duration for requests to external payment services. In Python, we can use the `httpx` library, which allows us to specify timeouts easily.

```python
import httpx

async def process_payment(payment_data):
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post("https://payment-provider.com/api/pay", json=payment_data)
        response.raise_for_status()
        return response.json()
```

In this example, we set a timeout of 5 seconds. If the payment provider does not respond within this timeframe, a `TimeoutException` is raised.

### Hedged Requests
Hedged requests can be implemented by sending requests to multiple payment providers simultaneously and using the first successful response. This can be done using `asyncio` in Python.

```python
import asyncio

async def hedged_payment(payment_data):
    providers = [
        "https://payment-provider-a.com/api/pay",
        "https://payment-provider-b.com/api/pay"
    ]
    
    async def fetch(url):
        async with httpx.AsyncClient(timeout=5.0) as client:
            return await client.post(url, json=payment_data)

    tasks = [fetch(provider) for provider in providers]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)

    for task in done:
        if task.exception() is None:
            return task.result().json()
    raise Exception("All payment providers failed.")
```

In this code, we create a list of providers and use `asyncio.wait` to handle multiple requests. The first successful payment response is returned, while any failures are managed later.

### Circuit Breakers
A circuit breaker pattern can help prevent excessive load on a failing service. In Python, we can implement a simple circuit breaker class.

```python
import time

class CircuitBreaker:
    def __init__(self, failure_threshold, recovery_time):
        self.failure_threshold = failure_threshold
        self.failure_count = 0
        self.last_failure_time = None
        self.recovery_time = recovery_time

    def call(self, func, *args, **kwargs):
        if self.is_open():
            raise Exception("Circuit is open. Please try again later.")

        try:
            result = func(*args, **kwargs)
            self.failure_count = 0  # Reset on success
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            raise e

    def is_open(self):
        if self.failure_count >= self.failure_threshold:
            if time.time() - self.last_failure_time < self.recovery_time:
                return True
        return False
```

In this implementation, we check if the circuit is open before calling the payment function. If the number of failures exceeds the threshold, the circuit will stay open for the specified recovery time.

### Fallbacks
Finally, we can implement fallbacks to provide alternative behavior when a service fails. For example, if both payment providers are unavailable, we could log the transaction for later processing.

```python
async def fallback_payment(payment_data):
    try:
        return await hedged_payment(payment_data)
    except Exception:
        # Fallback logic
        log_transaction(payment_data)
        return {"status": "pending", "message": "Payment processing delayed. Please check back later."}
```

In the fallback implementation, we attempt the hedged payment and log the transaction if all attempts fail. 

## Validation

### Failure Modes & Debugging
1. **Timeouts**: If the timeouts are too short, valid requests may fail. Symptoms include frequent timeout exceptions. Diagnosing this can be done by monitoring response times and adjusting timeout durations based on historical data.
  
2. **Hedged Requests**: If the hedged requests are not implemented correctly, this can lead to multiple failures or unintended overload on providers. Symptoms include excessive logs of failures. Using throttling or limiting the number of concurrent requests can mitigate this.

3. **Circuit Breakers**: If the threshold values for the circuit breakers are too sensitive, legitimate spikes in traffic may cause unnecessary failures. Symptoms include constant open circuit alerts. Tuning these thresholds based on traffic patterns can help.

4. **Fallbacks**: If fallback logic is not adequately tested, it may lead to unhandled cases. Symptoms include unprocessed transactions. Extensive unit and integration testing can reveal weaknesses in fallback logic.

## Trade-offs

### When NOT to Use This Approach
1. **High Throughput Systems**: If your system handles a very high volume of requests, implementing all these strategies may introduce additional overhead that could degrade performance.
  
2. **Simple Service Calls**: In scenarios where the service calls are guaranteed to be reliable (e.g., internal services with high SLAs), the overhead of implementing these patterns may outweigh their benefits.

3. **Latency-Sensitive Applications**: If your application is extremely sensitive to latency, the additional complexity and time introduced by circuit breakers and hedged requests may not be ideal.

## Performance & Cost

### Latency and Throughput
- **Timeouts**: Setting a timeout of 5 seconds means a user waits up to 5 seconds per request. If using hedged requests, this may double the wait time, leading to a maximum of 10 seconds for simultaneous
