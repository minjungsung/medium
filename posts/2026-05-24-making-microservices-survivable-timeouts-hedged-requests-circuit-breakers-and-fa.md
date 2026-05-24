# Making Microservices Survivable: Timeouts, Hedged Requests, Circuit Breakers, and Fallbacks
*Strategies to enhance resilience in distributed systems.*

## Thesis

In a microservices architecture, ensuring survivability requires a multifaceted approach that incorporates timeouts, hedged requests, circuit breakers, and fallbacks. This article will explore how to implement these strategies in a hypothetical e-commerce system where a product catalog microservice must maintain availability and performance under load and potential failure scenarios.

## Constraints and Design Considerations

When designing a resilient system, we must consider the following constraints:

1. **Network Latency and Reliability**: Microservices communicate over the network, which is inherently unreliable. Timeouts must be defined to prevent cascading failures.
2. **Load Variability**: Traffic spikes during peak hours (e.g., sales events) necessitate mechanisms to handle increased load without degrading user experience.
3. **Dependency Chains**: The product catalog service relies on multiple other services (e.g., pricing, inventory). A failure in one of these can affect overall availability.
4. **Cost of Resilience**: Implementing resilience features incurs a performance and resource cost. We need to balance robustness with system efficiency.

To address these constraints, we can design our system to utilize timeouts, hedged requests, circuit breakers, and fallbacks.

### Implementation Overview

#### Timeouts

Timeouts are a first line of defense against unresponsive services. They allow the system to fail gracefully instead of waiting indefinitely. In our product catalog service, we set a timeout for external calls to the pricing service.

```python
import requests
from requests.exceptions import Timeout

def get_product_price(product_id):
    try:
        response = requests.get(f"http://pricing-service/products/{product_id}", timeout=2.0)
        response.raise_for_status()
        return response.json()['price']
    except Timeout:
        log("Pricing service timeout")
        return None
    except Exception as e:
        log(f"Error fetching price: {e}")
        return None
```

In this example, we define a 2-second timeout. If the pricing service does not respond in that time, we log the event and return `None`.

#### Hedged Requests

While timeouts help, they do not solve the problem of a slow service that eventually responds. Hedged requests can mitigate this by sending multiple requests simultaneously and taking the first successful response. This is particularly useful for external services that may have variable response times.

```python
import concurrent.futures

def hedged_price_request(product_id):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(get_product_price, product_id): i for i in range(2)}
        for future in concurrent.futures.as_completed(futures):
            try:
                price = future.result()
                if price is not None:
                    return price
            except Exception as e:
                log(f"Hedged request error: {e}")
    return None
```

Here, we use `ThreadPoolExecutor` to send two parallel requests for the product price. The first successful response will be returned, while others will be canceled.

#### Circuit Breakers

Circuit breakers prevent the application from making repeated requests to a failing service, allowing it to recover. We can implement a simple circuit breaker for the pricing service.

```python
import time

class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_time=10):
        self.failure_count = 0
        self.state = 'CLOSED'
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time
        self.last_failure_time = None

    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_time:
                self.state = 'HALF_OPEN'
            else:
                log("Circuit is open; rejecting request.")
                return None
        
        try:
            result = func(*args, **kwargs)
            self.failure_count = 0
            if self.state == 'HALF_OPEN':
                self.state = 'CLOSED'
            return result
        except Exception as e:
            self.failure_count += 1
            log(f"Circuit breaker triggered: {e}")
            if self.failure_count >= self.failure_threshold:
                self.state = 'OPEN'
                self.last_failure_time = time.time()
            return None

circuit_breaker = CircuitBreaker()

def get_price_with_circuit_breaker(product_id):
    return circuit_breaker.call(get_product_price, product_id)
```

In this implementation, the circuit breaker transitions between `CLOSED`, `OPEN`, and `HALF_OPEN` states based on the success or failure of requests. It provides a mechanism to back off from a failing service.

#### Fallbacks

Even with circuit breakers, there may be times when the service is completely unavailable. In these cases, we can implement fallback strategies to serve cached data or default responses.

```python
def get_price_with_fallback(product_id):
    price = get_price_with_circuit_breaker(product_id)
    if price is None:
        return get_cached_price(product_id)  # Fallback to cached data or defaults
    return price
```

In this function, if the circuit breaker returns `None`, we fall back to a cached price. This ensures that the user still receives some response, even if it is not the latest data.

## Performance and Cost

Implementing these resilience patterns comes with trade-offs. For instance, hedged requests can increase the load on the pricing service, leading to higher latency. In a system where requests to the pricing service average 100ms, a hedged request could double that latency during peak times.

Let's illustrate some hypothetical numbers:

- **Normal Load**: 100 requests/sec to pricing service, average response time of 100ms.
- **With Hedged Requests**: Potentially increases to 200 requests/sec, with 150ms average response time.

The cost implications extend to cloud resources as well. If we assume that each request costs $0.001, under normal load, the cost is $0.1 per second. With hedged requests, costs could double to $0.2 per second. These figures highlight the importance of monitoring and alerting on resource usage.

## Failure Modes & Debugging

### Common Symptoms

1. **Increased Latency**: If the service starts responding slowly, it could indicate a circuit breaker is open or the hedged requests are overwhelming the pricing service.
2. **Repeated Timeouts**: If timeouts occur frequently, it may be a sign of an overloaded service or network issues.
3. **Service Unavailability**: If the service returns `None` for all requests, the circuit breaker is likely in