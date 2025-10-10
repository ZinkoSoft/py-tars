#!/usr/bin/env python3
"""
Benchmark INT8 vs FP16 RKNN reranker models.

Direct RKNN inference test without heavy dependencies.
"""

import time
import os
import sys
import numpy as np

print("Loading RKNN Lite API...")
try:
    from rknnlite.api import RKNNLite
except ImportError:
    print("ERROR: rknnlite not available. Must run on NPU device.")
    sys.exit(1)

def create_dummy_inputs():
    """
    Create dummy tokenized inputs matching the expected format.
    
    Model expects:
    - input_ids: [1, 512] INT64
    - attention_mask: [1, 512] INT64  
    - token_type_ids: [1, 512] INT64
    """
    batch_size = 1
    seq_length = 512
    
    # Create realistic dummy data
    input_ids = np.zeros((batch_size, seq_length), dtype=np.int64)
    # Query: first 20 tokens
    input_ids[0, :20] = np.random.randint(1000, 5000, size=20)
    # SEP
    input_ids[0, 20] = 102
    # Passage: next 100 tokens
    input_ids[0, 21:121] = np.random.randint(1000, 10000, size=100)
    # SEP
    input_ids[0, 121] = 102
    
    # Attention mask: 1 for real tokens, 0 for padding
    attention_mask = np.zeros((batch_size, seq_length), dtype=np.int64)
    attention_mask[0, :122] = 1
    
    # Token type IDs: 0 for query, 1 for passage
    token_type_ids = np.zeros((batch_size, seq_length), dtype=np.int64)
    token_type_ids[0, 21:122] = 1
    
    return input_ids, attention_mask, token_type_ids


def benchmark_model(model_path: str, model_name: str, num_passages: int = 5, num_runs: int = 5):
    """Benchmark a single RKNN model."""
    print(f"\n{'='*70}")
    print(f"Testing: {model_name}")
    print(f"Model: {model_path}")
    print(f"{'='*70}")
    
    # Check file exists and get size
    if not os.path.exists(model_path):
        print(f"ERROR: Model not found: {model_path}")
        return None
    
    size_mb = os.path.getsize(model_path) / (1024 * 1024)
    print(f"Model size: {size_mb:.1f} MB")
    
    # Initialize RKNN
    print("Loading RKNN model...")
    rknn = RKNNLite()
    
    try:
        ret = rknn.load_rknn(model_path)
        if ret != 0:
            print(f"ERROR: Failed to load RKNN model (ret={ret})")
            return None
        
        ret = rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_0)
        if ret != 0:
            print(f"ERROR: Failed to init runtime (ret={ret})")
            return None
        
        print("✓ Model loaded successfully")
    except Exception as e:
        print(f"ERROR: {e}")
        return None
    
    # Create dummy inputs
    input_ids, attention_mask, token_type_ids = create_dummy_inputs()
    
    # Warmup run
    print("Warming up...")
    try:
        _ = rknn.inference(inputs=[input_ids, attention_mask, token_type_ids])
        print("✓ Warmup complete")
    except Exception as e:
        print(f"ERROR during warmup: {e}")
        rknn.release()
        return None
    
    # Benchmark runs
    print(f"\nBenchmarking {num_runs} runs with {num_passages} passages each...")
    
    run_times = []
    for run in range(num_runs):
        passage_times = []
        
        run_start = time.time()
        for passage_idx in range(num_passages):
            passage_start = time.time()
            
            try:
                outputs = rknn.inference(inputs=[input_ids, attention_mask, token_type_ids])
                passage_elapsed = time.time() - passage_start
                passage_times.append(passage_elapsed)
            except Exception as e:
                print(f"ERROR in run {run+1}, passage {passage_idx+1}: {e}")
                rknn.release()
                return None
        
        run_elapsed = time.time() - run_start
        run_times.append(run_elapsed)
        
        avg_per_passage = run_elapsed / num_passages
        print(f"  Run {run+1}: {run_elapsed*1000:.1f}ms total, {avg_per_passage*1000:.1f}ms per passage")
    
    # Cleanup
    rknn.release()
    
    # Calculate statistics
    avg_total = sum(run_times) / len(run_times)
    min_total = min(run_times)
    max_total = max(run_times)
    avg_per_passage = avg_total / num_passages
    
    print(f"\n{'='*70}")
    print(f"Results for {model_name}:")
    print(f"  Total time (avg):     {avg_total*1000:.1f}ms (min: {min_total*1000:.1f}ms, max: {max_total*1000:.1f}ms)")
    print(f"  Per passage (avg):    {avg_per_passage*1000:.1f}ms")
    print(f"  {num_passages} passages:          {avg_total*1000:.1f}ms")
    print(f"  Model size:           {size_mb:.1f} MB")
    print(f"{'='*70}")
    
    return {
        'name': model_name,
        'size_mb': size_mb,
        'avg_total_ms': avg_total * 1000,
        'avg_per_passage_ms': avg_per_passage * 1000,
        'min_total_ms': min_total * 1000,
        'max_total_ms': max_total * 1000,
    }


