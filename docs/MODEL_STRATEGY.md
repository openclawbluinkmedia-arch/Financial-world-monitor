# Model Strategy

## Abstraction Layer

All AI model interactions go through `backend/app/ai/router.py` which exposes
four operations:

| Operation  | Description                                      |
|-----------|--------------------------------------------------|
| `generate`| Chat/completion against a reasoning LLM          |
| `embed`   | Convert text to vector embeddings                |
| `rerank`  | Re-rank documents by relevance to a query        |
| `classify`| Zero-shot text classification                    |

Embeddings always use the local CPU-based adapter. The remaining three
operations route through the configured provider(s).

## Provider Selection

Controlled entirely by the `DEPLOYMENT_MODE` environment variable.

### Dev Mode (`DEPLOYMENT_MODE=dev`)

- **Primary**: NVIDIA NIM (`https://integrate.api.nvidia.com/v1`)
  - Model: configured via `NVIDIA_MODEL_SLUG` in `.env`
- **Fallback**: OpenRouter (`https://openrouter.ai/api/v1`)
  - Model: configured via `OPENROUTER_MODEL_SLUG` in `.env`
  - Activated automatically on HTTP 429 (rate-limit) or network error

### Customer Mode (`DEPLOYMENT_MODE=customer`)

- **Single provider**: Self-hosted vLLM endpoint
  - URL: configured via `VLLM_BASE_URL` in `.env`
  - Model: configured via `VLLM_MODEL_SLUG` in `.env`
  - No external API calls are made

## ⚠ Important

Hosted free tiers (NVIDIA NIM, OpenRouter) are for **development and demo
purposes only**, using **public or synthetic data**. Real customer data must
only be processed in `DEPLOYMENT_MODE=customer` with a self-hosted endpoint.

## Model Names

Model slugs are **never hard-coded** in business logic. They are read from
`.env` at startup. This allows operators to swap models without code changes.
