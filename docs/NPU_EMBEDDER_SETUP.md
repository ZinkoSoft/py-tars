# NPU Embedder Setup Guide

## Overview

This guide explains how to convert the SentenceTransformer embedding model to RKNN format for NPU acceleration on the RK3588, and how to enable it in the memory worker.

## Prerequisites

### Software Requirements
- Python 3.11+
- `rknn-toolkit2` (for conversion on x86_64 or aarch64)
- `rknn-toolkit-lite2` (for inference on RK3588 device)
- `sentence-transformers`, `torch`, `onnx`, `onnxruntime`

### Hardware Requirements
- **Conversion**: Can be done on x86_64 or aarch64 (including the RK3588 itself)
- **Inference**: RK3588 NPU device (e.g., Orange Pi 5 Max)

## Automatic Model Conversion (Recommended)

**The easiest way**: NPU models are automatically converted at runtime when the container starts.

### Step 1: Enable NPU in .env

Add to your `.env` file:

```bash
NPU_EMBEDDER_ENABLED=1
```

### Step 2: Build Memory Worker

Build the container with RKNN toolkit support:

```bash
docker compose build memory
```

**What happens at build**:
1. RKNN toolkit and dependencies are installed in the container
2. Conversion scripts are copied to the container
3. Container is ready to convert models at runtime

### Step 3: Start the Service

```bash
docker compose up -d memory
```

**What happens at startup**:
1. Container checks if RKNN model exists in `/data/model_cache/embedder/`
2. If not found, automatically converts:
   - SentenceTransformer → ONNX (87MB)
   - ONNX → RKNN (45MB)
3. Models are cached in the mounted volume (persistent across restarts)
4. Service starts and uses NPU embedder

**That's it!** Models are created once and reused on subsequent startups.

---

## Manual Model Conversion (Advanced)

If you need to convert models manually (for testing or different models):

### Step 1: Export to ONNX

```bash
cd apps/memory-worker/scripts

# Export default model (all-MiniLM-L6-v2) to project model cache
python convert_st_to_onnx.py \
  --model sentence-transformers/all-MiniLM-L6-v2 \
  --output ../../../data/model_cache/embedder/all-MiniLM-L6-v2.onnx \
  --max-seq-length 256
```

**Output**: ONNX model at `data/model_cache/embedder/all-MiniLM-L6-v2.onnx` (~87MB)

### Step 2: Convert to RKNN

```bash
cd apps/memory-worker/scripts

# Convert to RKNN (FP16 precision, no quantization)
python convert_onnx_to_rknn.py \
  ../../../data/model_cache/embedder/all-MiniLM-L6-v2.onnx \
  ../../../data/model_cache/embedder/all-MiniLM-L6-v2.rknn
```

**Output**: RKNN model at `data/model_cache/embedder/all-MiniLM-L6-v2.rknn` (~45MB)

### Step 3: Verify Model Files

```bash
ls -lh data/model_cache/embedder/
```

Expected output:
```
all-MiniLM-L6-v2.onnx  # ~87MB - ONNX intermediate format
all-MiniLM-L6-v2.rknn  # ~45MB - RKNN NPU format
```

## Enabling NPU Acceleration

### Option 1: Environment Variables (Recommended)

## Configuration

All configuration is in `.env` - just enable NPU and build:

```bash
# Enable NPU embedder (0=disabled, 1=enabled)
NPU_EMBEDDER_ENABLED=1

# Path to RKNN model (default works for auto-built models)
RKNN_EMBEDDER_PATH=/data/model_cache/embedder/all-MiniLM-L6-v2.rknn

# NPU core selection (0=auto, 1=core0, 2=core1, 4=core2, 7=all cores)
NPU_CORE_MASK=0

# Fallback to CPU if NPU unavailable
NPU_FALLBACK_CPU=1
```

**Note**: When `NPU_EMBEDDER_ENABLED=1`, Docker compose automatically:
- Passes build arg to install RKNN toolkit
- Converts models during build
- Mounts NPU device `/dev/dri/renderD129`
- Configures model cache volume

### Option 2: Docker Compose Configuration

The memory worker service needs access to the NPU device and model files:

```yaml
# ops/compose.yml
memory:
  image: tars/memory:dev
  container_name: tars-memory
  devices:
    - /dev/dri/renderD129:/dev/dri/renderD129  # NPU device
  volumes:
    - ../data:/data  # Model cache already mounted
  environment:
    - NPU_EMBEDDER_ENABLED=1
    - RKNN_EMBEDDER_PATH=/data/model_cache/embedder/all-MiniLM-L6-v2.rknn
```

