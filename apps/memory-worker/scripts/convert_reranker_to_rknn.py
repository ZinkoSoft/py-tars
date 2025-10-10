#!/usr/bin/env python3
"""
Convert Reranker Model to RKNN Format for NPU Acceleration

This script converts the ms-marco-MiniLM-L-12-v2 reranker model to RKNN format
for running on the RK3588 NPU.

Process:
1. Export model to ONNX with fixed shapes
2. (Optional) Generate calibration dataset for INT8 quantization
3. Convert ONNX to RKNN format (FP16 or INT8)
4. Validate conversion

Environment Variables:
    SKIP_EXPORT: Skip ONNX export step if model already exists (default: 0)
    SKIP_CONVERSION: Skip RKNN conversion if model already exists (default: 0)
    SKIP_VALIDATION: Skip validation step (default: 0)
    QUANTIZE: Enable INT8 quantization (default: 0, uses FP16)
    CALIBRATION_SAMPLES: Number of calibration samples to generate (default: 100)
    REGENERATE_DATASET: Force regeneration of calibration dataset (default: 0)

Examples:
    # Convert with FP16 (default):
    python convert_reranker_to_rknn.py
    
    # Convert with INT8 quantization:
    QUANTIZE=1 python convert_reranker_to_rknn.py
    
    # INT8 with more calibration samples:
    QUANTIZE=1 CALIBRATION_SAMPLES=200 python convert_reranker_to_rknn.py
    
Expected Results:
    FP16: ~69 MB model, 185ms per passage (2x slower than CPU)
    INT8: ~17-35 MB model, potentially matching CPU's 80-90ms per passage
"""

import os
import sys
import logging
from pathlib import Path

import onnx
from onnx import helper, TensorProto
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fix_onnx_shapes(input_path: str, output_path: str, batch_size: int = 1, seq_length: int = 512):
    """
    Fix dynamic shapes in ONNX model to static shapes for RKNN.
    
    Args:
        input_path: Path to input ONNX model with dynamic shapes
        output_path: Path to save fixed ONNX model
        batch_size: Fixed batch size (default: 1)
        seq_length: Fixed sequence length (default: 512)
    """
    logger.info(f"Loading ONNX model: {input_path}")
    model = onnx.load(input_path)
    
    # Get model info
    logger.info(f"Model IR version: {model.ir_version}")
    logger.info(f"Producer: {model.producer_name}")
    
    # Fix input shapes
    logger.info(f"Fixing input shapes to [{batch_size}, {seq_length}]")
    
    for input_tensor in model.graph.input:
        # Expected inputs: input_ids, attention_mask, token_type_ids
        logger.info(f"  Input: {input_tensor.name}")
        
        # Get current shape
        dims = input_tensor.type.tensor_type.shape.dim
        current_shape = [d.dim_value if d.dim_value > 0 else d.dim_param for d in dims]
        logger.info(f"    Current shape: {current_shape}")
        
        # Clear existing dimensions and create new ones
        del dims[:]
        
        # Add new fixed dimensions
        dims.add().dim_value = batch_size
        dims.add().dim_value = seq_length
        
        logger.info(f"    New shape: [{batch_size}, {seq_length}]")
    
    # Fix output shapes
    logger.info("Fixing output shapes")
    for output_tensor in model.graph.output:
        logger.info(f"  Output: {output_tensor.name}")
        
        dims = output_tensor.type.tensor_type.shape.dim
        current_shape = [d.dim_value if d.dim_value > 0 else d.dim_param for d in dims]
        logger.info(f"    Current shape: {current_shape}")
        
        # Output should be [batch_size, 1] for single score
        # Clear existing dimensions and create new ones
        del dims[:]
        
        # Add new fixed dimensions
        dims.add().dim_value = batch_size
        dims.add().dim_value = 1  # Single score output
        
        new_shape = [d.dim_value for d in dims]
        logger.info(f"    New shape: {new_shape}")
    
    # Check and save
    logger.info("Checking fixed model")
    onnx.checker.check_model(model)
    
    logger.info(f"Saving fixed ONNX model: {output_path}")
    onnx.save(model, output_path)
    
    return output_path


