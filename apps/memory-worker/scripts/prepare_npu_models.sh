#!/bin/bash
set -e

# NPU Embedder Model Preparation Script
# This script is run during Docker build to prepare NPU models if enabled

echo "=========================================="
echo "NPU Embedder Model Preparation"
echo "=========================================="

# Check if NPU is enabled
if [ "${NPU_EMBEDDER_ENABLED}" != "1" ]; then
    echo "NPU embedder not enabled (NPU_EMBEDDER_ENABLED != 1)"
    echo "Skipping NPU model conversion"
    exit 0
fi

echo "NPU embedder enabled - preparing models..."

# Set paths
MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-/data/model_cache}"
EMBEDDER_DIR="${MODEL_CACHE_DIR}/embedder"
MODEL_NAME="${EMBED_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"
MODEL_BASENAME="all-MiniLM-L6-v2"
ONNX_PATH="${EMBEDDER_DIR}/${MODEL_BASENAME}.onnx"
RKNN_PATH="${EMBEDDER_DIR}/${MODEL_BASENAME}.rknn"

# Create directory
mkdir -p "${EMBEDDER_DIR}"

echo "Model cache directory: ${EMBEDDER_DIR}"
echo "Base model: ${MODEL_NAME}"

# Check if RKNN model already exists
if [ -f "${RKNN_PATH}" ]; then
    echo "✅ RKNN model already exists: ${RKNN_PATH}"
    echo "   Size: $(du -h ${RKNN_PATH} | cut -f1)"
    exit 0
fi

# Check if ONNX model exists
if [ ! -f "${ONNX_PATH}" ]; then
    echo "Step 1/2: Converting to ONNX..."
    python /app/scripts/convert_st_to_onnx.py \
        --model "${MODEL_NAME}" \
        --output "${ONNX_PATH}" \
        --max-seq-length 256
    
    if [ $? -eq 0 ]; then
        echo "✅ ONNX conversion successful"
    else
        echo "❌ ONNX conversion failed"
        exit 1
    fi
else
    echo "✅ ONNX model already exists: ${ONNX_PATH}"
fi

# Convert to RKNN
echo "Step 2/2: Converting to RKNN..."
python /app/scripts/convert_onnx_to_rknn.py \
    "${ONNX_PATH}" \
    "${RKNN_PATH}" \
    --target "${NPU_TARGET_PLATFORM:-rk3588}"

if [ $? -eq 0 ]; then
    echo "✅ RKNN conversion successful"
    echo "   ONNX: $(du -h ${ONNX_PATH} | cut -f1)"
    echo "   RKNN: $(du -h ${RKNN_PATH} | cut -f1)"
else
    echo "❌ RKNN conversion failed"
    exit 1
fi

echo "=========================================="
echo "NPU embedder models ready!"
echo "=========================================="
