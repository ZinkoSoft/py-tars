"""Tests for NPU-accelerated wake word detection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest

from wake_activation.config import WakeActivationConfig
from wake_activation.detector import (
    DetectorUnavailableError,
    WakeDetector,
    _RKNNBackend,
    create_npu_wake_detector,
    create_wake_detector,
)


class TestRKNNBackend:
    """Tests for the RKNN NPU backend."""

    @patch("wake_activation.detector.RKNNLite")
    def test_rknn_backend_initialization_success(self, mock_rknn_class):
        """Test successful RKNN backend initialization."""
        # Setup mock
        mock_rknn = Mock()
        mock_rknn.load_rknn.return_value = 0  # Success
        mock_rknn.init_runtime.return_value = 0  # Success
        mock_rknn_class.return_value = mock_rknn

        # Create backend
        backend = _RKNNBackend("/path/to/model.rknn", core_mask=0)

        # Verify initialization
        assert backend.frame_samples == 1280
        assert backend.sample_rate == 16000
        mock_rknn.load_rknn.assert_called_once_with("/path/to/model.rknn")
        mock_rknn.init_runtime.assert_called_once_with(core_mask=0)

    @patch("wake_activation.detector.RKNNLite")
    def test_rknn_backend_load_failure(self, mock_rknn_class):
        """Test RKNN backend with model load failure."""
        mock_rknn = Mock()
        mock_rknn.load_rknn.return_value = -1  # Failure
        mock_rknn_class.return_value = mock_rknn

        with pytest.raises(DetectorUnavailableError, match="Failed to load RKNN model"):
            _RKNNBackend("/path/to/model.rknn")

    @patch("wake_activation.detector.RKNNLite")
    def test_rknn_backend_runtime_failure(self, mock_rknn_class):
        """Test RKNN backend with runtime init failure."""
        mock_rknn = Mock()
        mock_rknn.load_rknn.return_value = 0  # Success
        mock_rknn.init_runtime.return_value = -1  # Failure
        mock_rknn_class.return_value = mock_rknn

        with pytest.raises(DetectorUnavailableError, match="Failed to initialize RKNN runtime"):
            _RKNNBackend("/path/to/model.rknn")

    @patch("wake_activation.detector.RKNNLite")
    def test_rknn_backend_inference(self, mock_rknn_class):
        """Test RKNN backend inference processing."""
        # Setup successful backend
        mock_rknn = Mock()
        mock_rknn.load_rknn.return_value = 0
        mock_rknn.init_runtime.return_value = 0
        mock_rknn.inference.return_value = [np.array([0.8])]  # High confidence detection
        mock_rknn_class.return_value = mock_rknn

        backend = _RKNNBackend("/path/to/model.rknn")

        # Test inference
        frame = np.random.randint(-32767, 32767, 1280, dtype=np.int16)
        score = backend.process(frame)

        assert score == 0.8
        mock_rknn.inference.assert_called_once()
        # Verify input was normalized to float32 [-1, 1] range
        call_args = mock_rknn.inference.call_args[1]["inputs"]
        assert len(call_args) == 1
        assert call_args[0].dtype == np.float32
        assert np.all(call_args[0] >= -1.0) and np.all(call_args[0] <= 1.0)

    @patch("wake_activation.detector.RKNNLite", None)
    def test_rknn_backend_unavailable(self):
        """Test RKNN backend when RKNNLite not available."""
        with pytest.raises(DetectorUnavailableError, match="rknn-toolkit-lite2 is not installed"):
            _RKNNBackend("/path/to/model.rknn")


class TestNPUWakeDetector:
    """Tests for NPU wake detector creation."""

    @patch("wake_activation.detector._RKNNBackend")
    def test_create_npu_wake_detector_success(self, mock_backend_class):
        """Test successful NPU wake detector creation."""
        mock_backend = Mock()
        mock_backend.frame_samples = 1280
        mock_backend.sample_rate = 16000
        mock_backend_class.return_value = mock_backend

        model_path = Path("/models/test.rknn")

        # Mock file existence
        with patch.object(Path, "exists", return_value=True):
            detector = create_npu_wake_detector(
                model_path=model_path,
                threshold=0.5,
                min_retrigger_sec=1.0,
                energy_window_ms=750,
                npu_core_mask=7,
            )

        assert isinstance(detector, WakeDetector)
        mock_backend_class.assert_called_once_with("/models/test.rknn", 7)

    def test_create_npu_wake_detector_missing_model(self):
        """Test NPU detector creation with missing model file."""
        model_path = Path("/nonexistent/model.rknn")

        with pytest.raises(DetectorUnavailableError, match="RKNN model not found"):
            create_npu_wake_detector(
                model_path=model_path, threshold=0.5, min_retrigger_sec=1.0, energy_window_ms=750
            )

    def test_create_npu_wake_detector_wrong_extension(self):
        """Test NPU detector creation with wrong file extension."""
        model_path = Path("/models/test.tflite")

        with patch.object(Path, "exists", return_value=True):
            with pytest.raises(DetectorUnavailableError, match="Expected .rknn model"):
                create_npu_wake_detector(
                    model_path=model_path,
                    threshold=0.5,
                    min_retrigger_sec=1.0,
                    energy_window_ms=750,
                )


class TestNPUIntegration:
    """Tests for NPU integration in main detector creation."""

    @patch("wake_activation.detector.check_npu_availability")
    @patch("wake_activation.detector.create_npu_wake_detector")
    def test_create_wake_detector_npu_available(self, mock_create_npu, mock_check_npu):
        """Test detector creation when NPU is available."""
        mock_check_npu.return_value = (True, "NPU is available")
        mock_detector = Mock(spec=WakeDetector)
        mock_create_npu.return_value = mock_detector

        model_path = Path("/models/test.rknn")

        with patch.object(Path, "exists", return_value=True):
            detector = create_wake_detector(
                model_path=model_path,
                threshold=0.5,
                min_retrigger_sec=1.0,
                energy_window_ms=750,
                enable_speex_noise_suppression=False,
                vad_threshold=0.0,
                use_npu=True,
                npu_core_mask=7,
            )

        assert detector == mock_detector
        mock_create_npu.assert_called_once()

    @patch("wake_activation.detector.check_npu_availability")
    @patch("wake_activation.detector.create_cpu_wake_detector")
    def test_create_wake_detector_npu_unavailable_fallback(self, mock_create_cpu, mock_check_npu):
        """Test detector creation falls back to CPU when NPU unavailable."""
        mock_check_npu.return_value = (False, "NPU not available")
        mock_detector = Mock(spec=WakeDetector)
        mock_create_cpu.return_value = mock_detector

        model_path = Path("/models/test.rknn")

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "with_suffix") as mock_with_suffix:
                fallback_path = Path("/models/test.tflite")
                mock_with_suffix.return_value = fallback_path

                detector = create_wake_detector(
                    model_path=model_path,
                    threshold=0.5,
                    min_retrigger_sec=1.0,
                    energy_window_ms=750,
                    enable_speex_noise_suppression=False,
                    vad_threshold=0.0,
                    use_npu=True,
                )

        assert detector == mock_detector
        mock_create_cpu.assert_called_once()
        # Verify fallback to .tflite model
        args = mock_create_cpu.call_args[1]
        assert args["model_path"] == fallback_path


class TestWakeActivationConfig:
    """Tests for NPU configuration options."""

    def test_npu_config_defaults(self):
        """Test NPU configuration default values."""
        config = WakeActivationConfig()

        assert config.use_npu is False
        assert str(config.rknn_model_path) == "/models/openwakeword/hey_tars.rknn"
        assert config.npu_core_mask == 0

    def test_npu_config_from_env(self):
        """Test NPU configuration from environment variables."""
        env = {
            "WAKE_USE_NPU": "1",
            "WAKE_RKNN_MODEL_PATH": "/custom/path/model.rknn",
            "WAKE_NPU_CORE_MASK": "7",
        }

        config = WakeActivationConfig.from_env(env)

        assert config.use_npu is True
        assert str(config.rknn_model_path) == "/custom/path/model.rknn"
        assert config.npu_core_mask == 7

    def test_npu_config_boolean_variations(self):
        """Test NPU boolean config accepts various true values."""
        for true_value in ["1", "true", "yes", "TRUE", "YES"]:
            env = {"WAKE_USE_NPU": true_value}
            config = WakeActivationConfig.from_env(env)
            assert config.use_npu is True

        for false_value in ["0", "false", "no", "FALSE", "NO", ""]:
            env = {"WAKE_USE_NPU": false_value}
            config = WakeActivationConfig.from_env(env)
            assert config.use_npu is False


@pytest.mark.integration
class TestNPUDetectorIntegration:
    """Integration tests for NPU detector (requires actual NPU hardware)."""

    def test_npu_availability_check(self):
        """Test NPU availability check function."""
        from wake_activation.npu_utils import check_npu_availability

        is_available, status = check_npu_availability()

        # Should return boolean and non-empty status
        assert isinstance(is_available, bool)
        assert isinstance(status, str)
        assert len(status) > 0

    @pytest.mark.skipif(not Path("/dev/rknpu").exists(), reason="NPU device not available")
    def test_real_npu_backend_creation(self):
        """Test creating RKNN backend with real NPU (if available)."""
        # This test only runs if NPU hardware is present
        from wake_activation.npu_utils import check_npu_availability

        is_available, _ = check_npu_availability()
        if not is_available:
            pytest.skip("NPU hardware not available")

        # This would require a real .rknn model file
        # In practice, you'd convert a test model first
        pytest.skip("Requires real RKNN model file for testing")
