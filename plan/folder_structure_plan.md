For a multi-service, event-driven project like TARS, the cleanest approach is a monorepo with “src layout” packages: one package per app, plus a tiny shared “contracts” package. Keep each app self-contained (own config, runtime wiring, adapters), and keep “shared” minimal.

Here’s a battle-tested structure and the reasoning.

1) Top-level layout (monorepo, src layout)

py-tars/
├─ apps/
│  ├─ router/
│  │  ├─ pyproject.toml
│  │  ├─ src/tars_router/
│  │  │  ├─ app_main.py            # __main__/entrypoint (console_script)
│  │  │  ├─ config.py              # pydantic-settings
│  │  │  ├─ runtime/               # composition root + dispatcher
│  │  │  │  ├─ dispatcher.py
│  │  │  │  ├─ subscription.py
│  │  │  │  └─ ctx.py
│  │  │  ├─ domain/                # pure logic (no I/O)
│  │  │  │  └─ policy.py
│  │  │  └─ adapters/              # tech details (MQTT, HTTP, etc.)
│  │  │     └─ mqtt_asyncio.py
│  │  └─ tests/
│  │     ├─ unit/
│  │     └─ integration/
│  ├─ tts-worker/
│  │  ├─ pyproject.toml
│  │  ├─ src/tars_tts_worker/
│  │  │  ├─ app_main.py
│  │  │  ├─ config.py
│  │  │  ├─ runtime/
│  │  │  ├─ domain/                # TTS facade interface / small policy
│  │  │  └─ adapters/              # Piper/ElevenLabs/etc.
│  │  └─ tests/
│  └─ stt-worker/
│     ├─ pyproject.toml
│     ├─ src/tars_stt_worker/
│     │  ├─ app_main.py
│     │  ├─ config.py
│     │  ├─ runtime/
│     │  ├─ domain/                # VAD thresholds / partial aggregation
│     │  └─ adapters/
│     └─ tests/
├─ packages/
│  ├─ tars-contracts/              # the ONLY shared package (schemas)
│  │  ├─ pyproject.toml
│  │  └─ src/tars_contracts/
│  │     ├─ version.py
│  │     ├─ envelope.py            # id, type, ts, source, data
│  │     ├─ registry.py            # event_type ↔ topic map
│  │     └─ v1/
│  │        ├─ stt.py              # FinalTranscript, PartialTranscript
│  │        ├─ tts.py              # TtsSay, TtsCancel
│  │        └─ health.py           # HealthPing
│  └─ tars-testing/ (optional)     # test helpers, fake buses
├─ docker/                         # Dockerfiles or shared base images
├─ ops/                            # compose files, k8s, infra scripts
├─ scripts/                        # dev scripts (format, typecheck)
├─ .github/workflows/              # CI
├─ Makefile                        # make dev-up / dev-down / lint / test
└─ README.md

Why this works
	•	Isolation: each app is a real package (no PYTHONPATH hacks), with its own deps, entrypoint, tests.
	•	Clarity: business logic lives in domain/; I/O in adapters/; wiring in runtime/ (composition root).
	•	Extensibility: adding an app = add a folder under apps/ with the same skeleton.
	•	Safety: src layout prevents accidental imports from the working directory.

2) Contract-first design
	•	Put only Pydantic models, JSON schemas, and the event_type↔topic registry in packages/tars-contracts.
	•	No MQTT clients or helpers in contracts—keep it transport-agnostic.
	•	Version contracts (v1/, v2/) and pin versions per app (tars-contracts==1.x).

3) Each app’s internal layout

runtime/ (Observer plumbing)
	•	dispatcher.py: central subscribe/decode/validate/dispatch loop.
	•	subscription.py: table of Sub(topic, model, handler, qos).
	•	ctx.py: tiny facade with .publish(event_type, data, correlate=...) so handlers never see raw topics.

domain/
	•	Pure functions/classes: policies, small state machines, validators.
	•	No network, no files, no threads.

adapters/
	•	All tech details: mqtt_asyncio.py, Piper client, file I/O, device access.
	•	Swap implementations without touching domain/.

config.py
	•	pydantic-settings for env vars (MQTT_HOST, VOICE_PATH, etc.), default .env support.

app_main.py
	•	Wire config → adapters → domain → runtime; expose __main__ or console script.

4) Naming & entrypoints

Package names
	•	tars_router, tars_tts_worker, tars_stt_worker (prefix for easy pip list reading).

Entrypoints (pyproject.toml)

[project]
name = "tars-router"
version = "0.1.0"
dependencies = ["tars-contracts==1.*", "asyncio-mqtt", "pydantic-settings", "structlog"]

[project.scripts]
tars-router = "tars_router.app_main:main"

5) Tests

tests/
├─ unit/           # fast, pure domain tests
├─ integration/    # spins Mosquitto (testcontainers) and asserts pub/sub
└─ fixtures/       # sample JSON envelopes and WAVs

	•	Unit tests target domain/ (no I/O).
	•	Integration tests use fake or containerized adapters.
	•	Add a golden set of valid JSON messages from tars-contracts to catch drift.

