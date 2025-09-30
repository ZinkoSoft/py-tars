# llm-worker

A pluggable LLM microservice for TARS. Subscribes to `llm/request`, optionally performs RAG via `memory-worker`, calls a configured provider, and publishes `llm/response`.

Status: MVP scaffold with OpenAI-compatible provider (non-streaming) and RAG pre-fetch.

## Env
- MQTT_URL (e.g., mqtt://user:pass@127.0.0.1:1883)
- LLM_PROVIDER=openai|server|local|gemini|dashscope (currently using openai)
- LLM_MODEL, LLM_MAX_TOKENS, LLM_TEMPERATURE, LLM_TOP_P
- OPENAI_API_KEY, OPENAI_BASE_URL (optional)
- OPENAI_RESPONSES_MODELS (comma-separated list, supports `*` wildcards; defaults to `gpt-4.1*,gpt-4o-mini*,gpt-5*,gpt-5-mini,gpt-5-nano` to route those models through the OpenAI Responses API)
- RAG_ENABLED, RAG_TOP_K, RAG_PROMPT_TEMPLATE
- Topics: TOPIC_LLM_REQUEST, TOPIC_LLM_RESPONSE, TOPIC_MEMORY_QUERY, TOPIC_MEMORY_RESULTS, TOPIC_HEALTH

When targeting newer ChatGPT family models such as `gpt-4.1`, `gpt-4o-mini`, `gpt-5`, `gpt-5-mini`, or `gpt-5-nano`, the worker automatically switches to OpenAI's Responses API for compatibility. Adjust `OPENAI_RESPONSES_MODELS` if you need to override the defaults.

## Topics
- llm/request: { id, text, use_rag?, rag_k?, system?, params? }
- llm/response: { id, reply | error, provider, model, tokens? }
- system/health/llm (retained)

## Run (local)
Create a venv, install requirements, export MQTT_URL and OPENAI_API_KEY, then:

```bash
python -m llm_worker
```