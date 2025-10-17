# NPU Reranker INT8 Quantization Implementation

## Overview

This document describes the implementation of INT8 quantization for the NPU reranker to match CPU performance.

## Problem

The initial FP16 RKNN reranker was **2x slower** than the CPU version:
- **CPU (flashrank)**: 80-90ms per passage (32 MB INT8 quantized ONNX)
- **NPU FP16**: 185ms per passage (69 MB FP16 RKNN)

**Root Cause**: The CPU version uses INT8 quantization (4x less memory bandwidth than FP16), making it more efficient for memory-bound operations like 12-layer BERT with 512 token sequences.

## Solution: INT8 Quantization for RKNN

### Implementation

Added INT8 post-training quantization support to the RKNN conversion pipeline:

1. **Calibration Dataset Generation**
   - Generates realistic tokenized query+passage pairs
   - Configurable sample count (default: 100)
   - Varied token distributions: common words, special tokens, rare tokens
   - Proper attention masks and token type IDs
   - Saved as numpy arrays for RKNN calibration

2. **Enhanced Conversion Script**
   - Environment-controlled quantization mode (`QUANTIZE=1`)
   - Separate output filename for INT8 models (`_int8.rknn` suffix)
   - Automatic calibration dataset generation/reuse
   - Support for regenerating calibration data

3. **Usage**

```bash
# FP16 conversion (default):
python convert_reranker_to_rknn.py

# INT8 conversion:
QUANTIZE=1 python convert_reranker_to_rknn.py

# INT8 with custom calibration:
QUANTIZE=1 CALIBRATION_SAMPLES=200 python convert_reranker_to_rknn.py

# Force dataset regeneration:
QUANTIZE=1 REGENERATE_DATASET=1 python convert_reranker_to_rknn.py
```

## Code Changes

### `convert_reranker_to_rknn.py`

**New Function: `generate_calibration_dataset()`**
```python
def generate_calibration_dataset(output_dir: str, num_samples: int = 100):
    """
    Generate calibration dataset for INT8 quantization.
    
    Creates realistic input samples (tokenized query+passage pairs) for calibration.
    - Generates varied token distributions
    - Proper attention masks
    - Token type IDs (0=query, 1=passage)
    - Saves as numpy arrays for RKNN
    """
```

**Enhanced: `convert_to_rknn()`**
```python
def convert_to_rknn(
    onnx_path: str, 
    rknn_path: str, 
    do_quantization: bool = False,  # INT8 quantization flag
    dataset_path: str = None         # Path to calibration dataset
):
    """Convert ONNX to RKNN with optional INT8 quantization."""
```

**Enhanced: `main()`**
- Auto-detects quantization mode from `QUANTIZE` env var
- Generates `_int8.rknn` suffix for INT8 models
- Auto-generates/reuses calibration dataset
- Better logging for quantization mode

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QUANTIZE` | `0` | Enable INT8 quantization (`1`) or use FP16 (`0`) |
| `CALIBRATION_SAMPLES` | `100` | Number of calibration samples to generate |
| `REGENERATE_DATASET` | `0` | Force regeneration of calibration dataset |
| `FORCE_CONVERT` | `0` | Overwrite existing RKNN model |

## File Structure

```
/data/model_cache/reranker/
├── ms-marco-MiniLM-L-12-v2_fp32.onnx          # 128 MB (source)
├── ms-marco-MiniLM-L-12-v2_fixed.onnx         # 128 MB (fixed shapes)
├── ms-marco-MiniLM-L-12-v2.rknn               #  69 MB (FP16)
├── ms-marco-MiniLM-L-12-v2_int8.rknn          #  ?? MB (INT8, generating...)
└── calibration_data/
    ├── calibration_dataset.txt                # Dataset manifest
    └── sample_XXXX/                           # Per-sample data
        ├── input_ids.npy
        ├── attention_mask.npy
        └── token_type_ids.npy
