# RAG Architecture at Scale: Late Chunking and Contextual Retrieval in Production
*Moving past naive text splitting requires aligning token-level cross-attention with vector space retrieval to solve boundary loss in enterprise codebases.*

## The Constraint Horizon of Naive RAG

Naive Retrieval-Augmented Generation (RAG) relies on fixed-size sliding-window chunking (e.g., 512 tokens with 64-token overlap) combined with dense bi-encoder embeddings. For a mature enterprise codebase or dense technical documentation system, this architecture fails predictably. 

Consider a production workload indexing a multi-tenant monorepo containing 4 million lines of TypeScript and Go. A function definition sits at lines 480–520 of a file, but its critical type definitions, authentication guards, and interface implementations live in lines 20–50 and lines 120–150. When a sliding window splits this file into isolated 512-token chunks, the semantic context is fractured across boundaries. 

Standard chunking creates three cascading failures:
1. **Context Fragmentation:** Core logic is severed from its enclosing scope, resulting in embeddings that lack the necessary local context.
2. **Lexical-Semantic Mismatch:** Queries targeting domain-specific jargon fail because the chunk's vector is dominated by generic boilerplate or syntax tokens.
3. **Retrieval Blindness:** Bi-encoders compress an entire chunk into a single vector, losing the fine-grained token interactions required to match precise technical queries.

To solve this, we must evaluate three paradigms: Naive Chunking, Late Chunking (preserving transformer context windows before pooling), and Contextual Retrieval (injecting LLM-generated document-level context into individual chunks).

## Architectural Evolution: From Bi-Encoder Isolation to Late Contextualization

To ground our design, assume a target production system: a code-search and documentation RAG pipeline handling 100 QPS with a p99 latency SLA of 400ms for retrieval. The embedding model is a long-context transformer (e.g., `jina-embeddings-v3` or `bge-large-en-v1.5`), and the generation model is a quantized 70B parameter LLM hosted on vLLM.

```
[ Raw Document / Code File (e.g., 8k tokens) ]
       │
       ├─► Naive Chunking ────────► Fixed Windows ──► Bi-Encoder ──► Vector DB
       │
       ├─► Late Chunking ─────────► Full Pass ────► Mean Pool ───► Vector DB
       │
       └─► Contextual Retrieval ──► LLM Context ──► Bi-Encoder ──► Vector DB
```

### 1. Late Chunking Implementation
Late chunking reverses the traditional pipeline. Instead of chunking text *before* embedding, we pass the entire long-form document (up to the model's maximum context length, e.g., 8192 tokens) through the transformer backbone first. We then apply token-level mean pooling *after* the transformer layers, mapped back to the original chunk boundaries. This ensures every token in a chunk retains the cross-attention context of the entire source document.

```python
import torch
from transformers import AutoTokenizer, AutoModel
from typing import List, Dict, Any

class LateChunkingEmbedder:
    def __init__(self, model_name: str = "jinaai/jina-embeddings-v3", device: str = "cuda"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True).to(device)
        self.device = device

    def _get_token_ranges(self, full_text: str, chunks: List[str]) -> List[Dict[str, int]]:
        """Map character-level chunk spans to token-level indices."""
        encoding = self.tokenizer(full_text, return_offsets_mapping=True, add_special_tokens=False)
        offsets = encoding["offset_mapping"]
        
        token_ranges = []
        curr_char_idx = 0
        
        for chunk in chunks:
            chunk_start = full_text.find(chunk, curr_char_idx)
            chunk_end = chunk_start + len(chunk)
            curr_char_idx = chunk_end
            
            start_token = None
            end_token = None
            
            for idx, (start, end) in enumerate(offsets):
                if start >= chunk_start and start_token is None:
                    start_token = idx
                if end <= chunk_end:
                    end_token = idx + 1
                    
            token_ranges.append({"start": start_token, "end": end_token})
            
        return token_ranges

    @torch.no_grad()
    def embed_document(self, full_text: str, chunks: List[str]) -> torch.Tensor:
        inputs = self.tokenizer(
            full_text, 
            return_tensors="pt", 
            padding=True, 
            truncation=True, 
            max_length=8192
        ).to(self.device)
        
        model_output = self.model(**inputs)
        token_embeddings = model_output.last_hidden_state[0] # Shape: (seq_len, hidden_dim)
        
        token_ranges = self._get_token_ranges(full_text, chunks)
        chunk_embeddings = []
        
        for r in token_ranges:
            span_embeddings = token_embeddings[r["start"]:r["end"]]
            # Mean pooling over the token span that retains global context
            pooled = torch.mean(span_embeddings, dim=0)
            chunk_embeddings.append(pooled)
            
        return torch.stack(chunk_embeddings)
```

### 2. Contextual Retrieval Implementation
Late chunking is computationally expensive and requires transformer infrastructure capable of handling large context lengths at ingest time. Contextual Retrieval offers an alternative: use a fast, cheap LLM (e.g., Claude 3.5 Haiku or GPT-4o
