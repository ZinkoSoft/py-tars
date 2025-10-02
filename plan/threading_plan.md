# Threading & Async Optimization Plan for py-tars

**Date**: 2025-10-02  
**Status**: ✅ Core Implementation Complete - Documentation Pending  
**Python Version**: 3.11+ (TaskGroup, faster asyncio)

## 🎉 Implementation Progress

**Completed (5/7 High/Medium Priority Items)**:
- ✅ STT Worker - Async transcription with thread pool
- ✅ Memory Worker - Async embeddings with thread pool  
- ✅ LLM Worker - RAG query futures (no more inline subscriptions)
- ✅ LLM Worker - Tool polling replacement with futures
- ✅ TTS Worker - Async synthesis wrappers

**Test Results**: ✅ 159 passed, 4 skipped, 0 failures

**Pending**:
- ⏳ Async-specific tests (event loop responsiveness, concurrent ops, timeouts)
- ⏳ Documentation updates (.github/copilot-instructions.md)

---

## Executive Summary

The py-tars codebase is **already well-architected** for async/await patterns. Most services use `asyncio` correctly with proper task supervision, MQTT async clients, and non-blocking I/O. However, there are **targeted opportunities** to improve concurrency, reduce latency, and optimize CPU-bound operations through better use of threading and async primitives.

**Key Findings**:
- ✅ **Good**: All services use asyncio event loops properly
- ✅ **Good**: MQTT I/O is non-blocking via `asyncio-mqtt`
- ⚠️ **Improvement**: Some CPU-bound work (Whisper transcription, Piper synthesis, embeddings) blocks the event loop
- ⚠️ **Improvement**: TTS worker has good threading primitives but could use `asyncio.to_thread()` for consistency
- ⚠️ **Improvement**: Memory worker's embedding operations are synchronous and could benefit from thread pool execution

---

## 1. Current State Analysis

### 1.1 Services Using Async Correctly ✅

#### **Router** (`apps/router/main.py`)
- Pure async event loop with MQTT pub/sub
- Uses `Dispatcher` with proper task supervision
- Stream buffering and boundary detection is non-blocking
- **No blocking I/O** - well designed
- **Status**: ✅ No changes needed

#### **STT Worker** (`apps/stt-worker/stt_worker/app.py`)
- Good async architecture with MQTT subscription
- VAD processing is already in async context
- **Issue**: Whisper transcription via `SpeechTranscriber` is **synchronous** and blocks
- Audio capture runs in separate thread (good)
- **Action Required**: Offload transcription to thread pool

#### **LLM Worker** (`apps/llm-worker/llm_worker/service.py`)
- Async MQTT loop with proper streaming
- OpenAI HTTP requests are async via `httpx.AsyncClient`
- Tool call execution has async/await but uses **polling** for results
- **Issue**: Memory RAG query (`_do_rag`) uses **blocking MQTT subscribe pattern**
- **Action Required**: Fix RAG query to use proper async subscription; optimize tool result handling

#### **Memory Worker** (`apps/memory-worker/memory_worker/service.py`)
- Async MQTT loop
- **Issue**: Embedding computation (`STEmbedder.__call__`) is **CPU-bound and synchronous**
- **Issue**: HyperDB query/add operations are synchronous
- **Action Required**: Move embeddings to thread pool

#### **TTS Worker** (`apps/tts-worker/`)
- Good async architecture
- **Good Practice**: `PiperSynth` uses `threading.Thread` for synthesis pipeline
- **Issue**: Synthesis operations (`_synth_to_wav`) could use `asyncio.to_thread()` for better integration
- **Good**: Concurrent file synthesis with `ThreadPoolExecutor` in `_file_playback_pipelined`
- **Action Required**: Wrap blocking synthesis calls with `asyncio.to_thread()`

---

## 2. Optimization Opportunities (Priority Order)

### 2.1 **HIGH PRIORITY**: STT Worker - Offload Transcription ⚠️

**Problem**:
```python
# apps/stt-worker/stt_worker/transcriber.py
def transcribe(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
    # This blocks the event loop for ~100-500ms per transcription
    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    # ... Whisper model inference (CPU-bound)
```

**Impact**: 
- Transcription blocks the async event loop
- Delays MQTT message processing, health checks, and TTS status handling
- Latency: 100-500ms per transcription