### Option 3: Manual Testing

Test the NPU embedder before enabling in production:

```bash
# Check NPU availability
python -c "
from apps.wake_activation.wake_activation.npu_utils import check_npu_availability
is_available, status = check_npu_availability()
print(status)
"

# Test NPU embedder (after integration is complete)
# python test_npu_embedder.py
```

## Model Specifications

### Input Requirements
- **Shape**: Fixed [1, 256] tokens
- **Format**: Integer token IDs (int64)
- **Inputs**: 
  - `input_ids`: Token IDs from BERT tokenizer
  - `attention_mask`: 1 for real tokens, 0 for padding
  - `token_type_ids`: All zeros for single sentence

### Output Format
- **Shape**: [1, 256, 384]
- **Format**: Float16 (FP16)
- **Content**: Token embeddings from BERT encoder

### Post-Processing (Python)
After NPU inference, apply:
1. **Mean pooling**: Average token embeddings (respecting attention mask)
2. **L2 normalization**: Normalize to unit length

Result: [1, 384] sentence embedding (same as CPU version)

## Performance Expectations

### Embedding Time
- **CPU (current)**: ~150ms per query
- **NPU (FP16)**: ~40-60ms per query (3-4x faster)
- **NPU (int8)**: ~20-30ms per query (5-7x faster, future optimization)

### End-to-End RAG Query
- **CPU**: ~220ms (embedding 150ms + search 70ms)
- **NPU**: ~110-130ms (embedding 40-60ms + search 70ms)
- **Improvement**: ~2x overall speedup

### Batch Processing
- **CPU**: 10 docs = ~1.5s
- **NPU**: 10 docs = ~0.3-0.5s (3-5x faster)

## Architecture

### Model Pipeline
```
Text Input
  ↓
Tokenization (CPU, Python)
  - BertTokenizer with WordPiece
  - Padding to 256 tokens
  - Returns: input_ids, attention_mask, token_type_ids
  ↓
BERT Encoder (NPU, RKNN)
  - 6 transformer layers
  - 384-dimensional embeddings
  - FP16 precision
  - Returns: [1, 256, 384] token embeddings
  ↓
Mean Pooling (CPU, Python)
  - Average over sequence dimension
  - Respect attention mask
  - Returns: [1, 384]
  ↓
L2 Normalization (CPU, Python)
  - Normalize to unit length
  - Returns: [1, 384]
  ↓
Final Embedding
```

### Why Split Preprocessing?
- **Tokenization in Python**: BERT tokenizer is complex, easier in Python
- **BERT on NPU**: Compute-heavy, benefits most from acceleration
- **Pooling in Python**: Simple operations, minimal overhead (~5ms)
- **Clean separation**: Easy to debug and maintain

## Troubleshooting

### NPU Not Detected

**Problem**: NPU device not found
```
❌ No NPU device nodes found (/dev/rknpu or renderD129)
```

**Solution**:
```bash
# Check for NPU device
ls -l /dev/dri/renderD*
ls -l /dev/rknpu

# Check user permissions
groups  # Should include 'render' or 'video'

# Add user to groups if needed
sudo usermod -aG render,video $USER
# Log out and back in
```

### RKNN Runtime Error

**Problem**: `librknnrt.so not found`

**Solution**:
```bash
# Install RKNN runtime (on RK3588 device)
sudo apt-get install -y rockchip-mpp-dev rockchip-rga-dev
pip install rknn-toolkit-lite2
```

### Docker Build Fails

**Problem**: Models not created during build

**Solution**: Ensure `NPU_EMBEDDER_ENABLED=1` is in `.env` before building
```bash
# Check build args are passed
docker compose config | grep NPU_EMBEDDER_ENABLED

# Force rebuild with no cache
docker compose build --no-cache memory
```

### Conversion Fails: Dynamic Shapes

**Problem**: `The input shape ['batch_size', 'sequence'] is not support!`

**Solution**: This is fixed in the scripts - ONNX export uses fixed shapes
```python
# In convert_st_to_onnx.py (already configured correctly)
dynamic_axes = None  # Must be None for RKNN
```

### Model Output Mismatch

**Problem**: NPU embeddings don't match CPU embeddings

**Checks**:
1. Verify ONNX export validation passed (max_diff < 0.001)
2. Check pooling implementation (mean vs cls token)
3. Verify normalization is applied
4. Test with cosine similarity threshold (>0.99 expected)

### Performance Lower Than Expected

