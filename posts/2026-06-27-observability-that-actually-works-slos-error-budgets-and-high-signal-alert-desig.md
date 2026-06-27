# Observability that Actually Works: SLOs, Error Budgets, and High-Signal Alert Design

*How to implement a robust observability framework for a microservices architecture.*

## Introduction

In the realm of distributed systems, observability is often touted as a crucial component for maintaining reliability and performance. However, many teams struggle to translate observability theory into actionable practices. This article will explore a focused scenario involving a microservices architecture, specifically targeting the implementation of Service Level Objectives (SLOs), error budgets, and high-signal alert design. By following a structured reasoning chain—constraints leading to design, implementation, and validation—you will learn how to create an observability framework that genuinely works.

## Constraints

To ground our scenario, let's consider a fictional e-commerce platform composed of several microservices: 

1. **User Service**: Handles account creation and authentication.
2. **Product Service**: Manages product listings and inventory.
3. **Order Service**: Processes customer orders.

### Key Constraints:
- **Latency**: Users expect responses within 200 ms for most requests.
- **Availability**: The platform must maintain 99.9% uptime.
- **Throughput**: The system should handle 1000 requests per second during peak load.

These constraints will guide our design for observability, ensuring we focus on the most critical aspects that impact user experience.

## Designing SLOs and Error Budgets

### SLOs Definition

Service Level Objectives help quantify how well a service meets user expectations. Based on our constraints, we can set the following SLOs:

1. **Latency SLO**: 95th percentile response time of < 200 ms.
2. **Availability SLO**: 99.9% uptime per month.
3. **Throughput SLO**: 1000 requests per second sustained for 95% of the time.

### Error Budgets

An error budget allows teams to balance between innovation and reliability. It is calculated as follows:

```
Error Budget = (1 - Availability SLO) * Total Time
```

For our 99.9% availability:

```
Error Budget = (1 - 0.999) * 30 days * 24 hours * 60 minutes * 60 seconds
              = 2.592 seconds per month
```

This error budget permits 2.592 seconds of downtime per month. Teams should aim to consume this budget wisely, using it to drive feature releases while remaining conscious of reliability.

## Implementation

### Metrics Collection

To effectively monitor our SLOs, we need to implement metrics collection using an observability tool like Prometheus. Below is a code snippet for a Flask-based User Service that tracks response times and availability:

```python
from flask import Flask, request, jsonify
from prometheus_client import start_http_server, Summary, Counter
import time

app = Flask(__name__)

# Metrics
REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
REQUEST_COUNT = Counter('request_count', 'Total request count')

@app.route('/users', methods=['POST'])
@REQUEST_TIME.time()
def create_user():
    REQUEST_COUNT.inc()
    # Simulate user creation logic
    time.sleep(0.05)  # Simulated processing time
    return jsonify({"status": "success"}), 201

if __name__ == '__main__':
    start_http_server(8000)  # Expose metrics on port 8000
    app.run(host='0.0.0.0', port=5000)
```

This implementation captures the time taken to process requests and counts the total requests, both of which are essential for calculating our SLOs.

### Alerting Design

To create high-signal alerts, we need to define conditions that indicate significant issues without overwhelming the team. A good approach is to set alerts based on SLO breaches.

Using Prometheus Alertmanager, you can configure alerts as follows:

```yaml
groups:
- name: service_alerts
  rules:
  - alert: HighLatency
    expr: histogram_quantile(0.95, sum(rate(request_processing_seconds_bucket[5m])) by (le)) > 0.2
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "High latency detected in User Service"
      description: "95th percentile latency is above 200 ms for 5 minutes."
  
  - alert: LowAvailability
    expr: (sum(rate(request_count[1m])) / (30 * 24 * 60)) < 0.999
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: "Availability SLO breached"
      description: "Service is below 99.9% availability."
```

These alerts serve to notify the team when the service is not meeting user expectations, allowing proactive intervention before incidents escalate.

## Validation

### Testing SLOs

Validation of SLOs should occur through synthetic and real user monitoring. For synthetic checks, you can use a tool like `curl` or `Postman` to regularly ping your endpoints:

```bash
curl -w "@curl-format.txt" -o /dev/null -s "http://localhost:5000/users"
```

Where `curl-format.txt` specifies how to format the output for latency analysis:

```
time_total:  %{time_total}\n
```

Regularly check the output against your defined SLOs to ensure compliance.

### Observability Tools

To visualize and analyze metrics, you can use Grafana in combination with Prometheus. Set up dashboards that display:

- Latency distributions
- Request counts
- Availability trends over time

These visualizations allow for quick identification of trends and anomalies.

## Failure Modes & Debugging

### Common Symptoms

1. **Increased Latency**: If requests take longer than expected, you may start to see alerts from the HighLatency rule.
2. **Service Downtime**: If the LowAvailability alert triggers, it indicates that requests are failing more than anticipated.

### Diagnosis Steps

1. **Check Logs**: Look for error messages in your application logs. Ensure that your logging captures sufficient context.
2. **Examine Metrics**: Use Prometheus queries to isolate the affected service and examine its metrics in Grafana.
3. **Trace Requests**: Use distributed tracing (e.g., Jaeger or Zipkin) to visualize the request path and identify bottlenecks.

## Trade-offs

### When NOT to Use This Approach

1. **Simple Applications**: If your application is monolithic and has minimal traffic, the overhead of implementing complex observability practices may not justify the effort.
2. **Resource Constraints**: If your team lacks the capacity to maintain observability tools or the