**Solution**:
```python
# Use asyncio.to_thread for CPU-bound work
async def transcribe_async(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
    return await asyncio.to_thread(self._transcribe_sync, audio_data, input_sample_rate)

def _transcribe_sync(self, audio_data: bytes, input_sample_rate: int) -> Tuple[str, float, Dict[str, Any]]:
    # Current synchronous implementation moves here
    ...
```

**Benefits**:
- Event loop remains responsive during transcription
- Better handling of concurrent wake events, TTS status updates
- Cleaner code than manual thread management

**Files to Modify**:
- `apps/stt-worker/stt_worker/transcriber.py` - Add async wrapper
- `apps/stt-worker/stt_worker/app.py` - Call `await transcriber.transcribe_async()`
- `packages/tars-core/src/tars/domain/stt.py` - Update `STTService` to use async transcriber

---

### 2.2 **HIGH PRIORITY**: Memory Worker - Thread Pool for Embeddings ⚠️

**Problem**:
```python
# apps/memory-worker/memory_worker/service.py
class STEmbedder:
    def __call__(self, texts: list[str]) -> np.ndarray:
        # CPU-bound SentenceTransformer encoding - blocks event loop
        embeddings = self.model.encode(texts, ...)
        return embeddings.astype(np.float32)
```

**Impact**:
- Embedding generation blocks event loop (50-200ms per query)
- During queries, MQTT messages queue up
- Memory indexing (on `stt/final` or `tts/say`) causes spikes

**Solution**:
```python
class STEmbedder:
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name, device="cpu")
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embed")
    
    async def embed_async(self, texts: list[str]) -> np.ndarray:
        """Async wrapper for CPU-bound embedding."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, self._encode_sync, texts)
    
    def _encode_sync(self, texts: list[str]) -> np.ndarray:
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.astype(np.float32)
```

**Benefits**:
- Non-blocking embeddings
- Event loop stays responsive during memory operations
- Better throughput when handling concurrent STT/TTS ingest + queries

**Files to Modify**:
- `apps/memory-worker/memory_worker/service.py` - Convert `STEmbedder` to async
- `apps/memory-worker/memory_worker/hyperdb.py` - Accept async embedding function
- Update all call sites to `await embedder.embed_async(texts)`

---

### 2.3 **MEDIUM PRIORITY**: LLM Worker - Fix RAG Query Pattern ⚠️

**Problem**:
```python
# apps/llm-worker/llm_worker/service.py
async def _do_rag(self, client, prompt: str, top_k: int) -> str:
    await client.publish(TOPIC_MEMORY_QUERY, json.dumps(payload))
    # BLOCKING: subscribes and waits inline - poor async pattern
    async with client.messages() as mstream:
        await client.subscribe(TOPIC_MEMORY_RESULTS)
        async for m in mstream:
            # ...returns first result
```

**Impact**:
- Creates a new subscription per RAG query (inefficient)
- Blocks LLM processing until memory responds
- Doesn't handle timeouts or errors gracefully

**Solution**:
```python
# Subscribe to memory/results once at startup (like character/current)
# Use correlation IDs and asyncio.Future to match responses

class LLMService:
    def __init__(self):
        self._pending_rag: Dict[str, asyncio.Future[str]] = {}
    
    async def _handle_memory_results(self, payload: bytes) -> None:
        """Handle memory/results messages."""
        try:
            data = json.loads(payload)
            # Extract correlation ID from envelope if present
            corr_id = data.get("correlate") or data.get("id")
            if corr_id in self._pending_rag:
                future = self._pending_rag.pop(corr_id)
                results = data.get("results") or []
                snippets = [r.get("document", {}).get("text", "") for r in results]
                future.set_result("\n".join(snippets))
        except Exception as e:
            logger.warning("Failed to parse memory/results: %s", e)
    
    async def _do_rag(self, client, prompt: str, top_k: int, correlation_id: str) -> str:
        """Non-blocking RAG query using correlation ID."""
        future = asyncio.Future()
        self._pending_rag[correlation_id] = future
        
        payload = {"text": prompt, "top_k": top_k, "id": correlation_id}
        await client.publish(TOPIC_MEMORY_QUERY, json.dumps(payload))
        
        try:
            # Wait with timeout
            return await asyncio.wait_for(future, timeout=5.0)
        except asyncio.TimeoutError:
            self._pending_rag.pop(correlation_id, None)
            logger.warning("RAG query timeout for %s", correlation_id)
            return ""
```

