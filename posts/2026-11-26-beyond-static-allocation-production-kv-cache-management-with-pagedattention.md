# Beyond Static Allocation: Production KV Cache Management with PagedAttention
*Optimizing LLM inference throughput and eliminating memory fragmentation through virtualized block-based memory management.*

Senior engineers scaling large language model (LLM) serving infrastructure inevitably hit a hard ceiling dictated not by compute (FLOP/s), but by memory capacity. As sequence lengths scale to 32k or 128k tokens, the Key-Value (KV) cache for self-attention balloons to consume up to 80% of high-bandwidth memory (HBM), choking batch sizes and driving up cost-per-token. 

The root cause of this bottleneck in traditional serving engines is static contiguous allocation. When an engine reserves memory for a request, it must pre-allocate a contiguous block sized for the maximum possible generation length (`max_tokens`). Because generation lengths are stochastic and requests arrive asynchronously, this design induces massive internal fragmentation (wasted pre-allocated space within a sequence's slot) and external fragmentation (unusable scattered free memory blocks).

To maximize throughput in high-concurrency environments, we must treat LLM memory management like an operating system manages virtual memory. By implementing PagedAttention—virtualizing the KV cache into non-contiguous physical blocks managed via a centralized block table—we can eliminate fragmentation, pack more concurrent requests into HBM, and safely enable prefix sharing across concurrent requests.

---

### Constraints & System Design

Consider a production LLM serving cluster running a 70B parameter model in FP16, handling 250 concurrent requests with an average context window of 4,000 input tokens and 500 output tokens. 

* **The Math of Static Allocation:** For 70B models, the KV cache footprint per token is $2 \times L \times H$, where $L$ is the number of layers and $H$ is the hidden dimension per layer. For a typical configuration ($L=80$, $H=8192$, FP16/2 bytes), 1 token requires roughly $2 \times 80 \times 8192 \times 2 = 2.62$ MB of KV cache. For a maximum sequence length of 8,192 tokens, a single request demands ~21.5 GB of HBM just for the cache. Across 250 concurrent requests, static allocation requires ~5.3 TB of VRAM—an impossibility on an 8x A100/H100 node.
* **Design Objectives:** We need an engine architecture that:
  1. Allocates physical memory lazily on demand, token by token or block by block.
  2. Maps non-contiguous physical memory blocks to contiguous logical sequences via a page table.
  3. Enables Copy-on-Write (CoW) semantics to support beam search, parallel sampling, and system prompt caching without duplicating HBM blocks.

```
Logical KV Cache (Sequence View):
[ Token 0-15 ] -> [ Token 16-31 ] -> [ Token 32-47 ]

Physical HBM Blocks (Non-contiguous):
Block 412: [ Token 32-47 ]
Block 12:  [ Token 0-15 ]
Block 89:  [ Token 16-31 ]

Block Table (Per Request):
[ Logical Block 0 ] -> Physical Block 12
[ Logical Block 1 ] -> Physical Block 89
[ Logical Block 2 ] -> Physical Block 412
```

---

### Implementation: The Paged KV Cache Manager

To realize virtual memory for LLMs, we implement a BlockAllocator and a BlockTable mapping abstraction. Below is a production-grade Python implementation of the KV block management layer that interfaces with the inference scheduler.

```python
import torch
from typing import Dict, List, Optional, Set

class BlockAllocator:
    """Manages physical KV cache blocks in GPU high-bandwidth memory."""
    def __init__(self, num_blocks: int, block_size: int, device: torch.device):
        self.num_blocks = num_blocks
        self.block_size = block_size
        self.device = device
        
        # Free list tracking available physical block IDs
        self.free_block_ids: List[int] = list(range(num_blocks))
        
        # Reference counts for Copy-on-Write / prefix sharing
        self.ref_counts: torch.Tensor = torch.zeros(num_blocks, dtype=torch.int32, device=device)

    def allocate(self, count: int) -> List[int]:
        if len(self.free_block_ids) < count:
            raise MemoryError(f"Out of KV cache memory. Requested {count}, available {len(self.free_block_ids)}")
        
        allocated = []
        for _ in range(count):
            block_id = self.free_block_ids.pop()
            self.ref_counts[block_id] = 1
            allocated.append(block_id)
        return allocated

    def free(self, block_ids: List[int]) -> None:
        for block_id in block_ids:
            if self.ref_counts[block_id] > 0:
                self.ref_counts[block_id] -= 1
                if self.ref_counts[block_id] == 0:
                    self.free_block_ids.append(block_id)

    def ref_block(self, block_id: int) -> None:
        self.ref_counts[block_id] += 1

    @property
    def available_blocks(self) -> int:
        return len(self.free_block_ids)


class SequenceBlockTable:
    """Maintains the mapping from logical sequence blocks to physical GPU blocks."""
    def __init__(self, block_size: int, allocator: BlockAllocator):
        self.block_size = block_size
        self.allocator = allocator
        self.table: List[int] = []

    def append_token(self, seq_len: int) -> Optional[int]:
        """Returns a physical block ID if a new block allocation is triggered."""
        logical_idx = (seq_len - 1) // self.block_size
