# NPU Reranker Conversion - Final Report

**Date**: 2025-10-10  
**Status**: ✅ Conversion Successful, ⚠️ Performance Not Viable  
**Recommendation**: Use CPU reranker (flashrank)

## Executive Summary

Successfully converted the ms-marco-MiniLM-L-12-v2 reranker to RKNN format for NPU acceleration. However, performance testing revealed that the **NPU version is 2x slower than the CPU version** (185ms vs 80-90ms per passage). The CPU reranker uses INT8 quantization which RKNN couldn't support, resulting in a larger FP16 model that doesn't benefit from NPU acceleration.

**Recommendation**: Keep the CPU reranker (flashrank INT8 quantized ONNX).

## Technical Details

### Conversion Process

1. **Source Model**: cross-encoder/ms-marco-MiniLM-L-12-v2 (Hugging Face)
2. **Export**: PyTorch → FP32 ONNX (128 MB)
3. **Shape Fixing**: Dynamic shapes → Fixed [1, 512]
4. **RKNN Conversion**: FP32 ONNX → FP16 RKNN (69 MB)
5. **Validation**: ✓ Model loads and runs on NPU

### Why Flashrank Quantized Model Failed

The flashrank-provided quantized ONNX model (32 MB) uses `DynamicQuantizeLinear` operators that are **incompatible with RKNN**:

```
ValueError: The DynamicQuantizeLinear('/bert/embeddings/LayerNorm/Add_1_output_0_QuantizeLinear') 
will cause the graph to be a dynamic graph! Remove it manually and try again!
```

Solution: Export original FP32 model from Hugging Face instead.

### Model Specifications

| Aspect | CPU (Flashrank) | NPU (RKNN) |
|--------|----------------|------------|
| **Format** | INT8 quantized ONNX | FP16 RKNN |
| **Size** | 32 MB | 69 MB |
| **Layers** | 12-layer BERT | 12-layer BERT |
| **Seq Length** | 512 tokens | 512 tokens |
| **Precision** | INT8 | FP16 |

## Performance Results

### Per-Passage Inference Time

| Configuration | Time | Status |
|--------------|------|--------|
| CPU (flashrank INT8 ONNX) | 80-90ms | ✓ Optimized |
| NPU (RKNN FP16) | 185ms | ⚠️ 2x slower |

### Full RAG Pipeline (5 Candidates)

| Component | CPU Time | NPU Time |
|-----------|----------|----------|
| Embedding (NPU) | - | 39ms |
| Retrieval | - | 26ms |
| Reranking | 449ms | 925ms |
| **Total** | **514ms** | **990ms** |

**Result**: NPU reranker adds 476ms overhead vs CPU reranker's 449ms.

## Root Cause Analysis

### Why is NPU Slower?

1. **Quantization Mismatch**
   - CPU: INT8 (4x smaller, 4x faster memory access)
   - NPU: FP16 (2x FP32, but still 2x larger than INT8)
   - INT8 quantization incompatible with RKNN for this model

2. **Model Complexity**
   - 12-layer BERT is 2x larger than embedder (6-layer)
   - May exceed optimal NPU core utilization
   - Memory-bound rather than compute-bound

3. **Sequence Length**
   - 512 tokens (query + passage) vs 256 tokens (embedder)
   - 2x longer sequences = 2x more data movement
   - Amplifies memory bandwidth bottleneck

4. **NPU Architecture**
   - Optimized for smaller, highly-parallel models
   - Larger models become memory-bandwidth limited
   - CPU has better access to system memory

### Comparison with Embedder Success

| Model | Layers | Seq Length | CPU Time | NPU Time | Speedup |
|-------|--------|-----------|----------|----------|---------|
| **Embedder** | 6 | 256 | 150ms | 39ms | **3.8x** ✓ |
| **Reranker** | 12 | 512 | 80-90ms | 185ms | **0.5x** ⚠️ |

**Key Insight**: Success with small models (embedder) doesn't guarantee success with larger models (reranker).

## Production Recommendations

### Option 1: NPU Embedder ONLY (RECOMMENDED) ✅

```yaml
Configuration:
  NPU_EMBEDDER_ENABLED: 1
  RERANK_MODEL: ""  # Disabled

Performance:
  Embedding (NPU):    39ms
  Retrieval:          26ms
  Total:              65ms ✓ VOICE-READY
```

**Benefits**:
- Fast: 65ms RAG queries
- Voice-ready: <100ms target met
- Good quality: Hybrid retrieval (vector + BM25)

### Option 2: NPU Embedder + CPU Reranker (OPTIONAL) ⚠️

```yaml
Configuration:
  NPU_EMBEDDER_ENABLED: 1
  RERANK_MODEL: ms-marco-MiniLM-L-12-v2

Performance:
  Embedding (NPU):    39ms
  Retrieval:          26ms
  Reranking (CPU):    449ms
  Total:              514ms ⚠️ BORDERLINE
```

**Use Case**: Non-real-time queries where quality > speed

### Option 3: NPU Embedder + NPU Reranker (NOT RECOMMENDED) ❌

```yaml
Configuration:
  NPU_EMBEDDER_ENABLED: 1
  NPU_RERANKER_ENABLED: 1

Performance:
  Embedding (NPU):    39ms
  Retrieval:          26ms
  Reranking (NPU):    925ms
  Total:              990ms ❌ TOO SLOW
```

**Why Not**: 2x slower than CPU reranker, unacceptable for voice.

## Implementation Files

### Created Scripts

