# MQTT Contracts

This feature does not define new MQTT contracts. It consumes existing contracts from `packages/tars-core/src/tars/contracts/v1/`:

## Consumed Topics

| Topic | QoS | Contract | Usage |
|-------|-----|----------|-------|
| `stt/final` | 1 | `FinalTranscript` | Extract `text` field to display user message |
| `llm/response` | 1 | `LLMResponse` | Extract `reply` field to display TARS response |
| `wake/event` | 1 | `WakeEvent` | Check `detected` field to transition to listening mode |

## Published Topics

| Topic | QoS | Retained | Contract | Usage |
|-------|-----|----------|----------|-------|
| `system/health/ui-eink-display` | 1 | Yes | Health status JSON | `{"ok": bool, "err": str}` |

## Contract References

All contract definitions and validation schemas are located in:
- `packages/tars-core/src/tars/contracts/v1/stt.py` - FinalTranscript
- `packages/tars-core/src/tars/contracts/v1/llm.py` - LLMResponse  
- `packages/tars-core/src/tars/contracts/v1/wake.py` - WakeEvent

See `data-model.md` for contract usage details.
