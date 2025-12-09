# OpenServerGuardrails

Serveur FastAPI de guardrails pour applications LLM offrant chaînes de moteurs, scores de sévérité, multilingue, mitigation et observabilité. Le projet vise à couvrir le cahier des charges (endpoints /v1, moteurs multiples, profils culturels, sécurité, observabilité, tests).

## Sommaire
- [Architecture](#architecture)
- [Fonctionnalités clés](#fonctionnalités-clés)
- [Endpoints](#endpoints)
- [Configuration](#configuration)
- [Backends LLM](#backends-llm)
- [Moteurs de guardrails](#moteurs-de-guardrails)
- [Multilingue & profils culturels](#multilingue--profils-culturels)
- [Mitigation & circuit breaker](#mitigation--circuit-breaker)
- [Sécurité](#sécurité)
- [Observabilité](#observabilité)
- [Tests & couverture](#tests--couverture)
- [Docker](#docker)

## Architecture
- **FastAPI + Uvicorn** en frontal, avec routes publiques (`/v1/*`) et admin (`/admin/*`).
- **Chaîne de moteurs de guardrails** : chaque moteur produit sévérité/catégories ; un agrégateur détermine l'action (allow/warn/block) avec biais culturel.
- **Backends LLM pluggables** : Echo (déterministe), OpenAI, Hugging Face, vLLM ; sélection par configuration (`DEFAULT_BACKEND`).
- **Services** :
  - `services.moderation` orchestre détection de langue, profils culturels, chaîne de moteurs et actions graduées.
  - `services.chat` pilote génération/streaming en tenant compte de la décision de modération et des atténuations.
  - `services.locale` fournit détection, traduction (backend optionnel) et profils culturels.
  - `services.mitigation` applique masquage PII, réécriture de verbes violents et produit un plan d'atténuation.
- **Middleware** : PII masking JSON, circuit breaker (cooldown) et auth bearer.
- **Observabilité** : métriques Prometheus, exporter OTEL console, hooks TruLens/Phoenix (stubs activables).

## Fonctionnalités clés
- Chaînes de moteurs configurables avec scores de sévérité par catégorie et actions graduées.
- Profils culturels par langue pour ajuster la sévérité et restreindre des catégories.
- Modération OpenAI native optionnelle (`omni-moderation-latest`).
- Adaptateur HTTP générique pour brancher des services externes (NeMo, Guardrails AI, OpenGuardrails, LLM Guard, WildGuard, BingoGuard, PolyGuard, AEGIS 2.0, Llama Guard 3).
- Multilingue avec détection automatique et traduction optionnelle (backend `deep-translator`).
- Mitigation : masquage PII, réécriture de verbes violents, redaction en middleware.
- Observabilité : histogramme Prometheus pour sévérité, tracing OTEL console, hooks TruLens/Phoenix.
- Sécurité : auth bearer obligatoire par défaut, configuration TLS attendue côté frontal.

## Endpoints
- `POST /v1/chat/completions` : chat completions avec modération en amont, génération (synchrone ou streaming) et mitigation appliquée sur la réponse.
- `POST /v1/moderations` : exécute la chaîne de moteurs et renvoie sévérité, violations, engine votes, langue détectée, profil culturel appliqué.
- `POST /v1/classifications` : classification simple par les moteurs.
- `POST /v1/inference-mitigation` : applique masquage PII / réécritures et renvoie le plan de mitigation.
- `GET /admin/health` : santé basique.
- `GET /admin/metrics` : métriques Prometheus (histogramme sévérité, latence… si activé par les moteurs/backends).

## Configuration
Toutes les valeurs se configurent via variables d'environnement (voir `app/config/settings.py`). Principales options :
- **Sécurité** : `REQUIRE_AUTH=true|false`, `PUBLIC_TOKEN`, `ADMIN_TOKEN`, `REQUIRE_TLS=true|false`.
- **Backends LLM** : `DEFAULT_BACKEND` (`echo`, `openai`, `huggingface`, `vllm`), `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`, `HF_ENDPOINT`, `HF_API_TOKEN`, `VLLM_ENDPOINT`, `VLLM_API_KEY`, `VLLM_MODEL`.
- **Moteurs** : `ENGINE_CHAIN` (liste JSON), `ENGINE_ENDPOINTS` (map JSON nom -> URL), `ENGINE_API_KEYS` (map JSON nom -> clé), `OPENAI_MODERATION_MODEL`, `OPENAI_API_KEY` (pour l'étape native).
- **Multilingue** : `ENABLE_LIVE_TRANSLATION=true|false`, `TRANSLATION_BACKEND` (actuellement deep-translator), `LANGUAGE_PROFILES` (JSON map de biais de sévérité/restrictions par langue).
- **Circuit breaker / middleware** : `CIRCUIT_BREAKER_COOLDOWN`, `CIRCUIT_BREAKER_THRESHOLD`.
- **Observabilité** : `ENABLE_PROMETHEUS=true|false`, `OTEL_EXPORTER=console`, `ENABLE_TRULENS`, `ENABLE_PHOENIX`.

Exemple minimal (auth obligatoire et backend OpenAI) :
```bash
export PUBLIC_TOKEN=public123
export ADMIN_TOKEN=admin123
export DEFAULT_BACKEND=openai
export OPENAI_API_KEY=sk-...
uvicorn app.main:app --reload
```

## Backends LLM
- **Echo** (par défaut) : concatène les messages (utile pour tests hors réseau).
- **OpenAI** : appelle `/v1/chat/completions` avec support streaming ; nécessite `OPENAI_API_KEY` (et éventuellement `OPENAI_MODEL`, `OPENAI_BASE_URL`).
- **Hugging Face** : poste `{ "inputs": "..." }` sur `HF_ENDPOINT` avec `HF_API_TOKEN` optionnel, streaming chunké.
- **vLLM** : surface OpenAI-compatible (`/v1/chat/completions`) avec `VLLM_ENDPOINT`, `VLLM_API_KEY` facultatif.

## Moteurs de guardrails
- **HeuristicEngine** par défaut avec mots-clés et score de sévérité.
- **ExternalEngine** : appelle un endpoint HTTP externe (URL depuis `ENGINE_ENDPOINTS` + API key si fournie) et retombe sur HeuristicEngine en cas d'erreur.
- **OpenAI moderation** : s'active si `OPENAI_API_KEY` (modèle `omni-moderation-latest` configurable). Les moteurs listés (NeMo, Guardrails AI, OpenGuardrails, LLM Guard, WildGuard, BingoGuard, PolyGuard, AEGIS 2.0, Llama Guard 3) peuvent être mappés sur des endpoints réels via `ENGINE_ENDPOINTS`.

## Multilingue & profils culturels
- Détection de langue via `langdetect` avec fallback en `en`.
- Traduction optionnelle via backend `deep-translator` (activé par `ENABLE_LIVE_TRANSLATION=true`).
- Profils culturels configurables (`LANGUAGE_PROFILES`) pour ajuster les biais de sévérité et bloquer certaines catégories selon la locale ; ils sont appliqués avant décision finale.

## Mitigation & circuit breaker
- Masquage PII (emails, téléphones, cartes bancaires) et réécriture de verbes violents dans les réponses/modèles de mitigation.
- Middleware de masking JSON appliqué à toutes les réponses publiques.
- Circuit breaker middleware : compte les échecs 5xx et déclenche un cooldown configurable.

## Sécurité
- Auth bearer obligatoire par défaut pour toutes les routes (public + admin). Fournir `PUBLIC_TOKEN` et `ADMIN_TOKEN` pour démarrer.
- Déployer derrière un terminateur TLS ou configurer `REQUIRE_TLS=true` si la terminaison se fait en amont.
- Masquage PII en sortie, paramètres de mitigation configurables.
- Secrets uniquement via variables d'environnement (pas de valeurs en dur).

## Observabilité
- Exporter OTEL console activé par défaut pour traces.
- Métriques Prometheus exposées sur `/admin/metrics` (inclut histogramme des sévérités).
- Hooks TruLens et Phoenix présents ; lorsqu'ils sont activés via variables dédiées, ils journalisent l'activation en attendant une instrumentation complète.

## Tests & couverture
Exécuter l'ensemble des tests (unitaires, intégration, fonctionnels) :
```bash
python -m pytest -q --disable-warnings --maxfail=1
```
Générer un rapport de couverture :
```bash
python -m pytest --cov=app --cov-report=term-missing
```
Les tests couvrent :
- Authentification et middleware (bearer, PII masking, circuit breaker).
- Services de locale (détection, traduction, profils culturels).
- Chaînes de moteurs, OpenAI moderation et adaptateur HTTP externe (mocké).
- Backends LLM (Echo, OpenAI, Hugging Face, vLLM) avec mocks réseau et streaming.
- Endpoints FastAPI (fonctionnels) incluant chat/moderation/mitigation.

## Docker
```bash
docker build -t openserverguardrails .
docker run -p 8000:8000 --env-file .env openserverguardrails
```
Ajustez les variables d'environnement (tokens, backends, moteurs) via `--env-file` ou `-e`. Pour production, placez le service derrière un proxy TLS et fournissez des endpoints de moteurs réels via `ENGINE_ENDPOINTS`.
