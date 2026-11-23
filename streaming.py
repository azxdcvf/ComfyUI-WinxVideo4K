"""File-based video processing; only adjacent frames are held in Python memory."""
import json
import math
import os
import shutil
import subprocess
import tempfile
import time
import uuid
import zipfile
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch

import comfy.model_management
import comfy.utils
import folder_paths

from .runtime import RIFE_MODEL, VIDEO4K_MODELS, Rife46, Video4K


VIDEO_EXTENSIONS = {"mp4", "mkv", "mov", "avi", "webm", "m4v", "mpeg", "mpg", "ts", "m2ts"}
OUTPUT_SCALES = ["1280_long_edge", "source", "1.5x", "2x", "3x", "4x", "720p", "1080p", "1440p", "2160p"]


def _output_ui(final, subfolder, frame_rate, zip_output=False):
    if not zip_output:
        return {"gifs": [dict(filename=final.name, subfolder=subfolder, type="output",
                              format="video/h264-mp4", frame_rate=float(frame_rate), fullpath=str(final))]}
    archive = final.with_suffix(".zip")
    temporary = archive.with_suffix(".part.zip")
    try:
        # MP4 is already compressed. Store its bytes without encoding the video again.
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as bundle:
            bundle.write(final, arcname=final.name)
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    # Same file descriptor used by the installed solarL SaveImagesToZip node.
    return {"images": [dict(filename=archive.name, subfolder=subfolder, type="output")]}


def _video_path(video):
    if not isinstance(video, str) or not video:
        raise ValueError("Select a video uploaded into the ComfyUI input directory")
    path = Path(folder_paths.get_annotated_filepath(video)).resolve()
    if not path.is_relative_to(Path(folder_paths.get_input_directory()).resolve()) or not path.is_file():
        raise ValueError("Select a video uploaded into the ComfyUI input directory")
    if path.suffix.lower().lstrip(".") not in VIDEO_EXTENSIONS:
        raise ValueError("Unsupported video extension")
    return path


def _even(value):
    return max(2, round(value / 2) * 2)


def _fit_size(width, height, long_edge):
    ratio = min(1, long_edge / max(width, height))
    return _even(width * ratio), _even(height * ratio)


def _target_size(width, height, mode):
    if mode == "source":
        ratio = 1
    elif mode == "1280_long_edge":
        ratio = 1280 / max(width, height)
    elif mode in ("1.5x", "2x", "3x", "4x"):
        ratio = float(mode[:-1])
    else:
        ratio = int(mode[:-1]) / min(width, height)
    return _even(width * ratio), _even(height * ratio)


def _audio_atempo(multiplier):
    factors = []
    remaining = 1 / multiplier
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    if remaining != 1:
        factors.append(remaining)
    return factors