**Possible causes**:
1. **Not using NPU**: Check logs for "Using CPU embedder" fallback
2. **Single core**: Try `NPU_CORE_MASK=7` for all 3 cores
3. **Overhead**: Tokenization and pooling add ~15-20ms on CPU
4. **First query**: Model loading takes ~500ms, subsequent queries are fast

## Directory Structure

```
py-tars/
├── apps/
│   └── memory-worker/
│       ├── scripts/
│       │   ├── convert_st_to_onnx.py      # Step 1: PyTorch → ONNX
│       │   └── convert_onnx_to_rknn.py    # Step 2: ONNX → RKNN
│       └── memory_worker/
│           ├── service.py                  # Uses embedder
│           └── (future) npu_embedder.py    # NPU implementation
├── data/
│   └── model_cache/
│       └── embedder/
│           ├── all-MiniLM-L6-v2.onnx      # ONNX intermediate
│           └── all-MiniLM-L6-v2.rknn      # NPU-optimized model
└── docs/
    └── NPU_EMBEDDER_SETUP.md              # This file
```

## Model Cache Location

All embedding models are stored in `data/model_cache/embedder/`:
- **Why**: Consistent with other models (wake word, whisper)
- **Mounted**: `/data/model_cache` in Docker containers
- **Persistent**: Survives container restarts
- **Shared**: Accessible to all services if needed

## Advanced Configuration

### Using Different Models

To convert a different SentenceTransformer model:

```bash
# Example: paraphrase-MiniLM-L6-v2
python convert_st_to_onnx.py \
  --model sentence-transformers/paraphrase-MiniLM-L6-v2 \
  --output ../../../data/model_cache/embedder/paraphrase-MiniLM-L6-v2.onnx

python convert_onnx_to_rknn.py \
  ../../../data/model_cache/embedder/paraphrase-MiniLM-L6-v2.onnx \
  ../../../data/model_cache/embedder/paraphrase-MiniLM-L6-v2.rknn
```

Then update env:
```bash
RKNN_EMBEDDER_PATH=/data/model_cache/embedder/paraphrase-MiniLM-L6-v2.rknn
```

### Multi-Core NPU Usage

```bash
# Auto-select cores (default, recommended)
NPU_CORE_MASK=0

# Use specific cores
NPU_CORE_MASK=1  # Core 0 only
NPU_CORE_MASK=2  # Core 1 only  
NPU_CORE_MASK=4  # Core 2 only
NPU_CORE_MASK=7  # All 3 cores (1+2+4)
```

### Quantization (Future)

For int8 quantization (requires calibration dataset):

```bash
# Create calibration dataset from memory documents
python create_calibration_dataset.py \
  --input /data/memory.pickle.gz \
  --output /tmp/calibration_data.txt \
  --samples 100

# Convert with quantization
python convert_onnx_to_rknn.py \
  ../../../data/model_cache/embedder/all-MiniLM-L6-v2.onnx \
  ../../../data/model_cache/embedder/all-MiniLM-L6-v2-int8.rknn \
  --quantize \
  --calibration-dataset /tmp/calibration_data.txt
```

## Verification Checklist

Before enabling in production:

- [ ] ONNX export completed successfully
- [ ] RKNN conversion completed successfully
- [ ] Both model files exist in `data/model_cache/embedder/`
- [ ] NPU device detected: `/dev/dri/renderD129` or `/dev/rknpu`
- [ ] RKNN runtime installed: `librknnrt.so` available
- [ ] User in render/video groups
- [ ] Docker compose has NPU device mounted
- [ ] Environment variables configured
- [ ] Test inference successful (after integration)
- [ ] Performance benchmarks meet expectations
- [ ] Output validation passed (cosine similarity > 0.99)

## References

- **Wake Activation NPU**: `apps/wake-activation/` - Similar NPU integration pattern
- **RKNN Toolkit**: https://github.com/rockchip-linux/rknn-toolkit2
- **SentenceTransformers**: https://www.sbert.net/
- **RK3588 NPU Docs**: Rockchip NPU documentation

## Support

For issues or questions:
1. Check this documentation first
2. Review `plan/npu_embedder_acceleration.md` for technical details
3. Check wake-activation NPU implementation for reference patterns
4. Review RKNN toolkit documentation

## Future Enhancements

- [ ] Int8 quantization support with calibration dataset
- [ ] Batch processing optimization
- [ ] Dynamic sequence length support (if RKNN adds support)
- [ ] Alternative embedding models
- [ ] Performance profiling tools
- [ ] Automatic model download and conversion