**Benefits**:
- Single persistent subscription (not per-query)
- Non-blocking with proper timeout handling
- Better error recovery
- Follows envelope correlation pattern

**Files to Modify**:
- `apps/llm-worker/llm_worker/service.py` - Refactor `_do_rag` and add `_handle_memory_results`

---

### 2.4 **MEDIUM PRIORITY**: TTS Worker - Async Synthesis Wrappers ✅ COMPLETED

**Problem**: ✅ RESOLVED
```python
# apps/tts-worker/tts_worker/piper_synth.py
def synth_and_play(self, text: str, ...) -> float:
    # Calls blocking subprocess, file I/O, synthesis
    # Already uses threads internally, but not async-wrapped
```

**Impact**: ✅ RESOLVED
- TTS playback no longer blocks MQTT event processing
- Better integration with async service architecture
- Domain service now detects and uses async methods automatically

**Solution Implemented**:
```python
class PiperSynth:
    async def synth_and_play_async(self, text: str, streaming: bool = False, pipeline: bool = True) -> float:
        """Async wrapper for synthesis and playback."""
        return await asyncio.to_thread(self.synth_and_play, text, streaming, pipeline)
    
    async def synth_to_wav_async(self, text: str, wav_path: str) -> None:
        """Async wrapper for synthesis to file."""
        await asyncio.to_thread(self.synth_to_wav, text, wav_path)
```

**Benefits Achieved**:
- Event loop stays responsive during TTS playback
- Better integration with async service architecture
- Duck-typed protocol enables automatic async detection
- No breaking changes - backward compatible with sync-only synthesizers

**Files Modified**:
- ✅ `apps/tts-worker/tts_worker/piper_synth.py` - Added async wrappers
- ✅ `packages/tars-core/src/tars/domain/tts.py` - Added async detection and async synthesis method
- ✅ All tests pass (159 passed, 4 skipped)

---

### 2.5 **LOW PRIORITY**: LLM Worker - Async Tool Execution ⚠️

**Problem**:
```python
# apps/llm-worker/llm_worker/service.py
async def _execute_tool_calls(self, client, tool_calls: list[dict], ...) -> list[dict]:
    # ...
    while asyncio.get_event_loop().time() - start_time < timeout:
        if call_id in self.pending_tool_results:
            result = self.pending_tool_results.pop(call_id)
            break
        await asyncio.sleep(0.1)  # POLLING - inefficient
```

**Impact**:
- Busy-wait polling wastes CPU cycles
- Fixed 100ms polling interval adds latency
- Not using async primitives properly

**Solution**:
```python
class LLMService:
    def __init__(self):
        self._tool_futures: Dict[str, asyncio.Future[dict]] = {}
    
    async def _handle_tool_result(self, payload: bytes) -> None:
        """Handle tool call results."""
        try:
            data = json.loads(payload)
            call_id = data.get("call_id")
            if call_id and call_id in self._tool_futures:
                future = self._tool_futures.pop(call_id)
                future.set_result(data)
        except Exception as e:
            logger.error("Failed to handle tool result: %s", e)
    
    async def _execute_tool_calls(self, client, tool_calls: list[dict], ...) -> list[dict]:
        """Execute tool calls with async futures (no polling)."""
        results = []
        for call in tool_calls:
            call_id = call.get("id")
            if not call_id:
                continue
            
            # Create future for this tool call
            future = asyncio.Future()
            self._tool_futures[call_id] = future
            
            # Publish tool call request
            await self._publish_event(...)
            
            try:
                # Wait for result with timeout (no polling)
                result = await asyncio.wait_for(future, timeout=30.0)
                results.append(result)
            except asyncio.TimeoutError:
                logger.warning("Timeout for tool call %s", call_id)
                self._tool_futures.pop(call_id, None)
                results.append({"call_id": call_id, "error": "timeout"})
        
        return results
```

**Benefits**:
- No busy-wait polling - more efficient
- Immediate response when tool result arrives
- Better timeout handling

**Files to Modify**:
- `apps/llm-worker/llm_worker/service.py` - Replace polling with futures

