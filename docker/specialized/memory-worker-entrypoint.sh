#!/bin/bash
set -e

echo "=========================================="
echo "Memory Worker Startup"
echo "=========================================="

# Check if NPU embedder is enabled
if [ "${NPU_EMBEDDER_ENABLED:-0}" = "1" ]; then
    echo "✓ NPU embedder enabled"
    
    # Set defaults
    MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-/data/model_cache}"
    EMBED_MODEL="${EMBED_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"
    RKNN_MODEL_PATH="${RKNN_EMBEDDER_PATH:-$MODEL_CACHE_DIR/embedder/all-MiniLM-L6-v2.rknn}"
    ONNX_MODEL_PATH="${MODEL_CACHE_DIR}/embedder/all-MiniLM-L6-v2.onnx"
    
    echo "  Model cache: $MODEL_CACHE_DIR"
    echo "  RKNN model path: $RKNN_MODEL_PATH"
    
    # Check if RKNN model already exists
    if [ -f "$RKNN_MODEL_PATH" ]; then
        echo "✓ RKNN model already exists: $RKNN_MODEL_PATH"
        RKNN_SIZE=$(du -h "$RKNN_MODEL_PATH" | cut -f1)
        echo "  Size: $RKNN_SIZE"
    else
        echo "⚠ RKNN model not found, will create it now..."
        
        # Ensure model cache directory exists and is writable
        mkdir -p "$MODEL_CACHE_DIR/embedder"
        
        if [ ! -w "$MODEL_CACHE_DIR/embedder" ]; then
            echo "❌ ERROR: $MODEL_CACHE_DIR/embedder is not writable!"
            echo "   Please check volume mount permissions"
            exit 1
        fi
        
        echo "✓ Model cache directory is writable"
        
        # Step 1: Convert to ONNX if not exists
        if [ ! -f "$ONNX_MODEL_PATH" ]; then
            echo ""
            echo "Step 1/2: Converting SentenceTransformer to ONNX..."
            echo "  Model: $EMBED_MODEL"
            echo "  Output: $ONNX_MODEL_PATH"
            
            cd /app/scripts
            python convert_st_to_onnx.py \
                --model "$EMBED_MODEL" \
                --output "$ONNX_MODEL_PATH" \
                --max-seq-length 256
            
            if [ $? -eq 0 ] && [ -f "$ONNX_MODEL_PATH" ]; then
                ONNX_SIZE=$(du -h "$ONNX_MODEL_PATH" | cut -f1)
                echo "✓ ONNX conversion successful: $ONNX_SIZE"
            else
                echo "❌ ONNX conversion failed!"
                exit 1
            fi
        else
            echo "✓ ONNX model already exists: $ONNX_MODEL_PATH"
        fi
        
        # Step 2: Convert ONNX to RKNN
        echo ""
        echo "Step 2/2: Converting ONNX to RKNN..."
        echo "  Input: $ONNX_MODEL_PATH"
        echo "  Output: $RKNN_MODEL_PATH"
        
        cd /app/scripts
        python convert_onnx_to_rknn.py \
            "$ONNX_MODEL_PATH" \
            "$RKNN_MODEL_PATH"
        
        if [ $? -eq 0 ] && [ -f "$RKNN_MODEL_PATH" ]; then
            RKNN_SIZE=$(du -h "$RKNN_MODEL_PATH" | cut -f1)
            echo "✓ RKNN conversion successful: $RKNN_SIZE"
            echo ""
            echo "=========================================="
            echo "✓ NPU models ready!"
            echo "=========================================="
        else
            echo "❌ RKNN conversion failed!"
            exit 1
        fi
    fi
    
    # Verify NPU device is available
    if [ -e "/dev/dri/renderD129" ]; then
        echo "✓ NPU device found: /dev/dri/renderD129"
    else
        echo "⚠ NPU device not found: /dev/dri/renderD129"
        if [ "${NPU_FALLBACK_CPU:-1}" = "1" ]; then
            echo "  Will fall back to CPU embedder"
        else
            echo "  CPU fallback disabled - service may fail"
        fi
    fi
