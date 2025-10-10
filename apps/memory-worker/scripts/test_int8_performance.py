#!/usr/bin/env python3
"""
Quick performance test for INT8 RKNN reranker.

Compares INT8 vs FP16 performance using RKNN Lite2 directly.
"""

import time
import os
import sys
import numpy as np

try:
    from rknnlite.api import RKNNLite
except ImportError:
    print("ERROR: rknnlite not installed. This script must run on device with NPU.")
    sys.exit(1)

try:
    from transformers import AutoTokenizer
except ImportError:
    print("ERROR: transformers not installed")
    sys.exit(1)

def test_reranker(model_path: str, model_name: str, num_runs: int = 5):
    """Test reranker performance."""
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"Model: {model_path}")
    print(f"{'='*60}")
    
    # Check file size
    if os.path.exists(model_path):
        size_mb = os.path.getsize(model_path) / (1024 * 1024)
        print(f"Model size: {size_mb:.1f} MB")
    else:
        print(f"ERROR: Model not found: {model_path}")
        return None
    
    # Initialize RKNN
    print("Loading model...")
    rknn = RKNNLite()
    
    try:
        ret = rknn.load_rknn(model_path)
        if ret != 0:
            print(f"ERROR: Failed to load RKNN model (code: {ret})")
            return None
        
        ret = rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_0)
        if ret != 0:
            print(f"ERROR: Failed to init runtime (code: {ret})")
            return None
    except Exception as e:
        print(f"ERROR loading model: {e}")
        return None
    
    # Load tokenizer
    print("Loading tokenizer...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            "cross-encoder/ms-marco-MiniLM-L-12-v2",
            cache_dir="/data/model_cache"
        )
    except Exception as e:
        print(f"ERROR loading tokenizer: {e}")
        return None
    
    # Test data
    query = "What is the capital of France?"
    passages = [
        "Paris is the capital and most populous city of France.",
        "London is the capital of England and the United Kingdom.",
        "Berlin is the capital and largest city of Germany.",
        "Rome is the capital city of Italy.",
        "Madrid is the capital and most populous city of Spain.",
    ]
    
    print(f"\nRunning {num_runs} iterations with {len(passages)} passages...")
    
    times = []
    for i in range(num_runs):
        start = time.time()
        
        try:
            # Score each passage
            for passage in passages:
                # Tokenize
                inputs = tokenizer(
                    query,
                    passage,
                    padding='max_length',
                    truncation=True,
                    max_length=512,
                    return_tensors='np'
                )
                
                # Run inference
                outputs = rknn.inference(inputs=[
                    inputs['input_ids'].astype(np.int64),
                    inputs['attention_mask'].astype(np.int64),
                    inputs['token_type_ids'].astype(np.int64)
                ])
            
            elapsed = time.time() - start
            times.append(elapsed)
            
            print(f"  Run {i+1}: {elapsed*1000:.1f}ms (avg per passage: {elapsed*1000/len(passages):.1f}ms)")
        except Exception as e:
            print(f"  Run {i+1}: ERROR - {e}")
            import traceback
            traceback.print_exc()
            return None
    
    # Cleanup
    rknn.release()
    
    # Calculate stats
    avg_total = sum(times) / len(times)
    avg_per_passage = avg_total / len(passages)
    
    print(f"\n{'='*60}")
    print(f"Results for {model_name}:")
    print(f"  Average total time: {avg_total*1000:.1f}ms")
    print(f"  Average per passage: {avg_per_passage*1000:.1f}ms")
    print(f"  Model size: {size_mb:.1f} MB")
    print(f"{'='*60}")
    
    return {
        'name': model_name,
        'avg_total_ms': avg_total * 1000,
        'avg_per_passage_ms': avg_per_passage * 1000,
        'size_mb': size_mb,
    }


def main():
    """Main test runner."""
    results = []
    
    # Test FP16 model
    fp16_path = "/data/model_cache/reranker/ms-marco-MiniLM-L-12-v2.rknn"
    fp16_result = test_reranker(fp16_path, "NPU FP16", num_runs=5)
    if fp16_result:
        results.append(fp16_result)
    
    # Test INT8 model
    int8_path = "/data/model_cache/reranker/ms-marco-MiniLM-L-12-v2_int8.rknn"
    int8_result = test_reranker(int8_path, "NPU INT8", num_runs=5)
    if int8_result:
        results.append(int8_result)
    
    # Summary comparison
    if len(results) >= 2:
        print(f"\n{'='*60}")
        print("PERFORMANCE COMPARISON")
        print(f"{'='*60}")
        print(f"{'Configuration':<20} {'Size':<12} {'Per-Passage':<15} {'5 Passages'}")
        print(f"{'-'*60}")
        
        for r in results:
            total_5 = r['avg_per_passage_ms'] * 5
            print(f"{r['name']:<20} {r['size_mb']:>6.1f} MB   {r['avg_per_passage_ms']:>7.1f}ms      {total_5:>7.1f}ms")
        
        # CPU baseline for reference
        print(f"{'CPU (flashrank INT8)':<20} {'32.0 MB':>9}   {'85.0ms':>10}      {'449ms':>10}")
        
        if int8_result and fp16_result:
            speedup = fp16_result['avg_per_passage_ms'] / int8_result['avg_per_passage_ms']
            compression = fp16_result['size_mb'] / int8_result['size_mb']
            print(f"\n{'-'*60}")
            print(f"INT8 vs FP16:")
            print(f"  Speedup: {speedup:.2f}x faster")
            print(f"  Compression: {compression:.2f}x smaller")
            
            if int8_result['avg_per_passage_ms'] <= 100:
                print(f"\n✓ INT8 NPU is viable for production (≤100ms target)")
            else:
                print(f"\n⚠️  INT8 NPU still slower than target (<100ms)")
                print(f"   Recommendation: Use CPU reranker (85ms)")
        
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
