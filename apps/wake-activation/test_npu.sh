#!/bin/bash
set -e

echo "=== Building and Testing NPU Wake Activation ==="

# Check if RKNN model exists
if [ ! -f "../../models/openwakeword/hey_tars.rknn" ]; then
    echo "❌ RKNN model not found. Please run the conversion script first:"
    echo "    python scripts/convert_tflite_to_rknn.py ../../models/openwakeword/hey_tars.onnx ../../models/openwakeword/hey_tars.rknn"
    exit 1
fi

echo "✅ RKNN model found"

# Build the NPU-enabled container
echo "Building NPU wake activation container..."
docker compose -f compose.npu.yml build wake-activation-npu

# Test NPU functionality in container
echo "Testing NPU functionality..."
docker compose -f compose.npu.yml run --rm wake-activation-npu python scripts/test_npu_docker.py

echo "🎉 NPU wake activation test completed!"
echo ""
echo "To run the wake activation service with NPU:"
echo "    docker compose -f compose.npu.yml up wake-activation-npu"
echo ""
echo "To run with CPU fallback:"
echo "    docker compose -f compose.npu.yml --profile cpu-fallback up wake-activation-cpu"