```

## Expected Results

### Model Size
- **FP16**: 69 MB
- **INT8**: ~17-35 MB (expected 2-4x compression)

### Performance (Hypothesized)
- **CPU INT8**: 80-90ms per passage ✓ (baseline)
- **NPU FP16**: 185ms per passage (2x slower)
- **NPU INT8**: **Target: 80-100ms** (match or beat CPU)

### Why INT8 Should Help
1. **Memory Bandwidth**: 4x less data movement (INT8 vs FP16)
2. **Model Size**: Smaller model fits better in NPU cache
3. **Quantization Match**: Both CPU and NPU using INT8 (apples-to-apples)
4. **NPU Optimization**: RK3588 NPU has INT8 acceleration units

## Testing Plan

1. ✅ Generate INT8 model (in progress)
2. ⏳ Validate model loads and runs
3. ⏳ Benchmark performance (5 passages, multiple runs)
4. ⏳ Compare: CPU INT8 vs NPU FP16 vs NPU INT8
5. ⏳ Update production config if viable

## Performance Testing

### Test Script: `test_reranker_npu.py`

Update to test INT8 model:
```python
# Option 1: Environment variable
NPU_RERANK_MODEL=/data/model_cache/reranker/ms-marco-MiniLM-L-12-v2_int8.rknn \
    python test_reranker_npu.py

# Option 2: Modify test script
reranker = RerankRKNNLite(
    model_path="/data/model_cache/reranker/ms-marco-MiniLM-L-12-v2_int8.rknn"
)
```

### Benchmark Comparison

| Configuration | Model Size | Per-Passage | 5 Passages | Status |
|--------------|------------|-------------|------------|--------|
| CPU (flashrank INT8) | 32 MB | 80-90ms | 449ms | ✓ Baseline |
| NPU FP16 | 69 MB | 185ms | 925ms | ⚠️ Too slow |
| NPU INT8 | ?? MB | ??ms | ??ms | 🔄 Testing |

## Production Decision

### If NPU INT8 ≤ 100ms per passage:
```env
# Enable NPU reranker
NPU_RERANK_ENABLED=1
NPU_RERANK_MODEL=/data/model_cache/reranker/ms-marco-MiniLM-L-12-v2_int8.rknn
RERANK_MODEL=""  # Disable CPU reranker
```

### If NPU INT8 > 100ms per passage:
```env
# Keep CPU reranker
NPU_RERANK_ENABLED=0
RERANK_MODEL=ms-marco-MiniLM-L-12-v2  # flashrank CPU
NPU_EMBEDDER_ENABLED=1  # Keep NPU embedder (proven 3.8x speedup)
```

## Lessons Learned

1. **Quantization Matters**: Don't compare FP16 NPU to INT8 CPU
2. **Model Size Scaling**: Larger models (12-layer) less likely to benefit from NPU than smaller (6-layer)
3. **Memory Bandwidth**: For sequence models, bandwidth often more important than compute
4. **Calibration Dataset**: Realistic token distributions important for accurate quantization
5. **Separate Filenames**: Use `_int8` suffix to avoid overwriting FP16 models

## References

- NPU Embedder Success: `docs/NPU_EMBEDDER_PERFORMANCE.md` (3.8x speedup with INT8)
- FP16 Failure Analysis: `docs/NPU_RERANKER_ANALYSIS.md` (2x slower than CPU)
- Conversion Script: `apps/memory-worker/scripts/convert_reranker_to_rknn.py`
- RKNN Documentation: RK3588 NPU supports INT8/INT16/FP16

## Next Steps

1. ⏳ Wait for INT8 model generation (~5-10 minutes)
2. ⏳ Test INT8 model performance
3. ⏳ Compare results with CPU and FP16
4. ⏳ Make production decision
5. ⏳ Update memory-worker configuration
6. ⏳ Document final findings in `NPU_RERANKER_ANALYSIS.md`

---

**Status**: INT8 model generation in progress (2025-10-10 14:51 UTC)
