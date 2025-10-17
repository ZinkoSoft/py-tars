# Breaking Change Policy for MQTT Topics

**Version**: 1.0  
**Last Updated**: 2024-10-16  
**Status**: Active

This document defines how to handle breaking changes to MQTT topics and message contracts.

---

## Principles

1. **Stability First**: Breaking changes are expensive - avoid them when possible
2. **Versioned Contracts**: All contracts live in versioned packages (`v1`, `v2`, etc.)
3. **Graceful Deprecation**: Support old contracts for at least one major version
4. **Clear Communication**: Breaking changes require documentation and migration guides
5. **Testing**: All changes must pass integration tests before release

---

## What Constitutes a Breaking Change?

### Breaking Changes (Require Major Version Bump)

1. **Topic Rename**: Changing topic name (e.g., `stt/final` → `stt/transcript`)
2. **Required Field Addition**: Adding a required field to an existing contract
3. **Field Removal**: Removing a field from a contract
4. **Field Type Change**: Changing field type (e.g., `str` → `int`)
5. **QoS Change**: Changing QoS level (may affect reliability guarantees)
6. **Retention Change**: Changing retained flag (affects late subscribers)
7. **Schema Tightening**: Making validation stricter (e.g., adding `extra="forbid"`)

### Non-Breaking Changes (Allowed in Minor/Patch Versions)

1. **Optional Field Addition**: Adding an optional field with a default value
2. **Documentation Updates**: Clarifying field usage without changing behavior
3. **Contract Loosening**: Relaxing validation (use sparingly)
4. **Internal Refactoring**: Changes that don't affect message shape or topic names

---

## Versioning Strategy

### Contract Versioning

Contracts are organized in versioned packages:

```
packages/tars-core/src/tars/contracts/
├── v1/           # Current stable version
│   ├── stt.py
│   ├── tts.py
│   ├── llm.py
│   └── ...
├── v2/           # Next version (when breaking changes needed)
│   ├── stt.py   # Updated contracts
│   └── ...
```

### Version Selection

Services specify which contract version they use via imports:

```python
# Service uses v1 contracts
from tars.contracts.v1 import TOPIC_STT_FINAL, FinalTranscript

# Service upgraded to v2
from tars.contracts.v2 import TOPIC_STT_FINAL, FinalTranscript
```

### Topic Versioning

**Current Approach**: No version in topic names  
- Topics: `stt/final`, `tts/say`, etc.
- Contract version is decoupled from topic name
- Services can publish/subscribe with different contract versions to same topic

**Future Consideration**: If incompatible schemas must coexist, version topics:
- `stt/v1/final` vs `stt/v2/final`
- Use only when absolutely necessary (adds operational complexity)

---

## Deprecation Process

### Phase 1: Announce Deprecation (N)
- Document deprecation in changelog
- Add deprecation warnings to contract docstrings
- Update topic registry with deprecation notice
- Set deprecation timeline (e.g., "deprecated in v2.0, removed in v3.0")

### Phase 2: Dual Support (N → N+1)
- Support both old and new contracts
- Services can migrate incrementally
- Integration tests cover both versions
- Monitor usage metrics to track migration progress

### Phase 3: Remove (N+1)
- Remove deprecated contracts
- Update all services to new version
- Remove from topic registry
- Document in migration guide

---

## Migration Process

### 1. Assess Impact
- Identify all publishers and subscribers of affected topics
- Review message volumes and criticality
- Estimate migration effort

### 2. Create Migration Plan
- Define new contract version
- Write migration guide with code examples
- Schedule migration windows for services
- Plan rollback strategy

### 3. Implement Dual Support
- Create new contract version (e.g., `v2`)
- Update one service to publish both old and new
- Verify consumers can still process old messages
- Deploy and monitor

### 4. Incremental Migration
- Migrate consumers first (they must handle both formats)
- Then migrate publishers
- Monitor error rates and logs
- Roll back if issues detected

### 5. Cleanup
- After all services migrated, deprecate old version
- Wait one release cycle, then remove
- Update documentation

---

## Example: Adding a Required Field

**Scenario**: Add required `session_id` field to `FinalTranscript`

### ❌ Breaking Approach (Avoid)
```python
# v2/stt.py
class FinalTranscript(BaseModel):
    message_id: str
    text: str
    session_id: str  # NEW REQUIRED FIELD - breaks old publishers!
    ...
```

### ✅ Non-Breaking Approach (Preferred)
```python
# v1/stt.py (backward compatible)
class FinalTranscript(BaseModel):
    message_id: str
    text: str
    session_id: str | None = None  # Optional with default
    ...
```

**Migration Path**:
1. Add as optional field in v1
2. Update all publishers to include field
3. In v2, make required (or keep optional if not critical)

---

## Example: Topic Rename

**Scenario**: Rename `stt/final` to `stt/transcript` for consistency

