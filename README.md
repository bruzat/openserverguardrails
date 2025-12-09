# OpenServerGuardrails

Serveur FastAPI de guardrails pour applications LLM avec chaînes de moteurs, scores de sévérité, multilingue et observabilité.

## Démarrage

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Endpoints principaux :
- `POST /v1/chat/completions`
- `POST /v1/moderations`
- `POST /v1/classifications`
- `POST /v1/inference-mitigation`
- `GET /admin/health`
- `GET /admin/metrics`

Fonctionnalités clés :
- Chaînes de moteurs configurables avec actions graduées et profils par catégorie
- Pluggable guardrails : chaque moteur peut pointer vers un endpoint HTTP réel (NeMo, GuardrailsAI, OpenGuardrails, LLM Guard, WildGuard, BingoGuard, PolyGuard, AEGIS 2.0, Llama Guard 3) ou utiliser les heuristiques intégrées
- Moderation OpenAI native : l'étape finale de la chaîne peut appeler le modèle `omni-moderation-latest` si `OPENAI_API_KEY` est défini, avec repli heuristique sinon
- Détection de langue et traduction déterministe pour préserver la conformité multilingue
- Profil culturel appliquant des biais de sévérité sur les catégories sensibles
- Mitigation d'inférence avec masquage PII et circuit breaker configurable
- Observabilité par métriques Prometheus et hooks de télémétrie
- Option de traduction live (lorsque `deep-translator` est installée) via `ENABLE_LIVE_TRANSLATION=true`

## Tests

Run tests locally (unit, integration, and functional):

```bash
pytest
```

Generate a coverage report:

```bash
pytest --cov=app --cov-report=term-missing
```

Security and auth:

* Authentication is enforced by default. Set `PUBLIC_TOKEN` and `ADMIN_TOKEN`; startup fails without them when `REQUIRE_AUTH=true` (default).
* To intentionally disable bearer auth for local experiments, set `REQUIRE_AUTH=false`.
* Deploy behind a TLS terminator or set `REQUIRE_TLS=true` if TLS is enforced upstream.
* Configure real guardrail engines by setting `ENGINE_ENDPOINTS` (JSON map) and optional `ENGINE_API_KEYS` so the service will call external moderation backends instead of the built-in heuristics.
* To activate the native OpenAI moderation engine inside the default chain, set `OPENAI_API_KEY` (and optionally `OPENAI_BASE_URL`/`OPENAI_MODERATION_MODEL`).

### OpenAI backend

Switch to the OpenAI backend by supplying credentials and model metadata:

```bash
export DEFAULT_BACKEND=openai
export OPENAI_API_KEY=sk-...
export OPENAI_MODEL=gpt-4o-mini
uvicorn app.main:app
```

### Hugging Face backend

You can target a hosted text-generation-inference or Inference API endpoint while keeping the same FastAPI surface:

```bash
export DEFAULT_BACKEND=huggingface
export HF_ENDPOINT=https://api-inference.huggingface.co/models/your-model
export HF_API_TOKEN=hf_xxx   # optional if the endpoint is public
uvicorn app.main:app
```

The backend issues a minimal `POST {"inputs": "..."}` request and streams the resulting text in fixed-size chunks. Tests mock the HTTP layer to remain hermetic.

### vLLM backend

Use the OpenAI-compatible vLLM HTTP surface when available:

```bash
export DEFAULT_BACKEND=vllm
export VLLM_ENDPOINT=https://vllm.yourdomain.test
export VLLM_API_KEY=optional-token
export VLLM_MODEL=meta-llama-guard-3-8b   # optional; falls back to server default
uvicorn app.main:app
```

The adapter posts to `/v1/chat/completions` and supports streaming responses, mirroring the OpenAI API contract.

## Docker

```bash
docker build -t openserverguardrails .
docker run -p 8000:8000 openserverguardrails
```