def main():
    """Main benchmark runner."""
    print("\n" + "="*70)
    print("NPU RERANKER BENCHMARK - INT8 vs FP16")
    print("="*70)
    
    num_passages = 5
    num_runs = 5
    
    results = []
    
    # Test FP16 model
    fp16_path = "/data/model_cache/reranker/ms-marco-MiniLM-L-12-v2.rknn"
    if os.path.exists(fp16_path):
        fp16_result = benchmark_model(fp16_path, "NPU FP16", num_passages, num_runs)
        if fp16_result:
            results.append(fp16_result)
    else:
        print(f"\n⚠️  FP16 model not found: {fp16_path}")
    
    # Test INT8 model
    int8_path = "/data/model_cache/reranker/ms-marco-MiniLM-L-12-v2_int8.rknn"
    if os.path.exists(int8_path):
        int8_result = benchmark_model(int8_path, "NPU INT8", num_passages, num_runs)
        if int8_result:
            results.append(int8_result)
    else:
        print(f"\n⚠️  INT8 model not found: {int8_path}")
    
    # Summary comparison
    if len(results) >= 2:
        print(f"\n{'='*70}")
        print("PERFORMANCE COMPARISON")
        print(f"{'='*70}")
        print(f"{'Configuration':<15} {'Size':<12} {'Per-Passage':<15} {'5 Passages':<15} {'Speedup'}")
        print(f"{'-'*70}")
        
        for i, r in enumerate(results):
            total_5 = r['avg_per_passage_ms'] * 5
            speedup = ""
            if i > 0:
                baseline = results[0]['avg_per_passage_ms']
                speedup_factor = baseline / r['avg_per_passage_ms']
                speedup = f"{speedup_factor:.2f}x"
            
            print(f"{r['name']:<15} {r['size_mb']:>6.1f} MB   {r['avg_per_passage_ms']:>7.1f}ms      {total_5:>7.1f}ms      {speedup}")
        
        # CPU baseline for reference
        print(f"{'CPU INT8':<15} {'32.0 MB':>9}   {'85.0ms':>10}      {'425ms':>10}      {'(baseline)'}")
        
        # Analysis
        if len(results) == 2:
            fp16_r = results[0]
            int8_r = results[1]
            
            speedup = fp16_r['avg_per_passage_ms'] / int8_r['avg_per_passage_ms']
            compression = fp16_r['size_mb'] / int8_r['size_mb']
            
            print(f"\n{'-'*70}")
            print(f"INT8 vs FP16 Analysis:")
            print(f"  Speedup:      {speedup:.2f}x faster")
            print(f"  Compression:  {compression:.2f}x smaller")
            
            # Compare to CPU
            cpu_per_passage = 85.0  # ms
            int8_vs_cpu = int8_r['avg_per_passage_ms'] / cpu_per_passage
            
            print(f"\nINT8 vs CPU Analysis:")
            print(f"  NPU INT8:     {int8_r['avg_per_passage_ms']:.1f}ms per passage")
            print(f"  CPU INT8:     {cpu_per_passage:.1f}ms per passage")
            print(f"  Ratio:        {int8_vs_cpu:.2f}x ({'slower' if int8_vs_cpu > 1 else 'faster'} than CPU)")
            
            print(f"\n{'-'*70}")
            print("RECOMMENDATION:")
            if int8_r['avg_per_passage_ms'] <= 100:
                print("✓ NPU INT8 is viable for production (≤100ms target)")
                print("  → Enable: NPU_RERANK_ENABLED=1")
                print("  → Model:  NPU_RERANK_MODEL=/data/model_cache/reranker/ms-marco-MiniLM-L-12-v2_int8.rknn")
            else:
                print("⚠️  NPU INT8 still slower than target (<100ms)")
                print(f"  → Current: {int8_r['avg_per_passage_ms']:.1f}ms per passage")
                print("  → Recommendation: Keep CPU reranker (85ms)")
                print("  → Keep NPU embedder only (proven 3.8x speedup)")
        
        print(f"{'='*70}\n")
    
    elif len(results) == 1:
        print(f"\n⚠️  Only one model tested. Need both FP16 and INT8 for comparison.")
    else:
        print(f"\n❌ No models could be tested.")


if __name__ == "__main__":
    main()