### Migration Steps

1. **Create v2 with new topic name**
```python
# v2/stt.py
TOPIC_STT_TRANSCRIPT = "stt/transcript"  # New name

# v1/stt.py (unchanged)
TOPIC_STT_FINAL = "stt/final"  # Old name
```

2. **Dual Publishing Phase**
```python
# STT Worker publishes to BOTH topics
await client.publish(TOPIC_STT_FINAL, payload)      # v1 (deprecated)
await client.publish(TOPIC_STT_TRANSCRIPT, payload)  # v2 (new)
```

3. **Consumer Migration**
```python
# Consumers subscribe to both during transition
await client.subscribe(TOPIC_STT_FINAL)       # Old
await client.subscribe(TOPIC_STT_TRANSCRIPT)  # New

# Deduplicate via message_id
async for msg in messages:
    if msg.message_id not in seen:
        process(msg)
        seen.add(msg.message_id)
```

4. **Sunset Old Topic**
- After all consumers migrated to new topic
- Stop dual publishing
- Remove old topic from registry

---

## Contract Evolution Examples

### Adding Optional Field (Non-Breaking)
```python
# Before
class LLMRequest(BaseModel):
    id: str
    text: str

# After (safe)
class LLMRequest(BaseModel):
    id: str
    text: str
    max_tokens: int | None = None  # New optional field
```

### Changing Field Type (Breaking)
```python
# Before
class TtsStatus(BaseModel):
    event: str  # "speaking_start" or "speaking_end"

# After (breaking - needs v2)
from enum import Enum

class TtsEvent(str, Enum):
    SPEAKING_START = "speaking_start"
    SPEAKING_END = "speaking_end"

class TtsStatus(BaseModel):
    event: TtsEvent  # Now enum instead of str
```

### Renaming Field (Breaking)
```python
# Before
class MemoryQuery(BaseModel):
    text: str
    top_k: int = 5

# After (breaking - needs v2)
class MemoryQuery(BaseModel):
    text: str
    limit: int = 5  # Renamed from top_k
```

**Migration Path**: Add new field, deprecate old, support both temporarily:
```python
class MemoryQuery(BaseModel):
    text: str
    top_k: int | None = Field(None, deprecated=True)  # Old field
    limit: int | None = None  # New field
    
    @model_validator(mode='after')
    def handle_deprecated(self):
        if self.top_k is not None and self.limit is None:
            self.limit = self.top_k  # Use old value if new not provided
        return self
```

---

## Testing Requirements

All breaking changes must include:

1. **Unit Tests**: Validate new contract schema
2. **Integration Tests**: Verify end-to-end flows with new contracts
3. **Backward Compatibility Tests**: Ensure old contracts still work during transition
4. **Migration Tests**: Validate migration path from old to new

Example:
```python
# tests/integration/test_migration_v1_to_v2.py
def test_stt_final_to_transcript_migration():
    """Test dual publishing during topic rename."""
    # Publisher sends to both topics
    await stt_worker.publish_both_topics(transcript)
    
    # Old consumers still receive via old topic
    old_msg = await old_subscriber.receive(TOPIC_STT_FINAL)
    assert old_msg.text == transcript.text
    
    # New consumers receive via new topic
    new_msg = await new_subscriber.receive(TOPIC_STT_TRANSCRIPT)
    assert new_msg.text == transcript.text
    
    # Same message_id for deduplication
    assert old_msg.message_id == new_msg.message_id
```

---

## Rollback Strategy

If breaking change causes issues:

1. **Immediate**: Revert publisher to send old messages
2. **Monitor**: Watch for error rates to drop
3. **Investigate**: Root cause analysis
4. **Fix**: Address issues in new version
5. **Retry**: Re-attempt migration with fixes

**Rollback Checklist**:
- [ ] Stop publishing new message format
- [ ] Resume publishing old format
- [ ] Verify consumers processing correctly
- [ ] Notify stakeholders of rollback
- [ ] Document lessons learned

---

## Communication Checklist

Before deploying breaking changes:

- [ ] Document change in `/specs/003-standardize-mqtt-topics/CHANGELOG.md`
- [ ] Update topic registry with deprecation notices
- [ ] Write migration guide with code examples
- [ ] Announce in team communication channels
- [ ] Set clear timeline for deprecation and removal
- [ ] Create tracking issue for migration progress
- [ ] Update `.github/copilot-instructions.md` with new patterns

---

## Governance

- **Breaking Changes Require**: Approval from 2+ maintainers
- **Review Period**: Minimum 1 week for community feedback
- **Emergency Changes**: May bypass process if system is down, but must be documented retroactively

---

## References

- [Topic Registry](./topic-registry.md)
- [Migration Guide](./migration-guide.md)
- [Semantic Versioning](https://semver.org/)
- [Pydantic Migration Guide](https://docs.pydantic.dev/latest/migration/)
