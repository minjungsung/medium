# Making Microservices Survivable: Timeouts, Hedged Requests, Circuit Breakers, and Fallbacks  
*Strategies to enhance resilience in microservices architecture.*

## Thesis Statement
In a microservices architecture, designing for survivability is paramount to maintain system reliability under failure conditions. By effectively implementing timeouts, hedged requests, circuit breakers, and fallbacks within a service-focused scenario, we can significantly enhance resilience and ensure continued service availability.

## Constraints and Design Considerations
When designing resilient microservices, we must consider the following constraints:

1. **Latency Sensitivity**: The system must remain responsive under varying load conditions. A latency threshold should be defined based on service-level objectives (SLOs).
2. **Dependency Changes**: Microservices often rely on other services, which may experience varying levels of availability.
3. **Resource Limits**: Memory and CPU usage must be monitored to prevent resource exhaustion.

Given these constraints, we will implement a microservice that consumes a weather API to provide weather data for a travel application. The system will incorporate timeouts, hedged requests, circuit breakers, and fallbacks to ensure resilience.

### Architectural Overview
In our microservice architecture, we will deploy:
- **Service A**: The client service that makes requests to the weather API.
- **Service B**: The weather API service.

The design will use:
- **Timeouts**: To prevent long wait times for responses.
- **Hedged Requests**: To mitigate latency by sending multiple requests to different instances of the API.
- **Circuit Breakers**: To prevent failure propagation.
- **Fallbacks**: To provide alternative behaviors when the primary service fails.

## Implementation Details

### 1. Timeouts
We will set a timeout for requests to the weather API. This is critical to avoid waiting indefinitely for a response.

```python
import requests
from requests.exceptions import Timeout

def get_weather_data(api_url):
    try:
        response = requests.get(api_url, timeout=2)  # 2 seconds timeout
        response.raise_for_status()
        return response.json()
    except Timeout:
        return {"error": "Request timed out"}
    except requests.RequestException as e:
        return {"error": str(e)}
```

### 2. Hedged Requests
To further mitigate latency, we can implement hedged requests. This involves sending multiple requests to different instances of the weather API and returning the first successful response.

```python
import concurrent.futures

def get_weather_hedged(api_urls):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_to_url = {executor.submit(get_weather_data, url): url for url in api_urls}
        for future in concurrent.futures.as_completed(future_to_url):
            result = future.result()
            if "error" not in result:
                return result
    return {"error": "All requests failed"}
```

### 3. Circuit Breakers
To prevent flooding the weather API with requests during failures, we can implement a circuit breaker pattern.

```python
import time

class CircuitBreaker:
    def __init__(self, failure_threshold=3, recovery_timeout=10):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.state = "CLOSED"
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = None

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                return {"error": "Circuit is open"}

        try:
            result = func(*args, **kwargs)
            self.reset()
            return result
        except Exception:
            self.record_failure()
            return {"error": "Service unavailable"}

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def reset(self):
        self.failure_count = 0
        self.state = "CLOSED"
```

### 4. Fallbacks
Finally, we can implement a fallback mechanism to provide alternative data or behavior when the primary service fails.

```python
def fallback_weather_data():
    return {"data": "Fallback weather data"}

def get_weather_with_fallback(api_urls, circuit_breaker):
    result = circuit_breaker.call(get_weather_hedged, api_urls)
    if "error" in result:
        return fallback_weather_data()
    return result
```

## Validation and Testing
To validate the implementation, we will conduct chaos testing to simulate service outages. We will intentionally induce failures in the weather API to ensure the circuit breaker and fallback mechanisms respond as expected.

### Failure Modes & Debugging
**Symptoms**: The service becomes slow to respond or starts returning errors.

**Diagnosis**:
1. **Timeouts**: If the service frequently returns timeout errors, the API may be overloaded or unresponsive.
2. **Circuit Breaker State**: Check the state of the circuit breaker. If it is open, the service is temporarily blocked from making requests.
3. **Fallback Behavior**: Monitor how often the fallback data is returned. Frequent fallbacks may indicate issues with the primary service.

### Trade-offs
While the above approaches enhance resilience, they come with trade-offs:
- **Increased Complexity**: The introduction of circuit breakers and hedged requests adds complexity to the codebase.
- **Resource Usage**: Hedged requests may lead to increased resource consumption due to multiple simultaneous requests.
- **Latency**: If not configured carefully, timeouts could lead to increased latency if the system frequently oscillates between states.

**When Not to Use**:
- For simple applications with low traffic and minimal dependencies, implementing such patterns may be overkill.
- In cases where the service can afford to block indefinitely (e.g., internal APIs), timeouts may not be necessary.

## Performance & Cost
Assuming our service makes 100 requests per second to the weather API:
- **Without Timeouts**: If each request takes 5 seconds on average, the service would experience significant latency, potentially leading to timeouts on the client side.
- **With Timeouts**: Setting a timeout of 2 seconds allows the service to recover quickly from unresponsive APIs, maintaining an average response time of ~2 seconds.
- **Hedged Requests**: Sending two hedged requests could double the network cost but reduce the average response time to <2 seconds when one of the requests succeeds.

For cloud costs, consider the implications of increased API calls. If each API call costs $0.01, hedging requests could lead to a 100% increase in costs, but the trade-off
