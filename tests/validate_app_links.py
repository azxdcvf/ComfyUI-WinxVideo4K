"""Validate linked video inputs with the real ComfyUI executor, locally only."""
import argparse
import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy", required=True)
    parser.add_argument("--runtime-packages")
    parser.add_argument("--models", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, args.comfy)
    if args.runtime_packages:
        sys.path.insert(0, args.runtime_packages)
    os.environ["WINX_FFMPEG_PATH"] = args.ffmpeg
    os.environ["WINX_FFPROBE_PATH"] = str(Path(args.ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe"))
    import torch
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    torch.set_num_threads(2)
    import folder_paths
    work = Path(args.output).resolve()
    for key, setter in (("input", folder_paths.set_input_directory),
                        ("output", folder_paths.set_output_directory),
                        ("temp", folder_paths.set_temp_directory)):
        path = work / key
        path.mkdir(parents=True, exist_ok=True)
        setter(str(path))
    os.environ["TEMP"] = os.environ["TMP"] = str(work / "temp")
    folder_paths.add_model_folder_path("winx_video4k", args.models)
    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("winx_app_link_test", root / "__init__.py",
                                                submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    source = work / "input" / "app-link-source.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=96x64:rate=24:duration=0.25", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=0.25", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source)],
                   check=True, capture_output=True)
    import execution
    import nodes
    import server

    # A runtime link recreates the production validator bug without a browser or cloud job.
    class LinkedFilename:
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"value": ("STRING", {})}}

        RETURN_TYPES = ("*",)
        FUNCTION = "get"

        def get(self, value):
            return (value,)

    nodes.NODE_CLASS_MAPPINGS.update(package.NODE_CLASS_MAPPINGS)
    nodes.NODE_CLASS_MAPPINGS["WinxTestLinkedFilename"] = LinkedFilename
    prompt = {
        "206": {"class_type": "WinxTestLinkedFilename", "inputs": {"value": source.name}},
        "200": {"class_type": "WinxVideoApp", "inputs": {
            "video": ["206", 0], "enhancement": "fast", "model_name": package.VIDEO4K_MODELS[0],
            "output_scale": "1.5x", "interpolation": 2, "slow_motion": False,
            "skip_scene_transitions": True, "stabilization": "off", "preview_seconds": 25.0,
            "tile_size": 128, "device": "cpu", "crf": 20, "encoder": "libx264",
            "target_fps": 48, "max_source_seconds": 0}},
    }
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    validation = loop.run_until_complete(execution.validate_prompt("winx-linked-video", prompt, None))
    evidence = {"validation": validation, "paid_task_submitted": False}
    (work / "link-validation.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    assert validation[0], json.dumps(validation, ensure_ascii=False)
    print("PASS linked WinxVideoApp validation", flush=True)
    if args.validate_only:
        loop.close()
        return

    from comfy_extras.nodes_video import SaveVideo
    nodes.NODE_CLASS_MAPPINGS["SaveVideo"] = SaveVideo
    prompt.update({
        "203": {"class_type": "WinxTestOutputFilename", "inputs": {"filenames": ["200", 0]}},
        "204": {"class_type": "WinxVideoFromPath", "inputs": {"file": ["203", 0]}},
        "205": {"class_type": "SaveVideo", "inputs": {
            "video": ["204", 0], "filename_prefix": "app-link/result", "format": "mp4", "codec": "auto"}},
    })

    class OutputFilename:
        @classmethod
        def INPUT_TYPES(cls):
            return {"required": {"filenames": ("VHS_FILENAMES",)}}

        RETURN_TYPES = ("STRING",)
        FUNCTION = "get"

        def get(self, filenames):
            return (filenames[1][-1],)

    nodes.NODE_CLASS_MAPPINGS["WinxTestOutputFilename"] = OutputFilename
    validation = loop.run_until_complete(execution.validate_prompt("winx-native-app-output", prompt, None))
    assert validation[0], validation
    assert package.WinxVideoApp.VALIDATE_INPUTS(source.name) is True
    assert package.WinxVideoApp.VALIDATE_INPUTS("missing.mp4") is not True
    assert package.WinxVideoApp.VALIDATE_INPUTS("../outside.mp4") is not True
    assert package.WinxVideoApp.IS_CHANGED(None) != package.WinxVideoApp.IS_CHANGED(None)
    for invalid in (None, "", "missing.mp4", "../outside.mp4"):
        try:
            package.WinxVideoFromPath().load_video(invalid)
        except (ValueError, OSError):
            pass
        else:
            raise AssertionError(f"Invalid output path accepted: {invalid!r}")
    prompt_server = server.PromptServer(loop)
    executor = execution.PromptExecutor(prompt_server, cache_type=execution.CacheType.NONE,
                                        cache_args={"lru": 0, "ram": 1.0, "ram_inactive": 1.0})
    loop.run_until_complete(executor.execute_async(prompt, "winx-native-app-output", {}, validation[2]))
    assert executor.success, executor.status_messages
    saved = list((work / "output" / "app-link").glob("*.mp4"))
    assert len(saved) == 1, saved
    probe = json.loads(subprocess.run([os.environ["WINX_FFPROBE_PATH"], "-v", "error", "-show_streams",
                                      "-of", "json", str(saved[0])], check=True, capture_output=True, text=True).stdout)
    video = next(s for s in probe["streams"] if s["codec_type"] == "video")
    assert (video["width"], video["height"]) == (144, 96), video
    assert Fraction(video["avg_frame_rate"]) == 48, video
    assert int(video["nb_frames"]) == 12, video
    assert abs(float(video["duration"]) - 0.25) < 0.001, video
    assert any(s["codec_type"] == "audio" for s in probe["streams"]), probe
    evidence.update({"status": "passed", "executor_success": True, "output": str(saved[0]),
                     "size": [144, 96], "fps": 48, "frames": 12, "audio": True,
                     "device": "CPUExecutionProvider", "cloud_execution_verified": False})
    (work / "report.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    loop.close()
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