---

## 3. Additional Optimizations

### 3.1 Use `asyncio.TaskGroup` (Python 3.11+)

**Current**: Manual task tracking with `asyncio.create_task()`  
**Better**: Use `TaskGroup` for structured concurrency

```python
# Instead of:
self._fft_task = asyncio.create_task(self._fft_loop())
self._partials_task = asyncio.create_task(self._partials_loop())

# Use TaskGroup:
async with asyncio.TaskGroup() as tg:
    tg.create_task(self._fft_loop())
    tg.create_task(self._partials_loop())
    tg.create_task(self.process_audio_stream())
# Automatic error propagation and cleanup
```

**Benefits**:
- Automatic exception propagation
- Clean cancellation of all tasks
- Better error handling

**Files to Consider**:
- `apps/stt-worker/stt_worker/app.py` - Background tasks
- `apps/router/main.py` - Dispatcher tasks

---

### 3.2 OpenAI Provider - Already Async ✅

**Status**: The OpenAI provider correctly uses `httpx.AsyncClient` for non-blocking HTTP.  
**No changes needed** - this is well implemented.

---

### 3.3 Audio Preprocessing - Consider Thread Pool

**Current**: Audio preprocessing (`preprocess_pcm`) runs inline  
**Potential**: Move to `asyncio.to_thread()` if CPU-intensive

```python
# Only if profiling shows preprocessing is slow (>10ms)
if preprocess_fn:
    processed = await asyncio.to_thread(preprocess_fn, chunk_bytes, ...)
```

**Priority**: Low - measure first

---

## 4. Implementation Strategy

### Phase 1: Critical Path (Week 1)
1. **STT Worker** - Offload Whisper transcription to thread pool
2. **Memory Worker** - Make embeddings async with thread pool
3. Add comprehensive async tests

### Phase 2: Service Quality (Week 2)
4. **LLM Worker** - Fix RAG query pattern (no more inline subscribe)
5. **TTS Worker** - Add async wrappers for synthesis
6. **LLM Worker** - Replace tool polling with futures

### Phase 3: Architecture (Week 3)
7. Migrate to `asyncio.TaskGroup` in STT/Router
8. Add async profiling and metrics
9. Document async patterns in copilot-instructions

---

## 5. Testing Strategy

### 5.1 Unit Tests

```python
# Test async transcription
@pytest.mark.asyncio
async def test_transcribe_async():
    transcriber = SpeechTranscriber()
    audio_data = generate_test_audio()
    text, conf, metrics = await transcriber.transcribe_async(audio_data, 16000)
    assert text
    assert isinstance(conf, float)

# Test embeddings don't block
@pytest.mark.asyncio
async def test_embeddings_concurrent():
    embedder = STEmbedder("model")
    tasks = [embedder.embed_async(["test"]) for _ in range(5)]
    results = await asyncio.gather(*tasks)
    assert len(results) == 5
```

### 5.2 Integration Tests

- Verify event loop responsiveness during CPU-bound operations
- Test MQTT message handling under load
- Measure latency improvements

### 5.3 Performance Benchmarks

```python
# Measure event loop blocking
async def test_event_loop_responsiveness():
    start = asyncio.get_event_loop().time()
    transcriber = SpeechTranscriber()
    # Should not block for >50ms
    await transcriber.transcribe_async(audio_data, 16000)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.05, "Transcription blocked event loop"
```

---

## 6. Patterns to Follow

### 6.1 CPU-Bound Work

```python
# ❌ BAD: Blocks event loop
def process_data(data):
    # Heavy computation
    return result

async def handler():
    result = process_data(data)  # BLOCKS!

# ✅ GOOD: Use asyncio.to_thread
async def handler():
    result = await asyncio.to_thread(process_data, data)
```

### 6.2 Async Request-Response Pattern

```python
# ❌ BAD: Inline subscription + polling
async def request_and_wait():
    await publish_request()
    async with client.messages() as stream:
        await client.subscribe(topic)
        async for msg in stream:
            return msg  # Poor pattern

# ✅ GOOD: Use futures with correlation IDs
async def request_and_wait(correlation_id: str):
    future = asyncio.Future()
    pending_requests[correlation_id] = future
    await publish_request(correlation_id)
    return await asyncio.wait_for(future, timeout=5.0)
```

