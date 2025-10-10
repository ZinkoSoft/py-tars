# Memory Worker Conversion Scripts

This directory contains scripts for converting the SentenceTransformer embedding model to RKNN format for NPU acceleration.

## Quick Start

From this directory, run:

```bash
# Step 1: Export to ONNX (creates ../../../data/model_cache/embedder/all-MiniLM-L6-v2.onnx)
python convert_st_to_onnx.py

# Step 2: Convert to RKNN (creates ../../../data/model_cache/embedder/all-MiniLM-L6-v2.rknn)
python convert_onnx_to_rknn.py \
  ../../../data/model_cache/embedder/all-MiniLM-L6-v2.onnx \
  ../../../data/model_cache/embedder/all-MiniLM-L6-v2.rknn

# Step 3: Enable in .env
echo "NPU_EMBEDDER_ENABLED=1" >> ../../../.env
echo "RKNN_EMBEDDER_PATH=/data/model_cache/embedder/all-MiniLM-L6-v2.rknn" >> ../../../.env
```

## Files

- **convert_st_to_onnx.py** - Export SentenceTransformer (PyTorch) to ONNX format
- **convert_onnx_to_rknn.py** - Convert ONNX model to RKNN format for RK3588 NPU

## Documentation

See **[docs/NPU_EMBEDDER_SETUP.md](../../../docs/NPU_EMBEDDER_SETUP.md)** for complete setup guide including:
- Prerequisites and requirements
- Detailed conversion process
- Configuration options
- Troubleshooting
- Performance expectations

## Model Location

All converted models are stored in:
```
py-tars/data/model_cache/embedder/
├── all-MiniLM-L6-v2.onnx  (~87MB)
└── all-MiniLM-L6-v2.rknn  (~45MB)
```

This location:
- ✅ Consistent with other models (wake word, whisper)
- ✅ Mounted as `/data/model_cache` in Docker containers
- ✅ Persists across container restarts
- ✅ Shared location for all embedding models

## Requirements

```bash
# For conversion (x86_64 or aarch64)
pip install rknn-toolkit2 sentence-transformers torch onnx onnxruntime

# For inference (RK3588 device only)
pip install rknn-toolkit-lite2
```

## Expected Performance

- **CPU**: ~150ms per query
- **NPU (FP16)**: ~40-60ms per query (3-4x faster)
- **Overall RAG**: 220ms → 110-130ms (2x speedup)

## Notes

- Models are exported with **fixed shapes** (batch=1, seq_len=256) for RKNN compatibility
- Currently using **FP16** precision (no int8 quantization) for simplicity
- **Tokenization** and **pooling** are done in Python; only BERT inference runs on NPU
- Scripts default to `data/model_cache/embedder/` for output paths
