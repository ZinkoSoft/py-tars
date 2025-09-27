from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if SRC_DIR.exists():
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

from tars.contracts.envelope import Envelope  # type: ignore[import]


def test_memory_query_roundtrip() -> None:
    from tars.contracts.v1.memory import (  # type: ignore[import]
        EVENT_TYPE_MEMORY_QUERY,
        EVENT_TYPE_MEMORY_RESULTS,
        EVENT_TYPE_CHARACTER_GET,
        EVENT_TYPE_CHARACTER_RESULT,
        MemoryQuery,
        MemoryResults,
        CharacterGetRequest,
        CharacterSnapshot,
        CharacterSection,
    )

    query = MemoryQuery(text="Where did we meet?", top_k=3)
    envelope = Envelope.new(event_type=EVENT_TYPE_MEMORY_QUERY, data=query, source="test-memory")
    encoded = envelope.model_dump_json().encode()
    decoded = Envelope.model_validate_json(encoded)

    assert decoded.type == EVENT_TYPE_MEMORY_QUERY
    restored_query = MemoryQuery.model_validate(decoded.data)
    assert restored_query.text == "Where did we meet?"
    assert restored_query.top_k == 3
    assert restored_query.message_id == query.message_id

    results = MemoryResults(query="Where did we meet?", k=2, results=[{"document": {"text": "At the lab"}, "score": 0.9}])
    env_out = Envelope.new(event_type=EVENT_TYPE_MEMORY_RESULTS, data=results, correlate=query.message_id, source="test-memory")
    decoded_out = Envelope.model_validate_json(env_out.model_dump_json())
    restored_results = MemoryResults.model_validate(decoded_out.data)
    assert restored_results.k == 2
    assert restored_results.results[0].document == {"text": "At the lab"}
    assert restored_results.results[0].score == pytest.approx(0.9)

    get_req = CharacterGetRequest(section="traits")
    env_get = Envelope.new(event_type=EVENT_TYPE_CHARACTER_GET, data=get_req, source="test-memory")
    restored_get = CharacterGetRequest.model_validate(Envelope.model_validate_json(env_get.model_dump_json()).data)
    assert restored_get.section == "traits"

    snapshot = CharacterSnapshot(name="Nova", description="Smart", traits={"kind": "very"})
    env_snapshot = Envelope.new(event_type=EVENT_TYPE_CHARACTER_RESULT, data=snapshot)
    restored_snapshot = CharacterSnapshot.model_validate(Envelope.model_validate_json(env_snapshot.model_dump_json()).data)
    assert restored_snapshot.traits == {"kind": "very"}

    section = CharacterSection(section="traits", value={"kind": "very"})
    env_section = Envelope.new(event_type=EVENT_TYPE_CHARACTER_RESULT, data=section)
    restored_section = CharacterSection.model_validate(Envelope.model_validate_json(env_section.model_dump_json()).data)
    assert restored_section.section == "traits"
    assert restored_section.value == {"kind": "very"}
