#!/usr/bin/env python3
"""Test NPU wake word detection in Docker container."""

import logging
import sys
import time
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_npu_availability():
    """Test NPU availability and basic functionality."""
    logger.info("=== Testing NPU Availability ===")
    
    try:
        from wake_activation.npu_utils import check_npu_availability, get_npu_info
        
        is_available, status = check_npu_availability()
        logger.info("NPU Status Check:")
        for line in status.split('\n'):
            logger.info(f"  {line}")
        
        if is_available:
            info = get_npu_info()
            if info:
                logger.info("NPU Capabilities:")
                for key, value in info.items():
                    logger.info(f"  {key}: {value}")
        
        return is_available
        
    except Exception as e:
        logger.error(f"NPU availability check failed: {e}")
        return False


def test_rknn_model_loading():
    """Test loading and basic inference with RKNN model."""
    logger.info("=== Testing RKNN Model Loading ===")
    
    model_path = Path("/models/openwakeword/hey_tars.rknn")
    if not model_path.exists():
        logger.error(f"RKNN model not found at {model_path}")
        return False
    
    try:
        from rknnlite.api import RKNNLite
        
        rknn = RKNNLite()
        
        # Load model
        ret = rknn.load_rknn(str(model_path))
        if ret != 0:
            logger.error("Failed to load RKNN model")
            return False
        logger.info("✅ RKNN model loaded successfully")
        
        # Initialize runtime
        ret = rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_AUTO)
        if ret != 0:
            logger.error("Failed to initialize RKNN runtime")
            return False
        logger.info("✅ RKNN runtime initialized successfully")
        
        # Test inference with dummy data
        dummy_input = np.random.normal(0, 1.0, (1, 16, 96)).astype(np.float32)
        logger.info(f"Running test inference with input shape: {dummy_input.shape}")
        
        start_time = time.time()
        outputs = rknn.inference(inputs=[dummy_input])
        inference_time = time.time() - start_time
        
        if outputs and len(outputs) > 0:
            output_shape = outputs[0].shape
            output_value = float(outputs[0].flatten()[0]) if outputs[0].size > 0 else 0.0
            logger.info(f"✅ Inference successful!")
            logger.info(f"  Output shape: {output_shape}")
            logger.info(f"  Output value: {output_value:.6f}")
            logger.info(f"  Inference time: {inference_time*1000:.2f}ms")
        else:
            logger.error("No outputs received from inference")
            return False
        
        # Clean up
        rknn.release()
        logger.info("✅ RKNN resources released")
        
        return True
        
    except Exception as e:
        logger.error(f"RKNN model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_wake_detector_creation():
    """Test creating wake detector with NPU backend."""
    logger.info("=== Testing Wake Detector Creation ===")
    
    try:
        from wake_activation.config import WakeActivationConfig
        from wake_activation.detector import create_wake_detector
        
        config = WakeActivationConfig()
        logger.info(f"Config: NPU enabled = {config.use_npu}")
        logger.info(f"RKNN model path: {config.rknn_model_path}")
        
        detector = create_wake_detector(
            config.rknn_model_path if config.use_npu else config.wake_model_path,
            threshold=config.wake_detection_threshold,
            min_retrigger_sec=config.min_retrigger_sec,
            energy_window_ms=config.detection_window_ms,
            enable_speex_noise_suppression=config.enable_speex_noise_suppression,
            vad_threshold=config.vad_threshold,
            energy_boost_factor=config.energy_boost_factor,
            low_energy_threshold_factor=config.low_energy_threshold_factor,
            background_noise_sensitivity=config.background_noise_sensitivity,
            use_npu=config.use_npu,
            npu_core_mask=config.npu_core_mask,
        )
        
        logger.info("✅ Wake detector created successfully!")
        logger.info(f"  Frame samples: {detector.frame_samples}")
        logger.info(f"  Sample rate: {detector.sample_rate}")
        
        # Test processing a dummy audio frame
        dummy_frame = np.random.uniform(-1.0, 1.0, detector.frame_samples).astype(np.float32)
        start_time = time.time()
        result = detector.process_frame(dummy_frame, ts=time.monotonic())
        process_time = time.time() - start_time
        
        logger.info(f"✅ Frame processing test completed")
        logger.info(f"  Processing time: {process_time*1000:.2f}ms")
        logger.info(f"  Detection result: {result}")
        
        return True
        
    except Exception as e:
        logger.error(f"Wake detector creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all NPU tests."""
    logger.info("🚀 Starting NPU Wake Activation Tests")
    
    # Test NPU availability
    if not test_npu_availability():
        logger.error("❌ NPU not available - cannot proceed with tests")
        return 1
    
    # Test RKNN model loading
    if not test_rknn_model_loading():
        logger.error("❌ RKNN model test failed")
        return 1
    
    # Test wake detector creation
    if not test_wake_detector_creation():
        logger.error("❌ Wake detector test failed")
        return 1
    
    logger.info("🎉 All NPU tests passed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())