def generate_calibration_dataset(output_dir: str, num_samples: int = 100):
    """
    Generate calibration dataset for INT8 quantization.
    
    Creates realistic input samples (tokenized query+passage pairs) for calibration.
    
    Args:
        output_dir: Directory to save calibration samples
        num_samples: Number of calibration samples to generate
    
    Returns:
        Path to calibration dataset file
    """
    import numpy as np
    
    os.makedirs(output_dir, exist_ok=True)
    dataset_file = f"{output_dir}/calibration_dataset.txt"
    
    logger.info(f"Generating {num_samples} calibration samples...")
    logger.info(f"Dataset will be saved to: {dataset_file}")
    
    # Generate samples with varied token patterns
    samples = []
    batch_size, seq_length = 1, 512
    vocab_size = 30522  # BERT vocab size
    
    for i in range(num_samples):
        # Create realistic token distributions
        # Most tokens in 0-10000 range (common words)
        # Some special tokens (0-100)
        # Occasional rare tokens (10000-30522)
        
        input_ids = np.zeros((batch_size, seq_length), dtype=np.int64)
        
        # Generate query tokens (first ~20 tokens)
        query_len = np.random.randint(5, 25)
        input_ids[0, :query_len] = np.random.randint(100, 5000, size=query_len)
        
        # SEP token
        input_ids[0, query_len] = 102
        
        # Generate passage tokens (remaining tokens up to random length)
        passage_len = np.random.randint(50, seq_length - query_len - 10)
        input_ids[0, query_len+1:query_len+1+passage_len] = np.random.randint(100, 10000, size=passage_len)
        
        # SEP token at end
        input_ids[0, query_len+1+passage_len] = 102
        
        # Attention mask: 1 for real tokens, 0 for padding
        attention_mask = np.zeros((batch_size, seq_length), dtype=np.int64)
        attention_mask[0, :query_len+1+passage_len+1] = 1
        
        # Token type ids: 0 for query, 1 for passage
        token_type_ids = np.zeros((batch_size, seq_length), dtype=np.int64)
        token_type_ids[0, query_len+1:query_len+1+passage_len+1] = 1
        
        samples.append({
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'token_type_ids': token_type_ids
        })
    
    # Save as numpy arrays
    logger.info(f"Saving calibration samples...")
    with open(dataset_file, 'w') as f:
        for i, sample in enumerate(samples):
            # RKNN expects one line per sample with paths to npy files
            sample_dir = f"{output_dir}/sample_{i:04d}"
            os.makedirs(sample_dir, exist_ok=True)
            
            np.save(f"{sample_dir}/input_ids.npy", sample['input_ids'])
            np.save(f"{sample_dir}/attention_mask.npy", sample['attention_mask'])
            np.save(f"{sample_dir}/token_type_ids.npy", sample['token_type_ids'])
            
            # Write paths to dataset file
            f.write(f"{sample_dir}/input_ids.npy {sample_dir}/attention_mask.npy {sample_dir}/token_type_ids.npy\n")
    
    logger.info(f"✓ Generated {num_samples} calibration samples")
    return dataset_file


def convert_to_rknn(onnx_path: str, rknn_path: str, do_quantization: bool = False, dataset_path: str = None):
    """
    Convert ONNX model to RKNN format for NPU.
    
    Args:
        onnx_path: Path to ONNX model (with fixed shapes)
        rknn_path: Path to save RKNN model
        do_quantization: Whether to quantize to INT8 (default: False, use FP16)
        dataset_path: Path to calibration dataset file (required if do_quantization=True)
    """
    try:
        from rknn.api import RKNN
    except ImportError:
        logger.error("rknn-toolkit2 not installed. Install with: pip install rknn-toolkit2")
        sys.exit(1)
    
    if do_quantization and not dataset_path:
        logger.error("Calibration dataset required for INT8 quantization")
        logger.error("Set GENERATE_DATASET=1 to auto-generate or provide dataset path")
        sys.exit(1)
    
    logger.info("Initializing RKNN converter")
    rknn = RKNN(verbose=True)
    
    # Configure for RK3588
    logger.info("Configuring RKNN for RK3588")
    ret = rknn.config(
        target_platform='rk3588',
        optimization_level=3,
        quantized_algorithm='normal',
        quantized_method='channel',
    )
    if ret != 0:
        logger.error(f"RKNN config failed with code: {ret}")
        sys.exit(1)
    
    # Load ONNX with explicit input shapes
    logger.info(f"Loading ONNX model: {onnx_path}")
    logger.info("Setting input_size_list to [[1, 512], [1, 512], [1, 512]]")
    ret = rknn.load_onnx(
        model=onnx_path,
        input_size_list=[[1, 512], [1, 512], [1, 512]]  # input_ids, attention_mask, token_type_ids
    )
    if ret != 0:
        logger.error(f"Failed to load ONNX model, code: {ret}")
        sys.exit(1)
    
    # Build RKNN model
    logger.info("Building RKNN model (this may take several minutes)...")
    if do_quantization:
        logger.info(f"Quantization: INT8 (using calibration dataset: {dataset_path})")
        logger.info("Note: INT8 quantization will reduce model size and may improve performance")
    else:
        logger.info("Quantization: disabled (FP16)")
    
    try:
        ret = rknn.build(do_quantization=do_quantization, dataset=dataset_path if do_quantization else None)
        if ret != 0:
            logger.error(f"RKNN build failed with code: {ret}")
            logger.error("This may be due to unsupported ONNX ops or quantization issues")
            if do_quantization:
                logger.error("Try without quantization: set QUANTIZE=0")
            sys.exit(1)
    except Exception as e:
        logger.error(f"RKNN build exception: {e}", exc_info=True)
        sys.exit(1)
    
    # Export RKNN
    logger.info(f"Exporting RKNN model: {rknn_path}")
    ret = rknn.export_rknn(rknn_path)
    if ret != 0:
        logger.error(f"RKNN export failed with code: {ret}")
        sys.exit(1)
    
    # Get model size
    rknn_size_mb = os.path.getsize(rknn_path) / (1024 * 1024)
    logger.info(f"✓ RKNN model created: {rknn_size_mb:.1f} MB")
    
    # Cleanup
    rknn.release()
    
    return rknn_path


def validate_conversion(onnx_path: str, rknn_path: str):
    """
    Validate RKNN conversion by comparing outputs with ONNX.
    
    Args:
        onnx_path: Path to original ONNX model
        rknn_path: Path to converted RKNN model
    """
    logger.info("Validating RKNN conversion")
    
    try:
        import onnxruntime as ort
        from rknn.api import RKNN
    except ImportError as e:
        logger.warning(f"Validation skipped: {e}")
        return
    
    # Create test input
    batch_size, seq_length = 1, 512
    input_ids = np.random.randint(0, 30522, size=(batch_size, seq_length), dtype=np.int64)
    attention_mask = np.ones((batch_size, seq_length), dtype=np.int64)
    token_type_ids = np.zeros((batch_size, seq_length), dtype=np.int64)
    
    logger.info(f"Test input shape: {input_ids.shape}")
    
    # ONNX inference
    logger.info("Running ONNX inference")
    ort_session = ort.InferenceSession(onnx_path)
    onnx_inputs = {
        'input_ids': input_ids,
        'attention_mask': attention_mask,
        'token_type_ids': token_type_ids
    }
    onnx_output = ort_session.run(None, onnx_inputs)[0]
    logger.info(f"ONNX output shape: {onnx_output.shape}")
    logger.info(f"ONNX output value: {onnx_output[0][0]:.6f}")
    
    # RKNN inference
    logger.info("Running RKNN inference")
    rknn = RKNN()
    ret = rknn.load_rknn(rknn_path)
    if ret != 0:
        logger.error("Failed to load RKNN for validation")
        return
    
    ret = rknn.init_runtime()
    if ret != 0:
        logger.error("Failed to init RKNN runtime")
        rknn.release()
        return
    
    rknn_output = rknn.inference(inputs=[input_ids, attention_mask, token_type_ids])
    rknn.release()
    
    logger.info(f"RKNN output shape: {rknn_output[0].shape}")
    logger.info(f"RKNN output value: {rknn_output[0][0][0]:.6f}")
    
    # Compare outputs
    diff = np.abs(onnx_output[0][0] - rknn_output[0][0][0])
    logger.info(f"Output difference: {diff:.6f}")
    
    if diff < 0.1:
        logger.info("✓ Validation passed: outputs are similar")
    else:
        logger.warning(f"⚠ Validation warning: outputs differ by {diff:.6f}")


def export_reranker_to_onnx(output_path: str):
    """
    Export ms-marco reranker from Hugging Face to ONNX (FP32).
    
    The flashrank quantized model has DynamicQuantizeLinear ops that RKNN doesn't support.
    We need to export the original FP32 model instead.
    """
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch
    except ImportError:
        logger.error("transformers and torch required. Install with: pip install transformers torch")
        sys.exit(1)
    
    logger.info("Loading ms-marco-MiniLM-L-12-v2 from Hugging Face")
    model_name = "cross-encoder/ms-marco-MiniLM-L-12-v2"
    
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForSequenceClassification.from_pretrained(model_name)
    model.eval()
    
    logger.info("Model loaded successfully")
    logger.info(f"Model config: {model.config}")
    
    # Create dummy inputs for ONNX export
    batch_size, seq_length = 1, 512
    dummy_input_ids = torch.randint(0, tokenizer.vocab_size, (batch_size, seq_length))
    dummy_attention_mask = torch.ones(batch_size, seq_length, dtype=torch.long)
    dummy_token_type_ids = torch.zeros(batch_size, seq_length, dtype=torch.long)
    
    logger.info(f"Exporting to ONNX: {output_path}")
    logger.info(f"Input shapes: input_ids={dummy_input_ids.shape}, attention_mask={dummy_attention_mask.shape}, token_type_ids={dummy_token_type_ids.shape}")
    
    torch.onnx.export(
        model,
        (dummy_input_ids, dummy_attention_mask, dummy_token_type_ids),
        output_path,
        input_names=['input_ids', 'attention_mask', 'token_type_ids'],
        output_names=['logits'],
        dynamic_axes={
            'input_ids': {0: 'batch', 1: 'sequence'},
            'attention_mask': {0: 'batch', 1: 'sequence'},
            'token_type_ids': {0: 'batch', 1: 'sequence'},
            'logits': {0: 'batch'}
        },
        opset_version=13,
        do_constant_folding=True
    )
    
    # Get file size
    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"✓ ONNX export complete: {size_mb:.1f} MB")
    
    return output_path


def main():
    """Main conversion workflow."""
    # Paths
    flashrank_cache = os.getenv("FLASHRANK_CACHE", "/data/flashrank_cache")
    model_cache = os.getenv("MODEL_CACHE", "/data/model_cache")
    
    # Use original FP32 ONNX (not flashrank's quantized version)
    use_flashrank = os.getenv("USE_FLASHRANK_ONNX", "0") == "1"
    
    output_dir = f"{model_cache}/reranker"
    os.makedirs(output_dir, exist_ok=True)
    
    if use_flashrank:
        logger.info("Using flashrank quantized ONNX model")
        input_onnx = f"{flashrank_cache}/ms-marco-MiniLM-L-12-v2/flashrank-MiniLM-L-12-v2_Q.onnx"
    else:
        logger.info("Exporting FP32 ONNX from Hugging Face (flashrank quantized model incompatible)")
        input_onnx = f"{output_dir}/ms-marco-MiniLM-L-12-v2_fp32.onnx"
    
    fixed_onnx = f"{output_dir}/ms-marco-MiniLM-L-12-v2_fixed.onnx"
    
    # Check if quantization is enabled to determine output filename
    do_quantization = os.getenv("QUANTIZE", "0") == "1"
    rknn_suffix = "_int8" if do_quantization else ""
    rknn_model = f"{output_dir}/ms-marco-MiniLM-L-12-v2{rknn_suffix}.rknn"
    
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Quantization mode: {'INT8' if do_quantization else 'FP16'}")
    logger.info(f"Output model path: {rknn_model}")
    
    # Check if input exists or export it
    if not os.path.exists(input_onnx):
        if use_flashrank:
            logger.error(f"Flashrank ONNX model not found: {input_onnx}")
            logger.error("Please ensure flashrank has downloaded the model first")
            sys.exit(1)
        else:
            logger.info(f"FP32 ONNX not found, exporting from Hugging Face...")
            export_reranker_to_onnx(input_onnx)
    
    # Get input size
    input_size_mb = os.path.getsize(input_onnx) / (1024 * 1024)
    logger.info(f"Input ONNX size: {input_size_mb:.1f} MB")
    
    # Check if output already exists
    if os.path.exists(rknn_model):
        logger.info(f"RKNN model already exists: {rknn_model}")
        rknn_size_mb = os.path.getsize(rknn_model) / (1024 * 1024)
        logger.info(f"Existing RKNN size: {rknn_size_mb:.1f} MB")
        
        overwrite = os.getenv("FORCE_CONVERT", "0") == "1"
        if not overwrite:
            logger.info("Skipping conversion (set FORCE_CONVERT=1 to overwrite)")
            return
        
        logger.info("FORCE_CONVERT=1, overwriting existing model")
    
    # Quantization setup (already checked above for filename)
    dataset_path = None
    
    if do_quantization:
        logger.info("INT8 quantization enabled")
        logger.info(f"Output model: {rknn_model}")
        
        # Check if dataset exists or needs generation
        dataset_dir = f"{output_dir}/calibration_data"
        dataset_file = f"{dataset_dir}/calibration_dataset.txt"
        
        if not os.path.exists(dataset_file) or os.getenv("REGENERATE_DATASET", "0") == "1":
            logger.info("Generating calibration dataset...")
            num_samples = int(os.getenv("CALIBRATION_SAMPLES", "100"))
            dataset_path = generate_calibration_dataset(dataset_dir, num_samples)
        else:
            logger.info(f"Using existing calibration dataset: {dataset_file}")
            dataset_path = dataset_file
    else:
        logger.info("FP16 conversion (no quantization)")
        logger.info(f"Output model: {rknn_model}")
    
    try:
        # Step 1: Fix shapes
        logger.info("\n" + "="*60)
        logger.info("Step 1: Fixing ONNX shapes")
        logger.info("="*60)
        fix_onnx_shapes(input_onnx, fixed_onnx, batch_size=1, seq_length=512)
        
        # Step 2: Convert to RKNN
        logger.info("\n" + "="*60)
        logger.info("Step 2: Converting to RKNN")
        logger.info("="*60)
        convert_to_rknn(fixed_onnx, rknn_model, do_quantization=do_quantization, dataset_path=dataset_path)
        
        # Step 3: Validate (optional, only if we have runtime)
        if os.getenv("VALIDATE_CONVERSION", "0") == "1":
            logger.info("\n" + "="*60)
            logger.info("Step 3: Validating conversion")
            logger.info("="*60)
            validate_conversion(fixed_onnx, rknn_model)
        
        logger.info("\n" + "="*60)
        logger.info("✓ Conversion complete!")
        logger.info("="*60)
        logger.info(f"RKNN model saved: {rknn_model}")
        
        # Cleanup intermediate file
        if os.getenv("KEEP_INTERMEDIATE", "0") != "1":
            logger.info("Cleaning up intermediate files")
            if os.path.exists(fixed_onnx):
                os.remove(fixed_onnx)
                logger.info(f"Removed: {fixed_onnx}")
        
    except Exception as e:
        logger.error(f"Conversion failed: {e}", exc_info=True)
        logger.error("\nCommon issues:")
        logger.error("  1. Unsupported ONNX operators for RKNN")
        logger.error("  2. Quantized model compatibility (try FP32 source)")
        logger.error("  3. RKNN toolkit version mismatch")
        logger.error("\nTroubleshooting:")
        logger.error("  - Check the full error trace above")
        logger.error("  - Try with original FP32 model instead of quantized")
        logger.error("  - Verify RKNN toolkit version matches librknnrt.so")
        sys.exit(1)


if __name__ == "__main__":
    main()