**apps/memory-worker/scripts/convert_reranker_to_rknn.py**
- Exports FP32 ONNX from Hugging Face (cross-encoder/ms-marco-MiniLM-L-12-v2)
- Fixes dynamic shapes to static [1, 512] for RKNN compatibility
- Converts ONNX to RKNN format (FP16, RK3588 target)
- Validates conversion with test inference

**Usage**:
```bash
# Convert (only needed once)
docker exec tars-memory-npu python /workspace/apps/memory-worker/scripts/convert_reranker_to_rknn.py

# Force reconversion
docker exec tars-memory-npu env FORCE_CONVERT=1 python /workspace/apps/memory-worker/scripts/convert_reranker_to_rknn.py
```

### Generated Models

**Location**: `/data/model_cache/reranker/`

| File | Size | Description |
|------|------|-------------|
| `ms-marco-MiniLM-L-12-v2_fp32.onnx` | 128 MB | FP32 ONNX (exported from HF) |
| `ms-marco-MiniLM-L-12-v2.rknn` | 69 MB | FP16 RKNN (NPU-optimized) |

**Status**: Models exist but not recommended for production use.

## Lessons Learned

### 1. Model Size Matters for NPU Acceleration

- **Small models (6-layer BERT)**: Excellent NPU performance (3.8x speedup)
- **Large models (12-layer BERT)**: Poor NPU performance (2x slower)
- **Threshold**: ~50 MB RKNN model size seems optimal for RK3588

### 2. Quantization is Critical for Performance

- **INT8**: 4x smaller, 4x less memory bandwidth
- **FP16**: 2x smaller than FP32, but 2x larger than INT8
- **FP32**: Baseline, largest and slowest

**Performance Ranking** (for CPU):
1. INT8 quantized (fastest)
2. FP16
3. FP32 (slowest)

**NPU Limitation**: Couldn't use INT8 for this model due to DynamicQuantizeLinear incompatibility.

### 3. Sequence Length Amplifies Overhead

- Embedder: 256 tokens → 39ms NPU (3.8x faster)
- Reranker: 512 tokens → 185ms NPU (2x slower)

**Rule of Thumb**: Longer sequences increase memory bandwidth requirements, reducing NPU benefits.

### 4. Not All Models Benefit from NPU

**Good Candidates**:
- Small models (<50 MB RKNN)
- Short sequences (<256 tokens)
- Compute-bound operations
- Examples: Embeddings, small classification models

**Poor Candidates**:
- Large models (>70 MB RKNN)
- Long sequences (>512 tokens)
- Memory-bound operations
- Examples: Large rerankers, long-context models

### 5. CPU Quantization Can Beat NPU FP16

The flashrank team's INT8 quantization is highly optimized:
- 32 MB vs 69 MB (2.15x smaller)
- 80-90ms vs 185ms (2x faster)
- Inference-optimized ONNX Runtime

**Takeaway**: Don't assume NPU is always faster. Profile both!

## Alternative Approaches (Not Pursued)

### 1. Smaller Reranker Model

Could try `cross-encoder/ms-marco-MiniLM-L-6-v2` (6-layer):
- Expected size: ~35 MB RKNN
- Might benefit from NPU like embedder
- Quality tradeoff unknown

**Decision**: Not worth effort given CPU reranker already fast enough.

### 2. Batch Processing

Convert model with batch size > 1:
- Process multiple query-passage pairs simultaneously
- Better NPU utilization
- Higher throughput but same latency per query

**Decision**: Voice application is single-query focused, no benefit.

### 3. Reduced Sequence Length

Use 256 tokens instead of 512:
- Faster processing
- May reduce reranking quality
- Query + passage might not fit

**Decision**: Quality degradation risk not worth it.

## Conclusion

The NPU reranker conversion was technically successful (model works) but not practically viable (too slow). The root cause is the **incompatibility between INT8 quantization and RKNN**, forcing us to use FP16 which doesn't compete with the CPU's INT8 performance.

### Final Recommendation

**Production Configuration**:
```yaml
# .env
NPU_EMBEDDER_ENABLED=1        # Use NPU for embeddings (3.8x faster)
RERANK_MODEL=                 # Disabled by default (too slow for voice)

# For non-realtime quality boost:
# RERANK_MODEL=ms-marco-MiniLM-L-12-v2  # CPU reranker (flashrank)
```

**Performance**:
- NPU embedder: 39ms ✓
- Hybrid retrieval: 26ms ✓
- **Total RAG**: 65ms ✓ Voice-ready
- Optional CPU reranker: +449ms (for quality, not realtime)

### Key Metrics

| Metric | Value | Status |
|--------|-------|--------|
| RAG query time (no rerank) | 65ms | ✅ Voice-ready |
| RAG query time (CPU rerank) | 514ms | ⚠️ Borderline |
| RAG query time (NPU rerank) | 990ms | ❌ Too slow |
| NPU embedder speedup | 3.8x | ✅ Excellent |
| NPU reranker speedup | 0.5x | ❌ Regression |

## References

- **Embedder Performance**: See `docs/NPU_EMBEDDER_PERFORMANCE.md`
- **Conversion Plan**: See `plan/npu_reranker_conversion_plan.md`
- **Conversion Script**: `apps/memory-worker/scripts/convert_reranker_to_rknn.py`
- **RKNN Documentation**: https://github.com/rockchip-linux/rknn-toolkit2
- **Flashrank**: https://github.com/PrithivirajDamodaran/FlashRank
