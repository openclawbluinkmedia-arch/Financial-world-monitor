# Model Evaluation

## Selected Models

| Operation | Model | License | VRAM | Source |
|-----------|-------|---------|------|--------|
| Reasoning/Generation | Qwen3.6-27B (Qwen/Qwen3.5-397B-A17B) | Apache 2.0 | ~24GB (4-bit) / ~60GB (FP16) | NVIDIA NIM / OpenRouter / vLLM |
| Embedding | BAAI/bge-m3 | MIT | 2GB (CPU) | Local, sentence-transformers |
| Reranking | BAAI/bge-reranker-v2-m3 | MIT | 4GB | Via provider API |
| Classification | ProsusAI/finbert (via API) | Apache 2.0 | — | Via provider API |
| NER | urchade/gliner_multi | MIT | 2GB | Local, GLiNER |

## Hardware Requirements

### Dev / Demo (laptop)
- CPU with AVX2 support
- 16GB RAM
- No GPU required (all AI via NVIDIA NIM / OpenRouter hosted APIs)
- Local embeddings run on CPU (bge-m3, ~2GB RAM)

### Production Self-Hosted (vLLM)
- 1x NVIDIA GPU with >=24GB VRAM (A10G, A100-40, L40S, or better)
- 64GB system RAM
- 8+ vCPU cores
- 100GB SSD for model cache + DB

### Production (Hosted API)
- No GPU required
- 16GB RAM, 4 vCPU minimum
- Requires NVIDIA/OpenRouter API keys

## Fallback Chain

```
generate() -> NVIDIA NIM -> OpenRouter -> error
rerank()   -> NVIDIA NIM -> OpenRouter -> error
classify() -> NVIDIA NIM -> OpenRouter -> error
embed()    -> Local CPU only (no fallback needed)
```

## Accuracy Benchmarks (Planned)

| Test | Target | Current |
|------|--------|---------|
| Entity extraction F1 | >=0.85 | TBD |
| Classification accuracy | >=0.80 | TBD |
| Citation validity | >=0.95 | TBD |
| Contradiction detection | >=0.90 | TBD |
## Hallucination Prevention

- Every factual claim must cite evidence
- Citation validation checks evidence existence in DB
- Confidence computed from 5 deterministic factors (never LLM-invented)
- Abstention triggered when confidence <0.3 or validation fails
- Human review flag set when confidence <0.4
