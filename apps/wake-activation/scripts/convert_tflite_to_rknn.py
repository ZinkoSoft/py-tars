#!/usr/bin/env python3
"""
Convert OpenWakeWord TFLite models to RKNN format for NPU acceleration.

This script converts .tflite wake word models to .rknn format optimized for the RK3588 NPU.
It handles the specific input/output format requirements for wake word detection.

Usage:
    python convert_tflite_to_rknn.py input.tflite output.rknn [--quantize]
    
Examples:
    # Basic conversion
    python convert_tflite_to_rknn.py /models/openwakeword/hey_tars.tflite /models/openwakeword/hey_tars.rknn
    
    # With quantization for better NPU performance
    python convert_tflite_to_rknn.py /models/openwakeword/hey_tars.tflite /models/openwakeword/hey_tars.rknn --quantize
"""

from __future__ import annotations

import argparse
import logging
import platform
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Union

import numpy as np

try:
    from rknn.api import RKNN
except ImportError:
    print("ERROR: rknn-toolkit2 is required but not installed.", file=sys.stderr)
    print("Install it with: pip install rknn-toolkit2", file=sys.stderr)
    sys.exit(1)

# Wake word model expects 16kHz audio frames of 1280 samples (80ms)
FRAME_SAMPLES = 1280
SAMPLE_RATE = 16000
FRAME_DURATION_MS = 80

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_calibration_dataset(
    num_samples: int = 100, 
    input_format: str = ".tflite"
) -> Union[List[np.ndarray], str]:
    """Create calibration dataset for quantization.
    
    For RKNN toolkit, this can be either:
    - List of numpy arrays (passed directly to build())
    - Path to dataset files (for some RKNN versions)
    
    Args:
        num_samples: Number of calibration samples to generate
        input_format: Input model format (".tflite" or ".onnx")
        
    Returns:
        List of numpy arrays for calibration
    """
    logger.info(f"Creating {num_samples} calibration samples for {input_format}")
    
    dataset = []
    for i in range(num_samples):
        if input_format == '.onnx':
            # ONNX model expects mel-spectrogram: [1, 16, 96]
            # Generate realistic mel-spectrogram-like data
            sample = np.random.normal(0, 1.0, (1, 16, 96)).astype(np.float32)
            
            # Add some speech-like characteristics to mel features
            if i % 5 == 0:  # 20% speech-like samples
                # Add some energy in lower frequency bins
                sample[0, :8, :] += 0.5
                # Add some formant-like structure
                sample[0, 2:4, 20:40] += 1.0
                sample[0, 6:8, 40:60] += 0.8
        else:
            # TFLite model expects raw audio: [1280] samples
            sample = np.random.normal(0, 0.1, FRAME_SAMPLES).astype(np.float32)
            
            # Add some speech-like characteristics
            if i % 5 == 0:  # 20% speech-like samples
                # Add some harmonic content and envelope
                t = np.linspace(0, FRAME_DURATION_MS / 1000, FRAME_SAMPLES)
                speech_like = 0.3 * np.sin(2 * np.pi * 200 * t) * np.exp(-t * 5)
                sample += speech_like
            elif i % 10 == 0:  # 10% higher energy samples
                sample *= 2.0
                
            # Normalize to [-1, 1] range typical for audio
            sample = np.clip(sample, -1.0, 1.0)
        
        dataset.append(sample)
    
    return dataset