else
    echo "ℹ NPU embedder disabled (using CPU)"
fi

# Check if NPU reranker is enabled
if [ "${NPU_RERANKER_ENABLED:-0}" = "1" ]; then
    echo ""
    echo "=========================================="
    echo "NPU Reranker Setup"
    echo "=========================================="
    
    # Set defaults
    MODEL_CACHE_DIR="${MODEL_CACHE_DIR:-/data/model_cache}"
    FLASHRANK_CACHE="${FLASHRANK_CACHE:-/data/flashrank_cache}"
    RERANK_MODEL="${RERANK_MODEL:-ms-marco-MiniLM-L-12-v2}"
    RKNN_RERANKER_PATH="${MODEL_CACHE_DIR}/reranker/${RERANK_MODEL}.rknn"
    FLASHRANK_ONNX="${FLASHRANK_CACHE}/${RERANK_MODEL}/flashrank-MiniLM-L-12-v2_Q.onnx"
    
    echo "✓ NPU reranker enabled"
    echo "  Model: $RERANK_MODEL"
    echo "  RKNN path: $RKNN_RERANKER_PATH"
    
    # Check if RKNN reranker already exists
    if [ -f "$RKNN_RERANKER_PATH" ]; then
        echo "✓ RKNN reranker already exists"
        RKNN_SIZE=$(du -h "$RKNN_RERANKER_PATH" | cut -f1)
        echo "  Size: $RKNN_SIZE"
    else
        echo "⚠ RKNN reranker not found, will create it now..."
        
        # Check if flashrank ONNX exists
        if [ ! -f "$FLASHRANK_ONNX" ]; then
            echo "⚠ Flashrank ONNX not found: $FLASHRANK_ONNX"
            echo "  Flashrank needs to download the model first"
            echo "  This happens automatically on first use"
            echo "  Skipping NPU reranker conversion for now"
        else
            # Ensure reranker cache directory exists
            mkdir -p "$MODEL_CACHE_DIR/reranker"
            
            if [ ! -w "$MODEL_CACHE_DIR/reranker" ]; then
                echo "❌ ERROR: $MODEL_CACHE_DIR/reranker is not writable!"
                echo "   Please check volume mount permissions"
                exit 1
            fi
            
            echo "✓ Reranker cache directory is writable"
            echo ""
            echo "Converting flashrank ONNX to RKNN..."
            echo "  Input: $FLASHRANK_ONNX"
            echo "  Output: $RKNN_RERANKER_PATH"
            
            # Run conversion
            cd /app/scripts
            FLASHRANK_CACHE="$FLASHRANK_CACHE" \
            MODEL_CACHE="$MODEL_CACHE_DIR" \
            python convert_reranker_to_rknn.py
            
            if [ $? -eq 0 ] && [ -f "$RKNN_RERANKER_PATH" ]; then
                RKNN_SIZE=$(du -h "$RKNN_RERANKER_PATH" | cut -f1)
                echo "✓ RKNN reranker conversion successful: $RKNN_SIZE"
            else
                echo "❌ RKNN reranker conversion failed!"
                if [ "${NPU_RERANKER_FALLBACK_CPU:-1}" = "1" ]; then
                    echo "  Will fall back to CPU reranker"
                else
                    exit 1
                fi
            fi
        fi
    fi
    
    # Verify NPU device is available
    if [ -e "/dev/rknpu" ]; then
        echo "✓ NPU device found: /dev/rknpu"
    else
        echo "⚠ NPU device not found: /dev/rknpu"
        if [ "${NPU_RERANKER_FALLBACK_CPU:-1}" = "1" ]; then
            echo "  Will fall back to CPU reranker"
        else
            echo "  CPU fallback disabled - service may fail"
        fi
    fi
else
    echo "ℹ NPU reranker disabled (using CPU flashrank)"
fi

echo ""
echo "Starting memory worker..."
echo "=========================================="
echo ""

# Execute the main command
exec "$@"
