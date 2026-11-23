"""Check MP4/ZIP delivery with real ComfyUI, ONNX and FFmpeg; no cloud jobs."""
import argparse
import asyncio
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import zipfile
from fractions import Fraction
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("comfy", "models", "ffmpeg", "output"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--runtime-packages")
    args = parser.parse_args()
    sys.path.insert(0, args.comfy)
    if args.runtime_packages:
        sys.path.insert(0, args.runtime_packages)
    os.environ["WINX_FFMPEG_PATH"] = args.ffmpeg
    ffprobe = str(Path(args.ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe"))
    os.environ["WINX_FFPROBE_PATH"] = ffprobe
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
    spec = importlib.util.spec_from_file_location("winx_delivery_test", root / "__init__.py",
                                                submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    source = work / "input" / "delivery-source.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=96x64:rate=24:duration=0.25", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=0.25", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source)],
                   check=True, capture_output=True)
    import execution
    import nodes
    import server
    from comfy_extras.nodes_primitive import Boolean
    nodes.NODE_CLASS_MAPPINGS.update(package.NODE_CLASS_MAPPINGS)
    nodes.NODE_CLASS_MAPPINGS["PrimitiveBoolean"] = Boolean
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    prompt_server = server.PromptServer(loop)
    base = dict(video=source.name, enhancement="fast", model_name=package.VIDEO4K_MODELS[0],
                output_scale="1.5x", interpolation=2, slow_motion=False,
                skip_scene_transitions=True, stabilization="off", preview_seconds=25,
                tile_size=128, device="cpu", crf=20, encoder="libx264", target_fps=48,
                max_source_seconds=0)
    assert package.WinxVideoApp.INPUT_TYPES()["optional"]["zip_output"][1]["default"] is False
    checks = []
    # Missing optional field is the old API contract; linked booleans match the application.
    for mode in (None, False, True):
        prompt = {"200": {"class_type": "WinxVideoApp", "inputs": dict(base)}}
        if mode is not None:
            prompt["216"] = {"class_type": "PrimitiveBoolean", "inputs": {"value": mode}}
            prompt["200"]["inputs"]["zip_output"] = ["216", 0]
        task_id = "delivery-" + str(mode)
        valid = loop.run_until_complete(execution.validate_prompt(task_id, prompt, None))
        assert valid[0] and valid[2] == ["200"], valid
        before = set((work / "output").glob("*.mp4"))
        executor = execution.PromptExecutor(prompt_server, cache_type=execution.CacheType.NONE,
                                            cache_args={"lru": 0, "ram": 1.0, "ram_inactive": 1.0})
        loop.run_until_complete(executor.execute_async(prompt, task_id, {}, valid[2]))
        assert executor.success, executor.status_messages
        output_ui = executor.history_result["outputs"]
        assert set(output_ui) == {"200"}, output_ui
        ui = output_ui["200"]
        created = set((work / "output").glob("*.mp4")) - before
        assert len(created) == 1, created
        video_path = created.pop()
        probe = json.loads(subprocess.run([ffprobe, "-v", "error", "-show_streams", "-of", "json",
                                          str(video_path)], check=True, capture_output=True, text=True).stdout)
        video = next(s for s in probe["streams"] if s["codec_type"] == "video")
        assert (video["width"], video["height"]) == (144, 96), video
        assert Fraction(video["avg_frame_rate"]) == 48 and int(video["nb_frames"]) == 12, video
        assert any(s["codec_type"] == "audio" for s in probe["streams"]), probe
        if mode is True:
            assert set(ui) == {"images"} and len(ui["images"]) == 1, ui
            archive = work / "output" / ui["images"][0]["subfolder"] / ui["images"][0]["filename"]
            with zipfile.ZipFile(archive) as bundle:
                assert bundle.namelist() == [video_path.name], bundle.namelist()
                assert bundle.testzip() is None
                assert bundle.getinfo(video_path.name).compress_type == zipfile.ZIP_STORED
                assert hashlib.sha256(bundle.read(video_path.name)).digest() == hashlib.sha256(video_path.read_bytes()).digest()
        else:
            assert set(ui) == {"gifs"} and len(ui["gifs"]) == 1, ui
            assert ui["gifs"][0]["filename"] == video_path.name
            assert not video_path.with_suffix(".zip").exists()
        assert not list((work / "output").glob("*.part*"))
        checks.append({"switch": mode, "single_output": ui, "size": [144, 96], "fps": 48,
                       "frames": 12, "audio": True, "executor_success": True})
        print("PASS", task_id, flush=True)
    loop.close()
    evidence = {"status": "passed", "cases": checks, "device": "CPUExecutionProvider",
                "zip_bytes_match_mp4": True, "paid_task_submitted": False,
                "cloud_execution_verified": False}
    (work / "report.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