6) Tooling & CI
	•	pre-commit: ruff (lint), black (format), mypy (type check).
	•	CI: matrix per app (apps/router, apps/tts-worker, etc.) + one job for packages/tars-contracts.
	•	Makefile:
	•	make fmt (ruff+black), make typecheck, make test
	•	make dev-up / dev-down (docker compose for broker + workers)

7) Docker / deployment
	•	One Dockerfile per app (build from python:3.x-slim, copy its src/, install from wheels).
	•	Root-level ops/compose.yaml wires broker + apps; per-app env files (apps/<app>/.env.example).

8) “Add a new app” playbook (repeatable)
	1.	apps/new-worker/ from a template (cookiecutter is great).
	2.	Fill pyproject.toml, add console script.
	3.	Create domain/ with the minimal policy or handler.
	4.	Create adapters/ as needed (or reuse existing packages).
	5.	Add subscriptions table + dispatcher wiring in runtime/.
	6.	Write unit tests (domain) + one integration test (end-to-end pub/sub).
	7.	Add a service block to ops/compose.yaml.

9) Do / Don’t

Do
	•	Keep all topics and event types centralized in tars-contracts/registry.py.
	•	Keep handlers tiny; business logic only; no raw publish/subscribe.
	•	Use src layout everywhere; avoid relative imports that jump across apps.

Don’t
	•	Create a giant “common” package (it becomes a dependency tarpit).
	•	Let adapters leak into domain (no paho clients inside policies).
	•	Scatter topic strings or QoS flags across many files.

⸻

Treat the shared payloads as a small, versioned “contracts” package that every app imports. That’s the cleanest way to use the same contract across multiple apps without tangling them together.

How to do it well

1) Package & versioning
	•	Create a single installable package (e.g., tars-contracts) that contains only:
	•	Pydantic models (schemas), enums, tiny validators
	•	JSON Schemas (generated from the models)
	•	An event registry mapping event_type ↔ topic
	•	Use semver; apps pin exact versions (tars-contracts==1.4.2) and upgrade intentionally.
	•	Keep it transport-agnostic (no MQTT clients or helper logic).

packages/
  tars-contracts/
    pyproject.toml
    src/tars_contracts/
      version.py
      envelope.py
      registry.py        # event_type ↔ topic map
      v1/
        stt.py           # FinalTranscript, PartialTranscript
        tts.py           # TtsSay, TtsCancel
        health.py        # HealthPing
      jsonschema/
        v1/*.schema.json

2) Event versioning (multi-app safe)

Pick one of these and stick to it:
	•	Type suffix: type="stt.final@v1" (easy routing, clear at a glance), or
	•	Envelope field: type="stt.final", schema_version=1.

Consumers can support multiple versions during migrations:

from pydantic import ValidationError
from tars_contracts.v2.stt import FinalTranscript as FinalV2
from tars_contracts.v1.stt import FinalTranscript as FinalV1

def parse_final(data: dict):
    try:
        return FinalV2.model_validate(data), "v2"
    except ValidationError:
        return FinalV1.model_validate(data), "v1"

Rule of thumb
	•	Minor bumps = additive/optional fields only.
	•	Major bumps = new module (v2/), keep v1/ around until retired.

3) Testing & CI across apps
	•	In tars-contracts CI:
	•	Generate JSON Schemas and run compat checks (no removed required fields in a minor).
	•	Publish the wheel to your internal index (or GitHub Packages) only if green.
	•	In each app CI:
	•	Install the pinned contracts version.
	•	Validate fixtures (sample envelopes) against the schemas.
	•	Optional: consumer-driven contract tests (Pact-style) by validating the consumer’s expectations against the producer’s fixtures.

4) Runtime usage pattern (same in every app)
	•	Subscribe → parse Envelope → route by envelope.type (and version) → validate with the right model → handle.
	•	Publish → build data model → wrap in Envelope with id, type, version, ts, source → publish to topic from the registry.

# publish (never hardcode topics in business code)
env = Envelope.new(event_type="tts.say@v1", data=TtsSay(text="Hello"))
topic = registry.resolve_topic(env.type)
await publisher.publish(topic, env.model_dump_json().encode(), qos=1)

5) Keep it small (avoid a “god” package)
	•	Only contracts live here. No logging utils, no retry helpers, no MQTT wrappers.
	•	If it starts to sprawl, split by bounded context later:
	•	tars-contracts-speech, tars-contracts-system (separate release cadences)
	•	But start with one package; premature splitting adds overhead.

6) Documentation & change control
	•	CHANGES.md in tars-contracts with human-readable diffs.
	•	MIGRATION.md for any major bump (how to consume both v1 and v2, deprecation windows).
	•	An ADR (Architecture Decision Record) describing your event versioning policy.

7) Upgrade workflow (multi-app friendly)
	•	Contracts repo releases 1.5.0.
	•	Renovate (or a simple script) opens PRs in each app bumping tars-contracts to 1.5.0.
	•	Each app CI validates fixtures; if green, merge and deploy. If not, fix in the app or revert.

⸻