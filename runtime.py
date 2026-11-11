from pathlib import Path

import numpy as np
import onnxruntime as ort


VIDEO4K_MODELS = (
    "Video4K_V9_video_V9_x2_S2GAN_latest.onnx",
    "Video4K_V10_video_V10_x2_S2GAN_417000.onnx",
)
RIFE_MODEL = "rife_v4.6_winx_fp16weights.onnx"


def create_session(path, device):
    if device not in ("cuda", "cpu"):
        raise ValueError("device must be cuda or cpu")
    if not Path(path).is_file():
        raise FileNotFoundError(f"Model not installed: {path}")
    provider = "CUDAExecutionProvider" if device == "cuda" else "CPUExecutionProvider"
    if provider not in ort.get_available_providers():
        raise RuntimeError(
            f"{provider} unavailable. Install the matching ONNX Runtime GPU/CUDA/cuDNN "
            "environment for cloud use; cpu is only for explicit local validation."
        )
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(path), sess_options=options, providers=[provider])
    if session.get_providers()[0] != provider:
        raise RuntimeError(f"Requested {provider}, initialized {session.get_providers()}")
    session.disable_fallback()
    return session


class Video4K:
    def __init__(self, path, device):
        self.session = create_session(path, device)
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        if (self.input_name, self.output_name) != ("DigiartyInput", "DigiartyOutput"):
            raise ValueError("This node expects the tested Video4K V9/V10 ONNX models")

    def upscale(self, image):
        image = np.ascontiguousarray(image, dtype=np.float32)
        if image.ndim != 4 or image.shape[:2] != (1, 3):
            raise ValueError("Expected one RGB NCHW frame")
        h, w = image.shape[-2:]
        # The exported network contains pixel-unshuffle/window reshapes.
        padded = np.pad(image, ((0, 0), (0, 0), (0, (-h) % 32), (0, (-w) % 32)), mode="edge")
        result = self.session.run([self.output_name], {self.input_name: padded})[0]
        if result.shape != (1, 3, padded.shape[2] * 2, padded.shape[3] * 2):
            raise RuntimeError(f"Unexpected Video4K output shape: {result.shape}")
        if not np.isfinite(result).all():
            raise RuntimeError("Video4K returned non-finite pixels")
        return np.ascontiguousarray(np.clip(result[:, :, :h * 2, :w * 2], 0, 1))


class Rife46:
    def __init__(self, path, device):
        self.session = create_session(path, device)
        input_info = self.session.get_inputs()
        if len(input_info) != 1 or input_info[0].shape[1] != 7:
            raise ValueError("Expected vs-mlrt rife_v2/rife_v4.6.onnx (7-channel input)")
        self.input_name = input_info[0].name
        self.output_name = self.session.get_outputs()[0].name

    def interpolate(self, first, second, timestep):
        if first.shape != second.shape or first.ndim != 4 or first.shape[:2] != (1, 3):
            raise ValueError("RIFE needs two equally sized RGB NCHW frames")
        time_plane = np.full((1, 1, *first.shape[2:]), timestep, dtype=np.float32)
        packed = np.ascontiguousarray(np.concatenate((first, second, time_plane), axis=1), dtype=np.float32)
        result = self.session.run([self.output_name], {self.input_name: packed})[0]
        if result.shape != first.shape or not np.isfinite(result).all():
            raise RuntimeError(f"Invalid RIFE output: {result.shape}")
        return np.ascontiguousarray(np.clip(result, 0, 1))
