# Model Strategy

## Abstraction Layer

All AI model interactions go through `backend/app/ai/router.py` which exposes
four operations:

| Operation  | Description                                      | Provider |
|-----------|--------------------------------------------------|----------|
| `generate`| Chat/completion against a reasoning LLM          | NVIDIA NIM → OpenRouter → vLLM |
| `embed`   | Convert text to vector embeddings                | Local CPU (sentence-transformers) |
| `rerank`  | Re-rank documents by relevance to a query        | NVIDIA NIM → OpenRouter → vLLM |
| `classify`| Zero-shot text classification                    | NVIDIA NIM → OpenRouter → vLLM |

Embeddings always use the local CPU-based adapter. The remaining three
operations route through the configured provider(s) with automatic fallback.

## Provider Selection

Controlled entirely by the `DEPLOYMENT_MODE` environment variable.

### Dev Mode (`DEPLOYMENT_MODE=dev`)

- **Primary**: NVIDIA NIM (`https://integrate.api.nvidia.com/v1`)
  - Model: Qwen/Qwen3.5-397B-A17B (activated MoE, ~27B active params)
  - Free tier: 1000 req/day rate limit
- **Fallback**: OpenRouter (`https://openrouter.ai/api/v1`)
  - Model: Qwen/Qwen3.7-Plus
  - Activated on HTTP 429 (rate-limit) or network error
- **Local embeddings**: BAAI/bge-m3 on CPU via sentence-transformers

### Customer Mode (`DEPLOYMENT_MODE=customer`)

- **Single provider**: Self-hosted vLLM endpoint
  - Model: Qwen/Qwen3.5-397B-A17B (or compatible)
  - No external API calls — data never leaves your network
  - Requires NVIDIA GPU with >=24GB VRAM

## ⚠ Data Isolation Warning

Hosted free tiers (NVIDIA NIM, OpenRouter) are for **development and demo
purposes only**, using **public or synthetic data**. Real customer data must
only be processed in `DEPLOYMENT_MODE=customer` with a self-hosted endpoint.

## Model Names

Model slugs are **never hard-coded** in business logic. They are read from
`.env` at startup, allowing operators to swap models without code changes.

## Hardware Requirements

| Mode | GPU | RAM | Storage |
|------|-----|-----|---------|
| Dev (hosted API) | None | 16GB | 20GB |
| Customer (vLLM, 4-bit) | 1x 24GB VRAM | 64GB | 100GB |
| Customer (vLLM, FP16) | 2x 40GB VRAM | 128GB | 200GB |

## Embedding Strategy

- **Model**: BAAI/bge-m3 (1024-dim, multilingual)
- **Deployment**: Local CPU via sentence-transformers
- **Cache**: Embeddings stored in `evidence.embedding` column (vector index)
- **Never external**: Embeddings are computed locally and never sent over the
  network

## Fallback Behavior

```
generate(text) →
  1. Try NVIDIA NIM (primary)
  2. On HTTP 429/5xx/network error → try OpenRouter
  3. On OpenRouter failure → raise RuntimeError("All adapters failed")

rerank(query, docs) →
  Same fallback chain as generate

classify(text, labels) →
  Same fallback chain as generate
  NOTE: Classification uses LLM prompting, not a dedicated classifier.
        Confidence scores are based on logit analysis where available,
        otherwise default to 0.5.

embed(texts) →
  Local only — no fallback needed
```

## AI Safety

- **No fabricated citations**: Every evidence reference is validated against DB
- **Deterministic confidence**: 5-factor weighted model (never LLM-invented)
- **Fact vs inference**: Causal edges labelled VERIFIED / INFERRED / UNCERTAIN
- **Uncertainty shown**: `uncertainty` field (1.0 - confidence) on every result
- **Abstention**: System abstains when confidence <0.3 or validation fails
- **Contradiction handling**: Opposing-impact claims on same entity detected
- **Provenance**: Every impact includes citations + reasoning text
- **Prompt-injection resistance**: Evidence text is parameterized, user text is
  truncated to 2000 chars, strict JSON schema enforced on LLM output