def _scene_cut(previous, current, threshold=0.28):
    # A heuristic: flashes and very rapid motion can also exceed the threshold.
    stride = max(1, max(previous.shape[:2]) // 64)
    a = previous[::stride, ::stride].astype(np.float32)
    b = current[::stride, ::stride].astype(np.float32)
    return float(np.mean(np.abs(a - b)) / 255) >= threshold


class _Process:
    """Keep stderr off pipes and reap every child on success, failure or cancel."""
    def __init__(self, args, **kwargs):
        self.log = tempfile.TemporaryFile()
        try:
            self.process = subprocess.Popen(
                args, stderr=self.log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                **kwargs,
            )
        except BaseException:
            self.log.close()
            raise

    def __enter__(self):
        return self

    def error(self):
        self.log.seek(max(0, self.log.seek(0, 2) - 4000))
        return self.log.read().decode("utf-8", errors="replace").strip()

    def wait(self):
        while self.process.poll() is None:
            comfy.model_management.throw_exception_if_processing_interrupted()
            time.sleep(0.1)
        if self.process.returncode:
            raise RuntimeError("FFmpeg/ffprobe failed: " + self.error())

    def __exit__(self, *exc):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None and not stream.closed:
                try:
                    stream.close()
                except OSError:
                    pass
        self.log.close()


def _capture(args, timeout=30):
    with _Process(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE) as child:
        deadline = time.monotonic() + timeout
        while True:
            comfy.model_management.throw_exception_if_processing_interrupted()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("FFmpeg/ffprobe inspection exceeded its time limit")
            try:
                value, _ = child.process.communicate(timeout=min(0.2, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
        child.wait()
    return value.decode("utf-8", errors="replace")


def _ffmpeg_paths():
    ffmpeg = os.environ.get("WINX_FFMPEG_PATH") or os.environ.get("VHS_FORCE_FFMPEG_PATH") or shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            from imageio_ffmpeg import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
        except ImportError:
            pass
    if not ffmpeg or not Path(ffmpeg).is_file():
        raise RuntimeError("Install FFmpeg or set WINX_FFMPEG_PATH")
    sibling = Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix)
    ffprobe = (os.environ.get("WINX_FFPROBE_PATH") or os.environ.get("VHS_FORCE_FFPROBE_PATH")
               or (str(sibling) if sibling.is_file() else shutil.which("ffprobe")))
    if not ffprobe or not Path(ffprobe).is_file():
        raise RuntimeError("Install ffprobe or set WINX_FFPROBE_PATH")
    return str(ffmpeg), str(ffprobe)


def _probe(ffprobe, path):
    data = json.loads(_capture([ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    video = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    audio = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)
    if video is None:
        raise ValueError("Uploaded file has no video stream")
    rate = video.get("avg_frame_rate")
    if rate in (None, "0/0"):
        rate = video.get("r_frame_rate")
    try:
        fps = Fraction(rate)
    except (ValueError, TypeError, ZeroDivisionError) as error:
        raise ValueError("Cannot determine the source video frame rate") from error
    if not 0 < fps <= 1000:
        raise ValueError("Source video frame rate must be between 0 and 1000")
    sar = video.get("sample_aspect_ratio", "1:1")
    try:
        sar = float(Fraction(sar.replace(":", "/")))
    except (ValueError, ZeroDivisionError):
        sar = 1
    width, height = video["width"] * (sar or 1), video["height"]
    rotation = float(video.get("tags", {}).get("rotate", 0))
    for item in video.get("side_data_list", []):
        if "rotation" in item:
            rotation = float(item["rotation"])
    if round(rotation) % 180 == 90:
        width, height = height, width
    duration = float(video.get("duration") or data.get("format", {}).get("duration") or 0)
    audio_offset = float(audio.get("start_time", 0)) - float(video.get("start_time", 0)) if audio else 0
    return dict(width=_even(width), height=_even(height), fps=fps, duration=duration,
                audio=audio is not None, audio_offset=audio_offset)


def _check_stabilization(ffmpeg, mode):
    required = {"off": (), "fast": ("deshake",), "two_pass": ("vidstabdetect", "vidstabtransform")}[mode]
    if required:
        available = _capture([ffmpeg, "-hide_banner", "-filters"])
        names = {parts[1] for line in available.splitlines() if len(parts := line.split()) >= 2}
        missing = set(required) - names
        if missing:
            raise RuntimeError("FFmpeg lacks stabilization filters: " + ", ".join(sorted(missing)))


def _encoder_args(encoder, crf):
    if encoder == "h264_nvenc":
        return ["-c:v", encoder, "-preset", "p4", "-rc", "vbr", "-cq", str(crf), "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), "-threads", "4"]


def _choose_encoder(ffmpeg, encoder, crf):
    if encoder == "libx264":
        return encoder
    # Listing the encoder is insufficient: the worker must actually support it.
    try:
        _capture([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=size=32x32:rate=1",
                  "-frames:v", "1", *_encoder_args("h264_nvenc", crf), "-f", "null", "-"])
    except RuntimeError:
        if encoder == "h264_nvenc":
            raise
        return "libx264"
    return "h264_nvenc"


def _resize(frame, size):
    width, height = size
    if frame.shape[:2] == (height, width):
        return frame
    tensor = torch.from_numpy(np.ascontiguousarray(frame.transpose(2, 0, 1)[None]))
    result = torch.nn.functional.interpolate(tensor, size=(height, width), mode="bicubic", align_corners=False)
    return result[0].numpy().transpose(1, 2, 0).clip(0, 1)


def _enhance_frame(model, frame, tile_size):
    samples = torch.from_numpy(np.ascontiguousarray(frame.transpose(2, 0, 1)[None])).float()
    def run_tile(tile):
        comfy.model_management.throw_exception_if_processing_interrupted()
        return torch.from_numpy(model.upscale(tile.numpy()))
    if tile_size:
        result = comfy.utils.tiled_scale(samples, run_tile, tile_x=tile_size, tile_y=tile_size,
                                        overlap=32, upscale_amount=2, out_channels=3, output_device="cpu")
    else:
        result = run_tile(samples)
    return result[0].numpy().transpose(1, 2, 0).clip(0, 1)


def _rife_pair(previous, current):
    def padded(frame):
        height, width = frame.shape[:2]
        frame = np.pad(frame, ((0, (-height) % 32), (0, (-width) % 32), (0, 0)), mode="edge")
        return np.ascontiguousarray(frame.transpose(2, 0, 1)[None], dtype=np.float32)
    return padded(previous), padded(current)


class WinxVideoApp:
    @classmethod
    def INPUT_TYPES(cls):
        files = [p.name for p in Path(folder_paths.get_input_directory()).iterdir()
                 if p.is_file() and p.suffix.lower().lstrip(".") in VIDEO_EXTENSIONS]
        return {"required": {
            "video": (sorted(files), {"video_upload": True}),
            "enhancement": (["fast", "quality", "off"], {"default": "fast", "tooltip": "fast: AI input long edge <=640; quality: native input; off: resize/interpolate only."}),
            "model_name": (list(VIDEO4K_MODELS),),
            "output_scale": (OUTPUT_SCALES, {"default": "1280_long_edge", "tooltip": "p denotes the short edge and preserves portrait/landscape orientation. 3x/4x use ordinary resizing above the 2x AI model."}),
            "interpolation": ("INT", {"default": 2, "min": 1, "max": 5, "tooltip": "Real RIFE frames. 1 disables interpolation; normal output FPS = source FPS x multiplier."}),
            "slow_motion": ("BOOLEAN", {"default": False, "tooltip": "Play inserted frames at source FPS. Audio is stretched while preserving pitch."}),
            "skip_scene_transitions": ("BOOLEAN", {"default": True, "tooltip": "Heuristic hard-cut detection; holds frames across cuts. Flashes may also trigger it."}),
            "stabilization": (["off", "fast", "two_pass"], {"default": "off"}),
            "preview_seconds": ("FLOAT", {"default": 2, "min": 0, "max": 3600, "step": 0.5, "tooltip": "Source seconds to process; 0 processes the full clip. Slow motion lengthens the output."}),
            "tile_size": ("INT", {"default": 512, "min": 0, "max": 1024, "step": 32}),
            "device": (["cuda", "cpu"],),
            "crf": ("INT", {"default": 20, "min": 0, "max": 51}),
            "encoder": (["auto", "libx264", "h264_nvenc"], {"default": "auto"}),
        }, "optional": {
            # Append fields so existing serialized widgets keep their positions.
            "target_fps": ("INT", {"default": 0, "min": 0, "max": 120, "tooltip": "1-120: exact output FPS, overrides interpolation. 0: legacy integer multiplier. Cannot combine with slow motion. Lower/equal FPS drops/keeps frames without RIFE."}),
            "max_source_seconds": ("INT", {"default": 0, "min": 0, "max": 25, "tooltip": "Reject longer uploaded videos before AI processing, even in preview mode. 0: no duration limit for legacy workflows."}),
            "zip_output": ("BOOLEAN", {"default": False, "label_on": "ZIP", "label_off": "MP4", "tooltip": "Off: return one MP4. On: return one ZIP containing the finished MP4 without re-encoding. Remove downstream SaveVideo nodes to avoid duplicate application outputs."}),
        }}

    RETURN_TYPES = ("VHS_FILENAMES", "STRING")
    RETURN_NAMES = ("video", "report")
    FUNCTION = "process"
    OUTPUT_NODE = True
    CATEGORY = "Winx Video4K"
    DESCRIPTION = "File-based enhancement and real RIFE interpolation. Defaults to a two-second fast preview."

    @classmethod
    def VALIDATE_INPUTS(cls, video, **kwargs):
        # ComfyUI supplies None for linked values before their upstream nodes execute.
        if video is None:
            return True
        try:
            _video_path(video)
        except (ValueError, OSError) as error:
            return str(error)
        return True

    @classmethod
    def IS_CHANGED(cls, video, **kwargs):
        if video is None:
            return float("nan")
        stat = _video_path(video).stat()
        return f"{stat.st_mtime_ns}:{stat.st_size}"

    def process(self, video, enhancement, model_name, output_scale, interpolation,
                slow_motion, skip_scene_transitions, stabilization, preview_seconds,
                tile_size, device, crf, encoder="auto", target_fps=0, max_source_seconds=0,
                zip_output=False):
        if not isinstance(zip_output, bool):
            raise ValueError("zip_output must be a boolean")
        if enhancement not in ("fast", "quality", "off") or output_scale not in OUTPUT_SCALES:
            raise ValueError("Invalid enhancement or output scale")
        if model_name not in VIDEO4K_MODELS or device not in ("cuda", "cpu"):
            raise ValueError("Invalid model or device")
        if stabilization not in ("off", "fast", "two_pass") or encoder not in ("auto", "libx264", "h264_nvenc"):
            raise ValueError("Invalid stabilization or encoder")
        if not isinstance(interpolation, int) or not 1 <= interpolation <= 5:
            raise ValueError("interpolation must be an integer from 1 to 5")
        if not isinstance(target_fps, int) or not 0 <= target_fps <= 120:
            raise ValueError("target_fps must be an integer from 0 to 120")
        if target_fps and slow_motion:
            raise ValueError("Exact target_fps requires slow_motion=false; use target_fps=0 for legacy slow motion")
        if not isinstance(max_source_seconds, int) or not 0 <= max_source_seconds <= 25:
            raise ValueError("max_source_seconds must be an integer from 0 to 25")
        if tile_size != 0 and (not 64 <= tile_size <= 1024 or tile_size % 32):
            raise ValueError("tile_size must be 0 or a multiple of 32 from 64 to 1024")
        if not math.isfinite(preview_seconds) or not 0 <= preview_seconds <= 3600 or not 0 <= crf <= 51:
            raise ValueError("Invalid preview_seconds or crf")
        started = time.monotonic()
        source = _video_path(video)
        ffmpeg, ffprobe = _ffmpeg_paths()
        info = _probe(ffprobe, source)
        if max_source_seconds and (not math.isfinite(info["duration"]) or not 0 < info["duration"] <= max_source_seconds):
            raise ValueError(f"Uploaded video must have a known duration of at most {max_source_seconds} seconds; trim the source first")
        output_size = _target_size(info["width"], info["height"], output_scale)
        if max(output_size) > 16384:
            raise ValueError("Output exceeds 16384 pixels on one edge")
        target_edge = max(output_size)
        input_edge = min(640, target_edge / 2) if enhancement == "fast" else max(info["width"], info["height"])
        if enhancement == "off":
            input_edge = min(input_edge, target_edge)
        working_size = _fit_size(info["width"], info["height"], input_edge)
        ai_size = tuple(size * 2 for size in working_size) if enhancement != "off" else working_size
        interpolation_size = _fit_size(*ai_size, min(target_edge, max(ai_size)))
        source_fps = info["fps"]
        sample_ratio = Fraction(target_fps, 1) / source_fps if target_fps else Fraction(interpolation, 1)
        output_fps = source_fps if slow_motion else source_fps * sample_ratio
        limit = math.ceil(preview_seconds * source_fps) if preview_seconds else None
        expected = limit or math.ceil(info["duration"] * source_fps) or 1
        progress = comfy.utils.ProgressBar(expected)
        _check_stabilization(ffmpeg, stabilization)
        encoder = _choose_encoder(ffmpeg, encoder, crf)
        # One session per active video, reused for every frame/tile.
        model = Video4K(folder_paths.get_full_path_or_raise("winx_video4k", model_name), device) if enhancement != "off" else None
        rife = Rife46(folder_paths.get_full_path_or_raise("winx_video4k", RIFE_MODEL), device) if sample_ratio > 1 else None

        width, height = working_size
        rate = f"{source_fps.numerator}/{source_fps.denominator}"
        common_filters = f"setpts=PTS-STARTPTS,fps={rate},scale={width}:{height}:flags=lanczos,setsar=1"
        decode_base = [ffmpeg, "-v", "error", "-threads", "2", "-i", str(source), "-map", "0:v:0", "-an", "-sn", "-dn", "-filter_threads", "2"]
        frame_limit = ["-frames:v", str(limit)] if limit else []
        Path(folder_paths.get_temp_directory()).mkdir(parents=True, exist_ok=True)
        final_part = None
        with tempfile.TemporaryDirectory(prefix="winxvideoapp-", dir=folder_paths.get_temp_directory()) as temp:
            try:
                filters = common_filters
                if stabilization == "two_pass":
                    # Relative filter paths avoid Windows drive-letter escaping.
                    analysis = decode_base + ["-vf", filters + ",vidstabdetect=shakiness=5:accuracy=9:result=transforms.trf", *frame_limit, "-f", "null", "-"]
                    with _Process(analysis, cwd=temp, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL) as child:
                        child.wait()
                    filters += ",vidstabtransform=input=transforms.trf:smoothing=10:optalgo=gauss:crop=keep"
                elif stabilization == "fast":
                    filters += ",deshake=rx=16:ry=16:search=less:edge=mirror"
                decode_args = decode_base + ["-vf", filters, *frame_limit, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
                silent = Path(temp) / "silent.mp4"
                iw, ih = interpolation_size
                ow, oh = output_size
                encode_args = [ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                               "-s", f"{iw}x{ih}", "-r", f"{output_fps.numerator}/{output_fps.denominator}", "-i", "pipe:0", "-an"]
                if interpolation_size != output_size:
                    encode_args += ["-filter_threads", "2", "-vf", f"scale={ow}:{oh}:flags=lanczos"]
                encode_args += [*_encoder_args(encoder, crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(silent)]
                count = emitted = cuts = rife_inferences = 0
                with _Process(decode_args, cwd=temp, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE) as decoder, \
                        _Process(encode_args, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL) as writer:
                    def emit(frame):
                        nonlocal emitted
                        comfy.model_management.throw_exception_if_processing_interrupted()
                        pixels = np.ascontiguousarray((frame.clip(0, 1) * 255).round(), dtype=np.uint8)
                        try:
                            writer.process.stdin.write(pixels.tobytes())
                        except (BrokenPipeError, OSError) as error:
                            raise RuntimeError("FFmpeg encoder stopped: " + writer.error()) from error
                        emitted += 1

                    previous = previous_source = None
                    while True:
                        comfy.model_management.throw_exception_if_processing_interrupted()
                        raw = decoder.process.stdout.read(width * height * 3)
                        if not raw:
                            break
                        if len(raw) != width * height * 3:
                            raise RuntimeError("FFmpeg returned a partial RGB frame")
                        if max_source_seconds and Fraction(count, 1) / source_fps >= max_source_seconds:
                            raise ValueError("Decoded video exceeds max_source_seconds; no output was saved")
                        source_frame = np.frombuffer(raw, np.uint8).reshape(height, width, 3)
                        frame = source_frame.astype(np.float32) / 255
                        if model:
                            frame = _enhance_frame(model, frame, tile_size)
                        frame = _resize(frame, interpolation_size)
                        count += 1
                        if previous is not None:
                            cut = skip_scene_transitions and _scene_cut(previous_source, source_frame)
                            cuts += int(cut)
                            pair = None
                            # Map each output timestamp to its actual source interval.
                            while emitted < (count - 1) * sample_ratio:
                                comfy.model_management.throw_exception_if_processing_interrupted()
                                timestep = Fraction(emitted, 1) / sample_ratio - (count - 2)
                                if timestep == 0 or cut or sample_ratio <= 1:
                                    emit(previous)
                                else:
                                    if pair is None:
                                        pair = _rife_pair(previous, frame)
                                    middle = rife.interpolate(*pair, float(timestep))[0, :, :ih, :iw].transpose(1, 2, 0)
                                    rife_inferences += 1
                                    emit(middle)
                        previous, previous_source = frame, source_frame
                        progress.update(1)
                    if previous is None:
                        raise RuntimeError("No video frames decoded")
                    while emitted < count * sample_ratio:
                        emit(previous)
                    decoder.wait()
                    writer.process.stdin.close()
                    writer.wait()
                duration = emitted / output_fps
                directory, prefix, counter, subfolder, _ = folder_paths.get_save_image_path(
                    "WinxVideoApp_" + uuid.uuid4().hex[:8], folder_paths.get_output_directory(), ow, oh)
                final = Path(directory) / f"{prefix}_{counter:05}.mp4"
                final_part = final.with_suffix(".part.mp4")
                if info["audio"]:
                    audio_filters = ["asetpts=PTS-STARTPTS"]
                    offset = info["audio_offset"]
                    if offset < 0:
                        audio_filters += [f"atrim=start={-offset:.9f}", "asetpts=PTS-STARTPTS"]
                    elif offset > 0:
                        audio_filters += [f"adelay={offset * 1000:.6f}:all=1"]
                    if slow_motion:
                        audio_filters += [f"atempo={factor:.12g}" for factor in _audio_atempo(interpolation)]
                    audio_filters += ["apad"]
                    mux = [ffmpeg, "-y", "-v", "error", "-i", str(silent), "-i", str(source),
                           "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
                           "-af", ",".join(audio_filters), "-t", f"{float(duration):.12f}", "-movflags", "+faststart", str(final_part)]
                    with _Process(mux, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL) as child:
                        child.wait()
                else:
                    shutil.copyfile(silent, final_part)
                os.replace(final_part, final)
                report = {
                    "source_frames_decoded": count,
                    "source_fps": float(source_fps), "source_fps_fraction": str(source_fps),
                    "output": {"path": str(final), "width": ow, "height": oh, "frames": emitted,
                               "fps": float(output_fps), "fps_fraction": str(output_fps),
                               "duration": float(duration), "audio": info["audio"]},
                    "settings": {"enhancement": enhancement, "model": model_name if model else None,
                                 "zip_output": zip_output,
                                 "interpolation": interpolation, "slow_motion": slow_motion,
                                 "target_fps": target_fps, "resampling_ratio": str(sample_ratio),
                                 "rife_inferences": rife_inferences, "max_source_seconds": max_source_seconds,
                                 "stabilization": stabilization, "cuts_skipped": cuts, "preview_source_seconds": preview_seconds,
                                 "ai_input_size": working_size if model else None,
                                 "interpolation_size": interpolation_size, "encoder": encoder, "crf": crf, "device": device},
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "notes": ["VFR is normalized to CFR before interpolation.",
                              "Fast AI input long edge is at most 640; final resizing is conventional.",
                              "3x/4x dimensions use conventional resizing above the 2x AI model.",
                              "The final source display interval is held; exact target FPS rounds duration up by less than one output frame.",
                              "Target FPS at or below source FPS keeps/drops source frames without RIFE.",
                              "Non-integer FPS ratios can need more RIFE calls than a nearby integer multiplier."],
                }
                ui = _output_ui(final, subfolder, output_fps, zip_output)
                return {"ui": ui, "result": ((True, [str(final)]), json.dumps(report, ensure_ascii=False))}
            finally:
                if final_part is not None:
                    final_part.unlink(missing_ok=True)