def convert_model_to_rknn(
    input_path: Path,
    rknn_path: Path,
    *,
    quantize: bool = False,
    target_platform: str = "rk3588",
    optimization_level: int = 3,
) -> bool:
    """Convert model (TFLite or ONNX) to RKNN format.
    
    Args:
        input_path: Path to input model (.tflite or .onnx)
        rknn_path: Path for output .rknn model
        quantize: Enable quantization (w8a8) for better NPU performance vs w16a16i
        target_platform: Target Rockchip platform (rk3588, rk3566, etc.)
        optimization_level: RKNN optimization level (0-3, higher = more aggressive)
        
    Returns:
        True if conversion successful, False otherwise
        
    Note:
        - quantize=True uses w8a8 (8-bit weights/activations) for maximum NPU efficiency
        - quantize=False uses w16a16i (16-bit) for higher precision but slower inference
        - For wake word detection, w8a8 typically provides best performance with minimal accuracy loss
        - On ARM64 platforms, ONNX models are preferred over TFLite for conversion
    """
    if not input_path.exists():
        logger.error(f"Input model not found: {input_path}")
        return False
    
    input_format = input_path.suffix.lower()
    if input_format not in [".tflite", ".onnx"]:
        logger.error(f"Unsupported input format: {input_format}. Use .tflite or .onnx")
        return False
    
    # Check platform compatibility
    arch = platform.machine().lower()
    if arch in ['aarch64', 'arm64'] and input_format == '.tflite':
        logger.warning("TFLite conversion on ARM64 is not supported by RKNN Toolkit2")
        logger.info("Looking for ONNX equivalent...")
        
        # Try to find ONNX equivalent
        onnx_path = input_path.with_suffix('.onnx')
        if onnx_path.exists():
            logger.info(f"Found ONNX equivalent: {onnx_path}")
            input_path = onnx_path
            input_format = '.onnx'
        else:
            logger.error(f"No ONNX equivalent found for {input_path}")
            logger.error("Please convert to ONNX first or run conversion on x86_64 platform")
            return False
    
    logger.info(f"Converting {input_path} to {rknn_path}")
    logger.info(f"Input format: {input_format}")
    logger.info(f"Target platform: {target_platform}")
    logger.info(f"Architecture: {arch}")
    logger.info(f"Quantization: {'enabled' if quantize else 'disabled'}")
    logger.info(f"Optimization level: {optimization_level}")
    
    rknn = RKNN(verbose=False)
    
    try:
        # Configure RKNN
        logger.info("Configuring RKNN...")
        
        # For audio/mel-spectrogram models, typically no normalization is needed
        # But we need to match the expected number of input channels
        if input_format == '.onnx':
            # ONNX models typically have mel-spectrogram input with 16 channels
            mean_values = [[0.0] * 16]  # 16 channels for mel-spectrogram
            std_values = [[1.0] * 16]
        else:
            # TFLite models might have different input structure
            mean_values = [[0.0]]
            std_values = [[1.0]]
        
        if quantize:
            # Use w8a8 (weight 8-bit, activation 8-bit) for quantized models
            ret = rknn.config(
                mean_values=mean_values,
                std_values=std_values,
                target_platform=target_platform,
                optimization_level=optimization_level,
                quantized_dtype="w8a8",
                quantized_algorithm="mmse",
            )
        else:
            # Use w16a16i for non-quantized models (16-bit weights/activations)
            ret = rknn.config(
                mean_values=mean_values,
                std_values=std_values,
                target_platform=target_platform,
                optimization_level=optimization_level,
                quantized_dtype="w16a16i",
            )
        if ret != 0:
            logger.error("RKNN config failed")
            return False
        
        # Load model based on format
        logger.info(f"Loading {input_format.upper()} model...")
        if input_format == '.onnx':
            ret = rknn.load_onnx(model=str(input_path))
        else:  # .tflite
            ret = rknn.load_tflite(model=str(input_path))
            
        if ret != 0:
            logger.error(f"Failed to load {input_format.upper()} model")
            return False
        
        # Build RKNN model
        logger.info("Building RKNN model...")
        
        if quantize:
            # Generate calibration dataset for quantization
            logger.info("Creating calibration dataset for quantization...")
            dataset = create_calibration_dataset(num_samples=50, input_format=input_format)
            
            ret = rknn.build(do_quantization=True, dataset=dataset)
        else:
            ret = rknn.build(do_quantization=False)
            
        if ret != 0:
            logger.error("RKNN build failed")
            return False
        
        # Export RKNN model
        logger.info(f"Exporting RKNN model to {rknn_path}...")
        ret = rknn.export_rknn(str(rknn_path))
        if ret != 0:
            logger.error("RKNN export failed")
            return False
        
        logger.info("✅ Conversion completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Conversion failed with exception: {e}")
        return False
    finally:
        # Always release RKNN resources
        rknn.release()


def validate_rknn_model(rknn_path: Path) -> bool:
    """Validate the converted RKNN model by running a test inference.
    
    Args:
        rknn_path: Path to the .rknn model to validate
        
    Returns:
        True if validation successful, False otherwise
    """
    logger.info(f"Validating RKNN model: {rknn_path}")
    
    try:
        from rknnlite.api import RKNNLite
    except ImportError:
        logger.warning("rknn-toolkit-lite2 not available, skipping validation")
        return True
    
    rknn_lite = RKNNLite()
    
    try:
        # Load model
        ret = rknn_lite.load_rknn(str(rknn_path))
        if ret != 0:
            logger.error("Failed to load RKNN model for validation")
            return False
        
        # Initialize runtime
        ret = rknn_lite.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO)
        if ret != 0:
            logger.error("Failed to initialize RKNN runtime")
            return False
        
        # Test inference with dummy data
        dummy_frame = np.random.uniform(-1.0, 1.0, (1, FRAME_SAMPLES)).astype(np.float32)
        outputs = rknn_lite.inference(inputs=[dummy_frame])
        
        if outputs and len(outputs) > 0:
            output_shape = outputs[0].shape
            logger.info(f"✅ Validation successful! Output shape: {output_shape}")
            return True
        else:
            logger.error("No outputs received from inference")
            return False
            
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return False
    finally:
        rknn_lite.release()


def main() -> int:
    """Main entry point for the conversion script."""
    parser = argparse.ArgumentParser(
        description="Convert OpenWakeWord models (TFLite/ONNX) to RKNN format for NPU acceleration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument("input", type=Path, help="Input model file (.tflite or .onnx)")
    parser.add_argument("output", type=Path, help="Output .rknn model file")
    parser.add_argument(
        "--quantize", 
        action="store_true",
        help="Enable w8a8 quantization for maximum NPU performance (vs w16a16i precision)"
    )
    parser.add_argument(
        "--target",
        default="rk3588",
        choices=["rk3588", "rk3566", "rk3568"],
        help="Target Rockchip platform (default: rk3588)"
    )
    parser.add_argument(
        "--optimization-level",
        type=int,
        default=3,
        choices=[0, 1, 2, 3],
        help="RKNN optimization level (default: 3)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the converted model with test inference"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Validate inputs
    if not args.input.exists():
        logger.error(f"Input file does not exist: {args.input}")
        return 1
    
    input_ext = args.input.suffix.lower()
    if input_ext not in [".tflite", ".onnx"]:
        logger.error(f"Input file must be .tflite or .onnx, got: {input_ext}")
        return 1
    
    if args.output.suffix.lower() != ".rknn":
        logger.error(f"Output file must have .rknn extension, got: {args.output.suffix}")
        return 1
    
    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert model
    success = convert_model_to_rknn(
        args.input,
        args.output,
        quantize=args.quantize,
        target_platform=args.target,
        optimization_level=args.optimization_level,
    )
    
    if not success:
        logger.error("❌ Conversion failed")
        return 1
    
    # Validate if requested
    if args.validate:
        if not validate_rknn_model(args.output):
            logger.error("❌ Validation failed")
            return 1
    
    logger.info("🎉 All operations completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())