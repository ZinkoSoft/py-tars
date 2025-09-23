# Character Module Plan

Goal: Centralize character/persona configuration so all services (router, llm-worker, tts-worker, ui, memory-worker) consume a single source of truth for name, persona/system prompt, greetings, voice, and styling.

## 1) Objectives
- Single, declarative character config that can be switched at runtime.
- Consistent persona across LLM prompts, TTS voice, and UI.
- Safe, minimal dynamic updates via MQTT with validation.
- Easy to author new characters and ship defaults.

## 2) Ownership & Scope
- New shared module (Python): `apps/common/character/`
  - Loader: read TOML/YAML/JSON
  - Schema: validate fields
  - MQTT helper: publish/subscribe character updates
  - Utilities: build LLM system prompt, pick greeting, render TTS config

Consumers:
- llm-worker: uses persona/system, style, boundaries, and name
- tts-worker: uses voice config (path/id), pitch/rate, language
- router: uses greeting on startup and online announcements
- ui/ui-web: uses avatar, display name, theme colors (optionally)
- memory-worker: can tag docs with active character name (optional)

## 3) Directory layout & formats
- Repo folder for characters: `characters/`
  - `TARS/character.toml`
  - `TARS/avatar.png` (optional)
  - `TARS/voice/` (optional; or reuse tts workers' voice directory)

Config file schema (TOML example):

```toml
version = 1
name = "TARS"
role = "Shipboard AI"
description = "Helpful, concise, a touch of dry humor"

[persona]
system_prompt = """
You are TARS, a helpful assistant. Be concise, direct, and pragmatic. Maintain a slightly dry humor when appropriate.
Avoid making up facts and prefer asking clarifying questions.
"""
style_guide = [
  "Concise sentences",
  "No markdown unless explicitly asked",
  "Avoid speculation",
]
boundaries = [
  "No medical or legal advice",
  "Defer unsafe requests",
]

[greetings]
startup = [
  "System online.",
  "Diagnostics nominal. Good to see you.",
]
wakeup = [
  "Yes?",
  "I'm here.",
]

[voice]
# for tts-worker
id = "TARS"
path = "/voices/TARS.onnx"     # or provider-specific id
rate = 1.0
pitch = 0.0
language = "en-US"

[llm]
# defaults used by llm-worker unless overridden
model = "gpt-4o-mini"
max_tokens = 256
temperature = 0.7

[wake]
# wake words/hotwords if used by UI/microphone
phrases = ["tars", "hey tars"]

[ui]
color = "#00AEEF"
avatar = "avatar.png"
```

Notes:
- Prefer TOML for readability; support JSON/YAML too if needed.
- Use version field for evolving schema.

## 4) Env & defaults
- Env vars:
  - `CHARACTER_NAME` (e.g., `TARS`)
  - `CHARACTER_DIR` (default `/config/characters`)
  - `CHARACTER_FILE` optional, else `CHARACTER_NAME/character.toml`
- Compose mounts:
  - Mount `./characters:/config/characters:ro`
  - Optionally mount overrides: `./data/character_overrides:/data/character_overrides`

## 5) MQTT topics and flow
- Retained announce: `system/character/current`
  - `{ name, version, voice: {id,path}, llm: {model}, updated_at }`
- Request/response (optional, auth guarded):
  - `system/character/get` → worker republishes current config (sanitized)
  - `system/character/set` → propose update; loader validates & writes to overrides, then announces
- Change events:
  - `system/character/changed` (non-retained) with `{name, reason}`

Security:
- By default, updates disabled in production; allow via env `CHARACTER_UPDATES=1` plus token `CHARACTER_TOKEN` in payload.

## 6) How each service uses it
- llm-worker:
  - On start, load character; build system prompt as: persona.system_prompt + style/boundaries summary.
  - When `system/character/current` changes, hot-reload.
  - For greetings: select a `greetings.startup` line on first ready.
- tts-worker:
  - Apply `voice` settings on start; subscribe to changes and reconfigure voice if supported.
- router:
  - On overall readiness, publish greeting `tts/say` from character.
- ui/ui-web:
  - Show `name`, `avatar`, and theme color.

## 7) Validation & schema
- Use pydantic to define a Character model; validate on load.
- Log warnings for unknown keys; reject invalid required fields.

## 8) Hot reload strategy
- Subscribe to `system/character/current`.
- Debounce updates (e.g., 250ms) and apply atomically.
- Services cache current character; fall back to last-known-good.

## 9) Milestones
- M1: Spec & example
  - Add this plan, create `characters/TARS/character.toml` example.
- M2: Common module
  - Implement `apps/common/character/` with loader, schema, MQTT helper, and README.
- M3: Router + TTS integration
  - Router uses `greetings.startup` instead of env; TTS applies voice config.
- M4: LLM integration
  - llm-worker composes system prompt from character and announces current character on health.
- M5: UI integration
  - ui/ui-web reads avatar/name/color; display on UI.
- M6: Optional updates via MQTT
  - Guarded set/get topic handling with token auth.

## 10) Acceptance
- With a single `CHARACTER_NAME`, all services present coherent persona and voice.
- Changing the character directory content and republishing results in hot reload across services.
- Router greeting and TTS voice use character config.

## 11) Persistent Traits and LLM-driven Updates

Goal: Store character traits (e.g., honesty, empathy) in a persistent database and enable controlled updates proposed by the LLM.

Storage options:
- Reuse memory-worker HybridDB for traits (advantages: one stack; vector+BM25 search by trait/history). Use a dedicated namespace/keyspace.
- Or a tiny KV/JSON store (e.g., SQLite + JSON column or pure JSON file) if we prefer simplicity.

Recommended (initial): HybridDB in memory-worker with a separate "character" collection:
- Keyed by `character_name` and `section` (e.g., traits, persona, voice).
- Document shape example:
  ```json
  {
    "section": "traits",
    "character": "TARS",
    "version": 1,
    "updated_at": 1737600000,
    "traits": {
      "honesty": 95, "humor": 90, "empathy": 20, "curiosity": 30, "confidence": 100,
      "formality": 10, "sarcasm": 70, "adaptability": 70, "discipline": 100, "imagination": 10,
      "emotional_stability": 100, "pragmatism": 100, "optimism": 50, "resourcefulness": 95,
      "cheerfulness": 30, "engagement": 40, "respectfulness": 20, "verbosity": 10
    },
    "note": "seed from character.toml"
  }
  ```

Access API (MQTT topics):
- `character/get` → `{ name: "TARS", section: "traits" }` → response on `character/result` with the current traits doc.
- `character/set` (guarded) → `{ name, section: "traits", traits: {...}, reason, token }`
- `character/changed` (event) → `{ name, section, updated_at }`

LLM-driven update workflow:
1) llm-worker or router proposes updates (e.g., after a learning event) by publishing to `character/set`.
2) character module validates values (0–100 ints), applies constraints, merges with existing traits, writes to DB, and emits `character/changed` and a retained `system/character/current` update.
3) services hot-reload the new traits.

Validation & guardrails:
- Require `CHARACTER_UPDATES=1` and a `CHARACTER_TOKEN` secret to accept set requests.
- Bounds check traits (0–100), whitelist keys, reject unknown fields unless `ALLOW_EXPERIMENTAL=1`.
- Optionally, rate-limit updates per character (e.g., 1/minute).

Audit & provenance:
- Keep an append-only log in DB with `{ before, after, reason, proposer, timestamp }`.
- Store last-N updates for quick rollback.

Seeding & sync:
- On startup, if DB lacks `traits`, seed from `character.toml`.
- On changes via DB, optionally write to an overrides file under `/data/character_overrides` for human inspection.

RAG considerations:
- Traits can be included as part of the prompt context; keep the system prompt concise (summarize top traits rather than dumping all keys).

Milestones (traits):
- C1: Seed traits from character.toml into DB on boot; expose `character/get` and `character/result`.
- C2: Implement guarded `character/set` with validation and audit; services hot-reload.
- C3: Add rollback helper (`character/rollback` with `to_version` or `update_id`).