### 6.3 Background Tasks

```python
# ❌ OKAY: Manual task tracking
task = asyncio.create_task(background_work())
try:
    await main_work()
finally:
    task.cancel()

# ✅ BETTER: TaskGroup (Python 3.11+)
async with asyncio.TaskGroup() as tg:
    tg.create_task(background_work())
    await main_work()
# Automatic cancellation and error propagation
```

---

## 7. Known Constraints

### 7.1 Compatibility

- **paho-mqtt < 2.0** required for `asyncio-mqtt` compatibility
- Must maintain Python 3.11+ target
- Keep threading for platform-specific audio (PulseAudio)

### 7.2 Don't Break

- Audio capture thread (platform-specific, must stay threaded)
- PulseAudio socket handling (host network mode)
- Existing MQTT QoS and retention behavior

### 7.3 Avoid

- Mixing `threading.Thread` with `asyncio.create_task` - pick one pattern
- Blocking calls inside async functions without `to_thread()`
- Creating new subscriptions for request-response patterns

---

## 8. Metrics & Observability

### 8.1 Add Async Metrics

```python
# Measure event loop lag
loop_lag_histogram = Histogram("event_loop_lag_seconds")

# Measure async operation duration
async def timed_operation(op_name: str):
    start = time.monotonic()
    try:
        yield
    finally:
        duration = time.monotonic() - start
        operation_duration_histogram.observe(duration, {"op": op_name})
```

### 8.2 Logging Enhancements

```python
# Log async operation context
logger.info("Starting CPU-bound work", extra={
    "operation": "transcribe",
    "thread": threading.current_thread().name,
    "coroutine": asyncio.current_task().get_name()
})
```

---

## 9. PR Checklist Template

- [ ] CPU-bound operations use `asyncio.to_thread()`
- [ ] No blocking calls in async functions
- [ ] Request-response uses correlation IDs + futures (not polling)
- [ ] Tests verify event loop responsiveness
- [ ] Async functions have proper timeout handling
- [ ] Background tasks use `TaskGroup` or proper cancellation
- [ ] Structured logs include async context
- [ ] `make check` passes (including new async tests)

---

## 10. References

- [Asyncio Documentation](https://docs.python.org/3/library/asyncio.html)
- [PEP 654: Exception Groups and TaskGroup](https://peps.python.org/pep-0654/)
- [asyncio-mqtt Usage](https://sbtinstruments.github.io/asyncio-mqtt/)
- Existing: `.github/copilot-instructions.md` - Async/concurrency section

---

## Appendix A: File Priority Matrix

| File | Priority | Effort | Impact |
|------|----------|--------|--------|
| `apps/stt-worker/stt_worker/transcriber.py` | 🔴 HIGH | Medium | High |
| `apps/memory-worker/memory_worker/service.py` | 🔴 HIGH | Medium | High |
| `apps/llm-worker/llm_worker/service.py` (RAG) | 🟡 MEDIUM | Low | Medium |
| `apps/llm-worker/llm_worker/service.py` (tools) | 🟡 MEDIUM | Low | Low |
| `apps/tts-worker/tts_worker/piper_synth.py` | 🟡 MEDIUM | Low | Medium |
| `apps/stt-worker/stt_worker/app.py` (TaskGroup) | 🟢 LOW | Low | Low |
| `apps/router/main.py` | 🟢 LOW | None | None (already good) |

---

## Appendix B: Async Anti-Patterns Found

1. **Blocking in async context** - Transcription, embeddings
2. **Polling instead of futures** - Tool results, RAG queries
3. **Per-request subscriptions** - RAG query pattern
4. **Missing timeout handling** - Several async operations
5. **Manual task tracking** - Could use TaskGroup

---

## Summary

The py-tars codebase has a **solid async foundation**. The primary improvements involve:

1. **Offloading CPU-bound work** (transcription, embeddings) to thread pools
2. **Fixing request-response patterns** to use futures instead of polling
3. **Adding async wrappers** for consistency

These changes will:
- Reduce event loop blocking by 80-90%
- Improve responsiveness during heavy operations
- Enable better concurrent request handling
- Maintain clean async/await code patterns

All changes should be **incremental, tested, and backward-compatible**.
