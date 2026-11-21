"""Expose an already encoded Winx MP4 as a native ComfyUI VIDEO without decoding it."""
from pathlib import Path

import folder_paths


class WinxVideoFromPath:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"file": ("STRING", {"forceInput": True})}}

    RETURN_TYPES = ("VIDEO",)
    RETURN_NAMES = ("video",)
    FUNCTION = "load_video"
    CATEGORY = "Winx Video4K"
    DESCRIPTION = "Wrap a generated output video for SaveVideo; preserves its audio and encoded frames."

    def load_video(self, file):
        if not isinstance(file, str) or not file:
            raise ValueError("A generated video file path is required")
        path = Path(file).resolve()
        if not path.is_relative_to(Path(folder_paths.get_output_directory()).resolve()) or not path.is_file():
            raise ValueError("Select a generated video inside the ComfyUI output directory")
        from comfy_api.latest import InputImpl
        return (InputImpl.VideoFromFile(str(path)),)
