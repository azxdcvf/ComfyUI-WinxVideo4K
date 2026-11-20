"""Exercise real ComfyUI nodes/ONNX/FFmpeg on a tiny clip; never submits a cloud job."""
import argparse
import asyncio
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comfy", required=True)
    parser.add_argument("--models", required=True)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--ffprobe", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--runtime-packages")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, args.comfy)
    if args.runtime_packages:
        sys.path.insert(0, args.runtime_packages)
    os.environ["VHS_FORCE_FFMPEG_PATH"] = args.ffmpeg
    os.environ["VHS_FORCE_FFPROBE_PATH"] = args.ffprobe
    import torch
    import comfy.cli_args
    comfy.cli_args.args.cpu = True
    torch.set_num_threads(2)
    import folder_paths
    directory = Path(args.output)
    for name, setter in (("input", folder_paths.set_input_directory),
                         ("output", folder_paths.set_output_directory),
                         ("temp", folder_paths.set_temp_directory)):
        path = directory / name
        path.mkdir(parents=True, exist_ok=True)
        setter(str(path))
    folder_paths.add_model_folder_path("winx_video4k", args.models)
    spec = importlib.util.spec_from_file_location("winx_streaming_test", root / "__init__.py",
                                                submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    streaming = sys.modules["winx_streaming_test.streaming"]
    assert streaming._target_size(720, 1280, "1080p") == (1080, 1920), "Resolution must keep orientation"
    assert streaming._target_size(1080, 1920, "1.5x") == (1620, 2880)

    source = directory / "input" / "tiny.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=96x64:rate=5:duration=0.6", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=0.6",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source)],
                   check=True, capture_output=True)
    base = dict(video="tiny.mp4", enhancement="off", model_name=package.VIDEO4K_MODELS[0],
                output_scale="source", interpolation=2, slow_motion=False,
                skip_scene_transitions=False, stabilization="off", preview_seconds=0,
                tile_size=128, device="cpu", crf=18, encoder="libx264")
    checks = []
    rife_calls = []
    real_interpolate = streaming.Rife46.interpolate
    def counted_interpolate(self, first, second, timestep):
        rife_calls.append(timestep)
        return real_interpolate(self, first, second, timestep)
    streaming.Rife46.interpolate = counted_interpolate

    def validate_case(name, settings, expected_frames, expected_fps, expected_duration, expected_size=(96, 64), audio=True):
        rife_calls.clear()
        result = package.WinxVideoApp().process(**{**base, **settings})
        report = json.loads(result["result"][1])
        output = result["result"][0][1][-1]
        probe = subprocess.run([args.ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", output],
                               check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
        streams = json.loads(probe.stdout)["streams"]
        video = next(s for s in streams if s["codec_type"] == "video")
        from fractions import Fraction
        assert int(video["nb_frames"]) == expected_frames, (name, video)
        assert abs(float(Fraction(video["avg_frame_rate"])) - expected_fps) < 0.001, (name, video)
        assert abs(float(video["duration"]) - expected_duration) < 0.005, (name, video)
        assert (video["width"], video["height"]) == expected_size, (name, video)
        assert any(s["codec_type"] == "audio" for s in streams) == audio, (name, streams)
        if audio:
            audio_stream = next(s for s in streams if s["codec_type"] == "audio")
            assert abs(float(audio_stream["duration"]) - expected_duration) < 0.08, (name, audio_stream)
        assert report["output"]["frames"] == expected_frames, (name, report)
        assert report["settings"]["rife_inferences"] == len(rife_calls), (name, report)
        assert abs(report["output"]["duration"] - expected_duration) < 0.005, (name, report)
        checks.append({"case": name, "frames": expected_frames, "fps": expected_fps,
                       "duration": expected_duration, "size": expected_size, "audio": audio,
                       "actual_RIFE_inferences": len(rife_calls), "output": output})
        print("PASS", name, expected_frames, "frames", expected_fps, "fps", expected_duration, "seconds", flush=True)
        return result

    for multiplier in (1, 2, 3, 5):
        validate_case(f"real_RIFE_{multiplier}x", {"interpolation": multiplier}, 3 * multiplier, 5 * multiplier, 0.6)
        assert len(rife_calls) == 2 * (multiplier - 1), (multiplier, rife_calls)
    validate_case("slow_5x_with_stretched_audio", {"interpolation": 5, "slow_motion": True}, 15, 5, 3.0)
    validate_case("preview_0.4s", {"preview_seconds": 0.4}, 4, 10, 0.4)
    validate_case("V9_fast_2x", {"enhancement": "fast", "output_scale": "2x"}, 6, 10, 0.6, (192, 128))
    validate_case("V10_quality_source", {"enhancement": "quality", "interpolation": 1,
                                       "model_name": package.VIDEO4K_MODELS[1]}, 3, 5, 0.6)
    validate_case("fast_stabilization", {"stabilization": "fast", "interpolation": 1}, 3, 5, 0.6)
    rotated = directory / "input" / "rotated.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-i", str(source), "-c", "copy",
                    "-metadata:s:v:0", "rotate=90", str(rotated)], check=True, capture_output=True)
    validate_case("portrait_rotation", {"video": rotated.name, "interpolation": 1}, 3, 5, 0.6, (64, 96))
    cut_video = directory / "input" / "cut.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=black:size=96x64:rate=5:duration=0.6", "-vf", "negate=enable='gte(n,1)'",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cut_video)], check=True, capture_output=True)
    result = validate_case("skip_hard_cut_no_audio", {"video": cut_video.name, "interpolation": 3,
                                                   "skip_scene_transitions": True}, 9, 15, 0.6, audio=False)
    assert json.loads(result["result"][1])["settings"]["cuts_skipped"] == 1
    assert len(rife_calls) == 2, "Only the white-white pair should invoke RIFE"
    fractional = directory / "input" / "fractional.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=96x64:rate=30000/1001", "-frames:v", "3", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(fractional)], check=True, capture_output=True)
    validate_case("fractional_30000_1001fps", {"video": fractional.name, "interpolation": 3},
                  9, 90000 / 1001, 0.1001, audio=False)
    validate_case("auto_encoding", {"encoder": "auto", "interpolation": 1}, 3, 5, 0.6)

    # Non-integer FPS ratios must use the actual output timestamps, not rounded multipliers.
    fps30 = directory / "input" / "fps30.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=96x64:rate=30", "-frames:v", "5", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(fps30)], check=True, capture_output=True)
    validate_case("exact_30_to_48fps", {"video": fps30.name, "target_fps": 48},
                  8, 48, 8 / 48, audio=False)
    assert rife_calls == [0.625, 0.25, 0.875, 0.5, 0.125, 0.75], rife_calls
    validate_case("V9_fast_1p5x_exact48", {"video": fps30.name, "enhancement": "fast",
                  "output_scale": "1.5x", "target_fps": 48, "max_source_seconds": 25},
                  8, 48, 8 / 48, (144, 96), audio=False)
    validate_case("exact48_with_audio_and_rounding", {"target_fps": 48},
                  29, 48, 29 / 48)
    validate_case("exact_fractional_source_to_48fps", {"video": fractional.name, "target_fps": 48},
                  5, 48, 5 / 48, audio=False)
    assert all(0 < t < 1 for t in rife_calls), rife_calls
    validate_case("target_fps_drops_without_RIFE", {"video": fps30.name, "target_fps": 24},
                  4, 24, 4 / 24, audio=False)
    assert not rife_calls
    validate_case("target_fps_same_as_source", {"video": fps30.name, "target_fps": 30},
                  5, 30, 5 / 30, audio=False)
    assert not rife_calls
    validate_case("exact_fps_hard_cut", {"video": cut_video.name, "target_fps": 8,
                  "skip_scene_transitions": True}, 5, 8, 5 / 8, audio=False)
    assert rife_calls == [0.25, 0.875], rife_calls

    boundary_video = directory / "input" / "25seconds.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=black:size=32x32:rate=1:duration=25", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(boundary_video)], check=True, capture_output=True)
    validate_case("accept_exactly_25s_source", {"video": boundary_video.name, "target_fps": 1,
                  "max_source_seconds": 25}, 25, 1, 25, (32, 32), audio=False)
    long_video = directory / "input" / "26seconds.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=black:size=32x32:rate=1:duration=26", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(long_video)], check=True, capture_output=True)
    real_model_init = streaming.Video4K
    def forbidden_model_init(*args, **kwargs):
        raise AssertionError("Overlong source must be rejected before loading AI models")
    streaming.Video4K = forbidden_model_init
    try:
        package.WinxVideoApp().process(**{**base, "video": long_video.name, "enhancement": "fast",
                                         "target_fps": 48, "max_source_seconds": 25, "preview_seconds": 2})
    except ValueError as error:
        assert "at most 25 seconds" in str(error), error
    else:
        raise AssertionError("26-second source was accepted by the 25-second preset")
    finally:
        streaming.Video4K = real_model_init
    try:
        package.WinxVideoApp().process(**{**base, "target_fps": 48, "slow_motion": True})
    except ValueError as error:
        assert "slow_motion=false" in str(error), error
    else:
        raise AssertionError("Conflicting target FPS and slow motion must be rejected")
    offset_video = directory / "input" / "offset_audio.mp4"
    subprocess.run([args.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=96x64:rate=5:duration=0.6", "-itsoffset", "0.2",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=0.4",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", "0.6",
                    str(offset_video)], check=True, capture_output=True)
    result = validate_case("slow_motion_preserves_audio_offset", {"video": offset_video.name, "slow_motion": True},
                           6, 5, 1.2)
    audio_output = subprocess.run([args.ffmpeg, "-v", "error", "-i", result["result"][0][1][-1],
                                   "-vn", "-ac", "1", "-ar", "48000", "-f", "f32le", "pipe:1"],
                                  check=True, capture_output=True).stdout

    import numpy as np
    audible = np.flatnonzero(np.abs(np.frombuffer(audio_output, dtype="<f4")) > 0.02)
    assert len(audible) and abs(audible[0] / 48000 - 0.4) < 0.08, "Audio offset must stretch with slow-motion video"
    assert streaming._scene_cut(np.zeros((64, 96, 3), np.uint8), np.full((64, 96, 3), 255, np.uint8))
    assert not streaming._scene_cut(np.zeros((64, 96, 3), np.uint8), np.full((64, 96, 3), 5, np.uint8))
    assert abs(__import__("math").prod(streaming._audio_atempo(5)) - 0.2) < 1e-8
    assert package.WinxVideoApp.VALIDATE_INPUTS("../outside.mp4") is not True
    try:
        streaming._capture([sys.executable, "-c", "import time; time.sleep(3)"], timeout=0.1)
    except TimeoutError:
        pass
    else:
        raise AssertionError("Inspection timeout was not enforced")

    # Verify cancellation cannot leave a new output or an FFmpeg child behind.
    before = set((directory / "output").glob("*.mp4"))
    original = streaming.comfy.model_management.throw_exception_if_processing_interrupted
    calls = 0
    tracked = []
    process_init = streaming._Process.__init__
    def tracked_init(self, *args, **kwargs):
        process_init(self, *args, **kwargs)
        tracked.append(self.process)
    streaming._Process.__init__ = tracked_init
    def interrupted():
        nonlocal calls
        if any(p.stdin is not None for p in tracked):
            calls += 1
            if calls >= 4:
                raise RuntimeError("test cancellation")
    streaming.comfy.model_management.throw_exception_if_processing_interrupted = interrupted
    try:
        try:
            package.WinxVideoApp().process(**base)
        except RuntimeError as error:
            assert str(error) == "test cancellation", error
        else:
            raise AssertionError("Cancellation was not propagated")
    finally:
        streaming.comfy.model_management.throw_exception_if_processing_interrupted = original
        streaming._Process.__init__ = process_init
    assert tracked and all(p.poll() is not None for p in tracked), "An FFmpeg child was not reaped"
    assert set((directory / "output").glob("*.mp4")) == before
    assert not list((directory / "temp").glob("winxvideoapp-*")), "Temporary files not cleaned"
    if not all(streaming._capture([args.ffmpeg, "-hide_banner", "-filters"]).find(name) >= 0
               for name in ("vidstabdetect", "vidstabtransform")):
        try:
            package.WinxVideoApp().process(**{**base, "stabilization": "two_pass"})
        except RuntimeError as error:
            assert "stabilization filters" in str(error), error
        else:
            raise AssertionError("Missing filters were not rejected")

    # The actual ComfyUI executor must validate and execute the new API graph.
    import nodes
    import server
    import execution
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    prompt_server = server.PromptServer(loop)
    nodes.NODE_CLASS_MAPPINGS.update(package.NODE_CLASS_MAPPINGS)
    workflow_path = root / "examples" / "Winx_App_Fast_Preview_API.json"
    prompt = json.loads(workflow_path.read_text(encoding="utf-8"))
    prompt["200"]["inputs"].update(base)
    prompt["200"]["inputs"]["interpolation"] = 1
    valid = loop.run_until_complete(execution.validate_prompt("streaming-local-test", prompt, None))
    assert valid[0], valid
    executor = execution.PromptExecutor(prompt_server, cache_type=execution.CacheType.NONE,
                                        cache_args={"lru": 0, "ram": 1.0, "ram_inactive": 1.0})
    loop.run_until_complete(executor.execute_async(prompt, "streaming-local-test", {}, valid[2]))
    assert executor.success, executor.status_messages
    target_prompt = json.loads((root / "examples" / "Winx_App_1p5x_48fps_Preview_API.json").read_text(encoding="utf-8"))
    target_prompt["200"]["inputs"].update(video=fps30.name, device="cpu", tile_size=128, encoder="libx264")
    valid = loop.run_until_complete(execution.validate_prompt("target-fps-local-test", target_prompt, None))
    assert valid[0], valid
    executor = execution.PromptExecutor(prompt_server, cache_type=execution.CacheType.NONE,
                                        cache_args={"lru": 0, "ram": 1.0, "ram_inactive": 1.0})
    loop.run_until_complete(executor.execute_async(target_prompt, "target-fps-local-test", {}, valid[2]))
    assert executor.success, executor.status_messages
    loop.close()
    report = {"status": "passed", "device": "CPUExecutionProvider", "cases": checks,
              "additional_checks": ["scene cut detection", "5x audio tempo", "path validation",
                                    "cancellation cleanup", "inspection timeout", "ComfyUI PromptExecutor",
                                    "1.5x dimensions", "exact 48fps timestamps", "25s source rejection before AI",
                                    "target FPS versus slow-motion validation", "new 48fps workflow PromptExecutor"],
              "not_tested": ["CUDA speed", "RunningHub deployment", "browser upload", "two-pass stabilization filters"]}
    (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
