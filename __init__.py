import math
from pathlib import Path

import torch

import comfy.model_management
import comfy.utils
import folder_paths

from .runtime import RIFE_MODEL, VIDEO4K_MODELS, Rife46, Video4K
from .streaming import WinxVideoApp

WEB_DIRECTORY = "./web"


folder_paths.add_model_folder_path("winx_video4k", str(Path(folder_paths.models_dir) / "winx_video4k"))


class WinxVideo4KUpscale:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",),
            "model_name": (list(VIDEO4K_MODELS),),
            "device": (["cuda", "cpu"],),
            "tile_size": ("INT", {"default": 256, "min": 0, "max": 1024, "step": 32,
                                  "tooltip": "0: full frame; 256: overlapping tiles. Larger tiles use more memory."}),
        }}

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "upscale"
    CATEGORY = "Winx Video4K"
    DESCRIPTION = "Video4K V9/V10 ONNX candidates. 2x resolution; CUDA required unless cpu is explicitly selected."

    def upscale(self, images, model_name, device, tile_size):
        if model_name not in VIDEO4K_MODELS:
            raise ValueError("Unsupported Video4K model")
        if images.ndim != 4 or images.shape[-1] != 3 or images.shape[0] < 1:
            raise ValueError("Expected non-empty RGB IMAGE frames")
        if tile_size != 0 and (tile_size < 64 or tile_size > 1024 or tile_size % 32):
            raise ValueError("tile_size must be 0, or a multiple of 32 between 64 and 1024")
        path = folder_paths.get_full_path_or_raise("winx_video4k", model_name)
        model = Video4K(path, device)

        def run_tile(tile):
            comfy.model_management.throw_exception_if_processing_interrupted()
            return torch.from_numpy(model.upscale(tile.detach().cpu().numpy()))

        samples = images.detach().movedim(-1, 1).to(device="cpu", dtype=torch.float32)
        if tile_size:
            steps = samples.shape[0] * comfy.utils.get_tiled_scale_steps(
                samples.shape[3], samples.shape[2], tile_size, tile_size, 32)
            result = comfy.utils.tiled_scale(samples, run_tile, tile_x=tile_size, tile_y=tile_size,
                                             overlap=32, upscale_amount=2, out_channels=3,
                                             output_device="cpu", pbar=comfy.utils.ProgressBar(steps))
        else:
            progress = comfy.utils.ProgressBar(samples.shape[0])
            result = torch.empty((samples.shape[0], 3, samples.shape[2] * 2, samples.shape[3] * 2))
            for index in range(samples.shape[0]):
                result[index:index + 1] = run_tile(samples[index:index + 1])
                progress.update(1)
        return (result.movedim(1, -1),)


class WinxRife46:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "images": ("IMAGE",),
            "source_fps": ("FLOAT", {"default": 25.0, "min": 0.001, "max": 1000.0}),
            "multiplier": ("INT", {"default": 2, "min": 1, "max": 5}),
            "device": (["cuda", "cpu"],),
        }}

    RETURN_TYPES = ("IMAGE", "FLOAT")
    RETURN_NAMES = ("images", "frame_rate")
    FUNCTION = "interpolate"
    CATEGORY = "Winx Video4K"
    DESCRIPTION = "RIFE 4.6 ONNX. Holds the final frame so output duration matches input duration. Use complete clips, without VHS meta_batch."

    def interpolate(self, images, source_fps, multiplier, device):
        if images.ndim != 4 or images.shape[-1] != 3 or images.shape[0] < 1:
            raise ValueError("Expected non-empty RGB IMAGE frames")
        if not math.isfinite(source_fps) or source_fps <= 0 or multiplier not in (1, 2, 3, 4, 5):
            raise ValueError("Positive source_fps and integer multiplier from 1 to 5 required")
        frames = images.detach().to(device="cpu", dtype=torch.float32)
        if multiplier == 1:
            return (frames, float(source_fps))
        count, h, w, _ = frames.shape
        result = torch.empty((count * multiplier, h, w, 3), dtype=torch.float32)
        if count > 1:
            path = folder_paths.get_full_path_or_raise("winx_video4k", RIFE_MODEL)
            model = Rife46(path, device)
            progress = comfy.utils.ProgressBar((count - 1) * (multiplier - 1))
            for index in range(count - 1):
                result[index * multiplier] = frames[index]
                first = frames[index:index + 1].movedim(-1, 1).numpy()
                second = frames[index + 1:index + 2].movedim(-1, 1).numpy()
                for step in range(1, multiplier):
                    comfy.model_management.throw_exception_if_processing_interrupted()
                    middle = model.interpolate(first, second, step / multiplier)
                    result[index * multiplier + step] = torch.from_numpy(middle).movedim(1, -1)[0]
                    progress.update(1)
        # Keep n/fps seconds, including the last frame's display interval.
        result[(count - 1) * multiplier:] = frames[-1]
        return (result, float(source_fps * multiplier))


NODE_CLASS_MAPPINGS = {"WinxVideo4KUpscale": WinxVideo4KUpscale, "WinxRife46": WinxRife46, "WinxVideoApp": WinxVideoApp}
NODE_DISPLAY_NAME_MAPPINGS = {
    "WinxVideo4KUpscale": "Video4K V9/V10 · 2x (ONNX)",
    "WinxRife46": "RIFE 4.6 · Frame Interpolation (ONNX)",
    "WinxVideoApp": "Winx Video App · Streaming Enhance + RIFE",
}
