# Building Reliable LLM Agents: Why State Machines Beat Autonomous ReAct Loops
*Autonomous ReAct loops fail predictably in production due to context rot and infinite tool-call loops; deterministic state machines with LLM-driven transitions provide the structural guarantees required for enterprise automation.*

## The Failure Mode of Autonomous Loops

For the past several years, the industry-standard architecture for LLM agents has been the autonomous ReAct (Reasoning and Acting) loop. A model receives a prompt, enters a `while` loop, and iteratively generates thoughts, selects tool calls, digests execution outputs, and repeats until it decides the task is complete. 

For trivial chat assistants or open-ended creative tasks, this unstructured autonomy is fine. For mission-critical workflows—such as automated enterprise invoice reconciliation or multi-system incident response—the ReAct loop is a liability. 

Autonomous loops fail for three structural reasons:
1. **Context Window Degradation (Context Rot):** As the loop iterates, the conversation history balloons. System prompts, intermediate tool outputs, stack traces, and recursive reasoning steps crowd the context window, causing the model to lose track of global constraints.
2. **Infinite Branching Loops:** When a tool returns an unexpected error (e.g., a database timeout or a validation failure), unconstrained models often try to "fix" it by calling the exact same tool with slightly perturbed arguments, burning through thousands of tokens and API budget without making forward progress.
3. **Implicit State:** Storing execution state purely in the conversational message history makes programmatic intervention, auditing, and human-in-the-loop (HITL) checkpoints nearly impossible. You cannot reliably pause a string of text tokens and resume it three days later after a compliance approval.

To build production-grade LLM agents, we must invert the paradigm: **Treat the LLM as a stateless computational unit that evaluates transitions within a deterministic Finite State Machine (FSM), rather than an autonomous agent driving its own execution flow.**

---

## Designing a Deterministic Agent Workload

To make this concrete, let us examine a specific production workload: **An Automated Cloud Infrastructure Provisioner**. 

This agent takes a natural language request from an internal developer (e.g., "Provision a secure PostgreSQL cluster with a read replica for the billing service"), inspects organizational compliance policies, generates Terraform code, validates it, runs a security scan, and executes the deployment.

### Constraints
* **Zero Undetected Drift:** The agent must never deploy code that fails security static analysis (Checkov/TfSec).
* **Idempotency:** If the process crashes midway, resuming must not duplicate cloud resources.
* **Deterministic Rollback:** If validation fails at step $N$, the system must cleanly transition to a remediation or failure state without relying on the LLM's conversational memory to "remember" it needs to clean up.
* **Human-in-the-Loop Interruption:** Deployments exceeding \$500/month in estimated cost require explicit synchronous approval via Slack before moving to execution.

Instead of writing a prompt like *"You are an infrastructure agent, figure out how to deploy this,"* we model the lifecycle as an explicit state machine:

```
[Init] ---> [ParseIntent] ---> [GenerateTerraform] ---> [SecurityScan]
                                                             |
                                      +----------------------+----------------------+
                                      | (Passed)                                    | (Failed)
                                      v                                             v
                             [CostEstimation]                               [RemediateCode]
                                      |
                                      +----------------------+
                                      | (Exceeds Threshold)  | (Within Threshold)
                                      v                      v
                             [AwaitingApproval]     [ExecuteDeployment]
                                      |                      |
                                      +----------+-----------+
                                                 |
                                                 v
                                             [Complete]
```

---

## Implementation

We implement this state machine using Python, leveraging Pydantic for strict structural typing between states and an explicit dispatcher. The LLM is invoked strictly within state handlers to perform specific extraction, generation, or evaluation tasks, but it never decides *which state comes next*.

```python
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import openai

class AgentState(str, Enum):
    INIT = "INIT"
    PARSE_INTENT = "PARSE_INTENT"
    GENERATE_TF = "GENERATE_TF"
    SECURITY_SCAN = "SECURITY_SCAN"
    COST_ESTIMATION = "COST_ESTIMATION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTE = "EXECUTE"
    REMEDIATE = "REMEDIATE"
    FAILED = "FAILED"
    COMPLETE = "COMPLETE"

class WorkflowContext(BaseModel):
    request_id: str
    raw_prompt: str
    parsed_spec: Optional[Dict[str, Any]] = None
    terraform_code: Optional[str] = None
    security_violations: list[str] = Field(default_factory=list)
    monthly_cost_usd: float = 0.0
    retry_count: int = 0
    current_state: AgentState = AgentState.INIT

class InfrastructureAgentEngine:
    def __init__(self, client: openai.OpenAI):
        self.client = client
        self.max_retries = 3

    def transition(self, ctx: WorkflowContext) -> WorkflowContext:
        # State machine dispatch table guarantees deterministic routing
        handlers = {
            AgentState.INIT: self._handle_init,
            AgentState.PARSE_INTENT: self._handle_parse_intent,
            AgentState.GENERATE_TF: self._handle_generate_tf,
            AgentState.SECURITY_SCAN: self._handle_security_scan,
            AgentState.COST_ESTIMATION: self._handle_cost_estimation,
            AgentState.AWAITING_APPROVAL: self._handle_awaiting_approval,
            AgentState.EXECUTE: self._handle_execute,
            AgentState.REMEDIATE: self._handle_remediate,
        }

        while ctx.current_state not in {AgentState.COMPLETE, AgentState.FAILED}:
            handler = handlers.get(ctx.current_state)
            if not handler:
                ctx.current_state = AgentState.FAILED
                break
            
            # Execute current state handler, returning updated context and next state
