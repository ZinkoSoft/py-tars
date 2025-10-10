#!/bin/bash
set -e

echo "=========================================="
echo "Testing INT8 vs FP16 Reranker Conversion"
echo "=========================================="
echo

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

MODEL_DIR="/data/model_cache/reranker"

# Check if FP16 model exists
if [ ! -f "$MODEL_DIR/ms-marco-MiniLM-L-12-v2.rknn" ]; then
    echo -e "${YELLOW}⚠️  FP16 model not found. Converting with FP16 first...${NC}"
    python convert_reranker_to_rknn.py
    echo
fi

# Get FP16 model size
FP16_SIZE=$(du -h "$MODEL_DIR/ms-marco-MiniLM-L-12-v2.rknn" | cut -f1)
echo -e "${GREEN}✓ FP16 model exists: $FP16_SIZE${NC}"
echo

# Check if INT8 model exists
INT8_MODEL="$MODEL_DIR/ms-marco-MiniLM-L-12-v2_int8.rknn"
if [ -f "$INT8_MODEL" ]; then
    echo -e "${YELLOW}⚠️  INT8 model already exists. Remove it to reconvert.${NC}"
    INT8_SIZE=$(du -h "$INT8_MODEL" | cut -f1)
    echo -e "   Current INT8 size: $INT8_SIZE"
    echo
else
    echo -e "${YELLOW}→ Converting with INT8 quantization...${NC}"
    echo "   This will generate 100 calibration samples and may take 5-10 minutes"
    echo
    
    # Convert with INT8
    QUANTIZE=1 CALIBRATION_SAMPLES=100 python convert_reranker_to_rknn.py
    
    if [ -f "$INT8_MODEL" ]; then
        INT8_SIZE=$(du -h "$INT8_MODEL" | cut -f1)
        echo
        echo -e "${GREEN}✓ INT8 conversion successful!${NC}"
        echo
    else
        echo -e "${RED}✗ INT8 conversion failed${NC}"
        exit 1
    fi
fi

# Compare sizes
echo "=========================================="
echo "Model Size Comparison"
echo "=========================================="
echo "FP16: $FP16_SIZE"
echo "INT8: $INT8_SIZE"
echo
FP16_BYTES=$(stat -c%s "$MODEL_DIR/ms-marco-MiniLM-L-12-v2.rknn")
INT8_BYTES=$(stat -c%s "$INT8_MODEL")
RATIO=$(echo "scale=2; $FP16_BYTES / $INT8_BYTES" | bc)
echo "Compression ratio: ${RATIO}x smaller"
echo

echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo "1. Update memory-worker to use INT8 model:"
echo "   NPU_RERANK_MODEL=$INT8_MODEL"
echo
echo "2. Test performance with test_reranker_npu.py"
echo
echo "3. Compare results:"
echo "   - CPU (flashrank): 80-90ms per passage"
echo "   - NPU FP16: 185ms per passage"
echo "   - NPU INT8: ? (test needed)"
echo
