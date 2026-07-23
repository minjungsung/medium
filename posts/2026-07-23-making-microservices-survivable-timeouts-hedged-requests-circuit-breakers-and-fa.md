# Making Microservices Survivable: Timeouts, Hedged Requests, Circuit Breakers, and Fallbacks
*Strategies for ensuring resilience in a microservices architecture.*

## Introduction

In today's microservices ecosystems, maintaining system resiliency is non-negotiable. As the number of services grows, so does the complexity of interactions, leading to increased potential for failures. This article will focus on a specific scenario: a microservices-based e-commerce platform where the payment service is critical to order processing. We will explore how to implement timeouts, hedged requests, circuit breakers, and fallbacks to enhance the survivability of this payment service.

## Constraints

The following constraints guide our design:

1. **Service Interdependence**: The payment service depends on third-party payment gateways that can be unreliable.
2. **User Experience**: Payment failures directly affect user satisfaction, requiring swift recovery mechanisms.
3. **Throughput & Latency Requirements**: The system must handle high traffic while maintaining low response times.
4. **Cost Considerations**: Any solution must minimize additional infrastructure costs, particularly in cloud environments.

## Design

Based on these constraints, we propose a layered approach to service resilience. 

1. **Timeouts**: Set strict limits on how long to wait for a response from the payment gateway.
2. **Hedged Requests**: Send multiple requests to different gateways simultaneously to increase the chances of a successful transaction.
3. **Circuit Breakers**: Prevent the system from overwhelming a failing service by temporarily blocking requests to it.
4. **Fallbacks**: Provide alternative responses when a service fails, ensuring the user experience remains intact.

This design creates a robust safety net around the critical payment service.

## Implementation

Let's implement each of these strategies in Python, utilizing the `aiohttp` library for asynchronous HTTP requests.

### Timeouts

Set a timeout for requests to the payment gateway. This ensures that if a request takes too long, it can be retried or handled differently.

```python
import aiohttp
import asyncio

async def make_payment_request(url, data):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=data, timeout=5) as response:
                return await response.json()
        except asyncio.TimeoutError:
            print("Payment request timed out")
            return None
```

### Hedged Requests

Send requests to multiple gateways simultaneously, returning the first successful response.

```python
async def hedged_payment_requests(gateways, data):
    tasks = [make_payment_request(gateway, data) for gateway in gateways]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    
    for task in done:
        if task.result() is not None:
            return task.result()
    
    for task in pending:
        task.cancel()
    
    return None
```

### Circuit Breaker

Implement a simple circuit breaker that tracks failures and prevents requests once a threshold is reached.

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=10):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None

    def is_open(self):
        if self.failure_count >= self.failure_threshold:
            if (self.last_failure_time is None or 
                (time.time() - self.last_failure_time) < self.recovery_timeout):
                return True
        return False

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

    def record_success(self):
        self.failure_count = 0
```

### Fallbacks

Provide a fallback method that executes when payment services fail.

```python
async def fallback_payment():
    # Implementing a simple logging mechanism or notifying the user
    print("Executing fallback mechanism: Payment processing failed")
    return {"status": "fallback", "message": "Please try again later."}
```

### Bringing It All Together

Here’s how we can wire these components together in the actual payment processing logic:

```python
async def process_payment(gateways, data):
    circuit = CircuitBreaker()
    
    if circuit.is_open():
        return await fallback_payment()
    
    result = await hedged_payment_requests(gateways, data)
    
    if result is None:
        circuit.record_failure()
        return await fallback_payment()

    circuit.record_success()
    return result
```

## Failure Modes & Debugging

### Symptoms

1. **Frequent Timeouts**: Users experience delays or failures during payment processing.
2. **Circuit Breaker Activation**: The circuit breaker frequently opens, blocking requests unexpectedly.

### Diagnoses

- **Timeouts**: Check network latency between your service and the payment gateways. Use a tool like `ping` or an application performance monitoring (APM) tool to measure latency.
  
- **Circuit Breaker**: If the circuit opens too often, analyze the failure response from the payment gateways. Are they returning errors, or is the network unreliable? Review logs for patterns.

## Trade-offs

### When NOT to Use This Approach

1. **Simple Use Cases**: If your application has only a single payment gateway with guaranteed uptime, implementing these resiliency patterns may introduce unnecessary complexity.
2. **Low Traffic Applications**: For applications with low traffic, the overhead of maintaining a circuit breaker or hedged requests might outweigh the benefits.

## Performance & Cost

### Latency

- **Timeouts**: Setting a 5-second timeout ensures quick failure detection, but if the average response time from the payment gateway is 2 seconds, the timeout should be higher to avoid unnecessary timeouts.
  
- **Hedged Requests**: Sending requests to 3 gateways can lead to an increase in latency. If each request takes 2 seconds, the worst-case scenario for a hedged request is 2 seconds, assuming one of the requests succeeds quickly.

### Throughput

- A circuit breaker may reduce throughput during failure scenarios but allows the system to recover faster when the service is back online.

### Cost

Using hedged requests can result in increased outbound requests to third-party services, potentially leading to higher costs. For example, if a payment gateway charges $0.01 per request and we send 3 hedged requests, the cost could rise to $0.03 for a single transaction.

## Observability

1. **Metrics**: Track the following metrics:
   - Request latency (both successful and failed)
   - Circuit breaker state (open/closed)
   - Number of hedged requests sent

2. **Logs**: Capture logs for each payment attempt, including responses from gateways, timeouts, and fallback activations.

3. **Traces**:
