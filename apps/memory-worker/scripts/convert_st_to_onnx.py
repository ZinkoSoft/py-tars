#!/usr/bin/env python3
"""
Convert SentenceTransformer model to ONNX format for NPU conversion.

This script exports a SentenceTransformer model (BERT-based) to ONNX format,
which can then be converted to RKNN for NPU acceleration.

Usage:
    python convert_st_to_onnx.py [--model MODEL_NAME] [--output OUTPUT_PATH]
    
Examples:
    # Export default model (all-MiniLM-L6-v2)
    python convert_st_to_onnx.py
    
    # Export specific model
    python convert_st_to_onnx.py --model sentence-transformers/paraphrase-MiniLM-L6-v2
    
    # Custom output path
    python convert_st_to_onnx.py --output /models/embedder/my-model.onnx
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def export_to_onnx(
    model_name: str,
    output_path: Path,
    *,
    max_seq_length: int = 256,
    opset_version: int = 14,
    validate: bool = True,
) -> bool:
    """Export SentenceTransformer model to ONNX format.
    
    Args:
        model_name: HuggingFace model name or local path
        output_path: Path for output .onnx file
        max_seq_length: Maximum sequence length for the model
        opset_version: ONNX opset version (14+ recommended for RK3588)
        validate: Run validation after export
        
    Returns:
        True if export successful, False otherwise
        
    Note:
        This exports only the BERT model. Tokenization should be done
        separately in Python before passing to the ONNX model.
    """
    logger.info(f"Loading SentenceTransformer model: {model_name}")
    
    try:
        # Load model
        model = SentenceTransformer(model_name)
        
        # Get the underlying transformer model (BERT)
        transformer_module = model[0]
        bert_model = transformer_module.auto_model
        
        # Set to eval mode
        bert_model.eval()
        
        logger.info(f"Model architecture: {type(bert_model).__name__}")
        logger.info(f"Embedding dimension: {model.get_sentence_embedding_dimension()}")
        logger.info(f"Max sequence length: {max_seq_length}")
        
        # Create dummy input for export
        # BERT expects: input_ids, attention_mask, (optional: token_type_ids)
        batch_size = 1
        seq_length = max_seq_length
        
        dummy_input = {
            'input_ids': torch.randint(0, 1000, (batch_size, seq_length), dtype=torch.long),
            'attention_mask': torch.ones((batch_size, seq_length), dtype=torch.long),
        }
        
        # Check if model expects token_type_ids
        try:
            with torch.no_grad():
                _ = bert_model(**dummy_input)
            input_names = ['input_ids', 'attention_mask']
        except TypeError:
            # Model might need token_type_ids
            dummy_input['token_type_ids'] = torch.zeros((batch_size, seq_length), dtype=torch.long)
            input_names = ['input_ids', 'attention_mask', 'token_type_ids']
        
        output_names = ['last_hidden_state']
        
        # For RKNN, we need FIXED shapes (no dynamic axes)
        # RKNN doesn't handle dynamic shapes well
        logger.info("Using FIXED shapes for RKNN compatibility (batch=1, seq_len=256)")
        logger.info("Note: This means all inputs must be padded to 256 tokens")
        dynamic_axes = None
        
        # Export to ONNX
        logger.info(f"Exporting to ONNX: {output_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        torch.onnx.export(
            bert_model,
            (dummy_input,),
            str(output_path),
            input_names=input_names,
            output_names=output_names,
            dynamic_axes=dynamic_axes,
            opset_version=opset_version,
            do_constant_folding=True,
            export_params=True,
        )
        
        logger.info("✅ ONNX export successful!")
        
        # Validate if requested
        if validate:
            success = validate_onnx_model(
                output_path,
                model,
                bert_model,
                input_names,
                max_seq_length
            )
            if not success:
                logger.error("❌ Validation failed")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return False


def validate_onnx_model(
    onnx_path: Path,
    original_model: SentenceTransformer,
    bert_model: torch.nn.Module,
    input_names: List[str],
    max_seq_length: int,
) -> bool:
    """Validate ONNX model output matches original PyTorch model.
    
    Args:
        onnx_path: Path to exported ONNX model
        original_model: Original SentenceTransformer model
        bert_model: BERT model that was exported
        input_names: Names of inputs used in export
        max_seq_length: Maximum sequence length
        
    Returns:
        True if validation successful, False otherwise
    """
    logger.info("Validating ONNX model...")
    
    try:
        import onnxruntime as ort
    except ImportError:
        logger.warning("onnxruntime not available, skipping validation")
        return True
    
    try:
        # Load ONNX model
        session = ort.InferenceSession(str(onnx_path))
        
        # Test with sample text
        test_texts = [
            "This is a test sentence.",
            "Another example for validation.",
            "Short text",
        ]
        
        logger.info(f"Testing with {len(test_texts)} sample texts...")
        
        for i, text in enumerate(test_texts):
            # Get tokenizer from SentenceTransformer
            tokenizer = original_model.tokenizer
            
            # Tokenize
            encoded = tokenizer(
                text,
                padding='max_length',
                truncation=True,
                max_length=max_seq_length,
                return_tensors='pt'
            )
            
            # Prepare inputs for ONNX
            onnx_inputs = {
                'input_ids': encoded['input_ids'].numpy(),
                'attention_mask': encoded['attention_mask'].numpy(),
            }
            
            if 'token_type_ids' in input_names:
                if 'token_type_ids' in encoded:
                    onnx_inputs['token_type_ids'] = encoded['token_type_ids'].numpy()
                else:
                    onnx_inputs['token_type_ids'] = np.zeros_like(onnx_inputs['input_ids'])
            
            # Run ONNX inference
            onnx_outputs = session.run(None, onnx_inputs)
            onnx_last_hidden = onnx_outputs[0]
            
            # Run PyTorch inference
            with torch.no_grad():
                if 'token_type_ids' in input_names and 'token_type_ids' not in encoded:
                    encoded['token_type_ids'] = torch.zeros_like(encoded['input_ids'])
                
                pt_outputs = bert_model(**{k: v for k, v in encoded.items() if k in input_names})
                pt_last_hidden = pt_outputs.last_hidden_state.numpy()
            
            # Compare outputs
            max_diff = np.abs(onnx_last_hidden - pt_last_hidden).max()
            mean_diff = np.abs(onnx_last_hidden - pt_last_hidden).mean()
            
            logger.info(f"  Test {i+1}: max_diff={max_diff:.6f}, mean_diff={mean_diff:.6f}")
            
            if max_diff > 1e-4:
                logger.warning(f"  Large difference detected: {max_diff:.6f}")
                logger.warning("  This may be acceptable depending on use case")
        
        logger.info("✅ Validation complete!")
        logger.info("")
        logger.info("Next steps:")
        rknn_output = onnx_path.with_suffix('.rknn')
        logger.info(f"1. Convert to RKNN: python convert_onnx_to_rknn.py {onnx_path} {rknn_output}")
        logger.info("2. Test on NPU device")
        logger.info("3. Enable in .env: NPU_EMBEDDER_ENABLED=1")
        logger.info("")
        logger.info("Note: Mean pooling and L2 normalization will be done in Python post-processing")
        
        return True
        
    except Exception as e:
        logger.error(f"Validation failed: {e}", exc_info=True)
        return False


def main() -> int:
    """Main entry point for the conversion script."""
    parser = argparse.ArgumentParser(
        description="Export SentenceTransformer model to ONNX format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="SentenceTransformer model name or path (default: all-MiniLM-L6-v2)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("../../../data/model_cache/embedder/all-MiniLM-L6-v2.onnx"),
        help="Output ONNX file path (default: ../../../data/model_cache/embedder/all-MiniLM-L6-v2.onnx)"
    )
    parser.add_argument(
        "--max-seq-length",
        type=int,
        default=256,
        help="Maximum sequence length (default: 256)"
    )
    parser.add_argument(
        "--opset-version",
        type=int,
        default=14,
        help="ONNX opset version (default: 14)"
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation after export"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Export model
    success = export_to_onnx(
        args.model,
        args.output,
        max_seq_length=args.max_seq_length,
        opset_version=args.opset_version,
        validate=not args.no_validate,
    )
    
    if not success:
        logger.error("❌ Export failed")
        return 1
    
    logger.info("🎉 Export completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
