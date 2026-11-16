"""Build separate streaming examples without modifying the legacy workflows."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = {
    "video": "upload_video.mp4",
    "enhancement": "fast",
    "model_name": "Video4K_V9_video_V9_x2_S2GAN_latest.onnx",
    "output_scale": "1280_long_edge",
    "interpolation": 2,
    "slow_motion": False,
    "skip_scene_transitions": True,
    "stabilization": "off",
    "preview_seconds": 2.0,
    "tile_size": 512,
    "device": "cuda",
    "crf": 20,
    "encoder": "auto",
}


def build():
    for name, seconds in (("Winx_App_Fast_Preview", 2.0), ("Winx_App_Fast_Full", 0.0)):
        settings = {**DEFAULTS, "preview_seconds": seconds}
        node = {
            "id": 200, "type": "WinxVideoApp", "title": "上传视频 · 画质 / 尺寸 / 插帧 / 防抖",
            "pos": [80, 80], "size": [530, 670], "flags": {}, "order": 0, "mode": 0,
            "inputs": [], "outputs": [{"name": "video", "type": "VHS_FILENAMES", "links": []},
                                        {"name": "report", "type": "STRING", "links": []}],
            "properties": {"Node name for S&R": "WinxVideoApp"}, "widgets_values": list(settings.values()),
        }
        note = {
            "id": 201, "type": "Note", "title": "运行前阅读 · 2026-11-17",
            "pos": [680, 80], "size": [660, 450], "flags": {}, "order": 1, "mode": 0, "properties": {},
            "widgets_values": [
                ("本文件只处理源片前2秒；先看效果和耗时。\n" if seconds else "本文件处理整片，会产生云端费用；先用 Preview 版本。\n")
                + "先让客服更新同一个 GitHub 仓库并注册 WinxVideoApp，再上传自己的视频。\n"
                + "enhancement: fast=AI输入长边至多640，quality=原尺寸增强，off=关闭AI增强。\n"
                + "output_scale: source=原尺寸，1280_long_edge=长边1280；720p等按短边计算并保持横竖方向。\n"
                + "interpolation: 1=关闭；2/3/4/5=真实RIFE插帧，通常保持时长。\n"
                + "slow_motion=true 才会延长时长，音频同步放慢并保持音调。\n"
                + "stabilization: off/fast/two_pass；两遍防抖需要FFmpeg的vidstab滤镜。\n"
                + "preview_seconds: 2=只处理源片前2秒；0=整片。默认CUDA，不自动把AI转到CPU。\n"
                + "快速模式和3/4倍尺寸含普通缩放；不承诺与Winx专有模型相同画质。\n"
                + "本地CPU小样通过不等于RunningHub/GPU速度已验证；不要直接提交高分辨率整片。"
            ],
        }
        graph = {"last_node_id": 201, "last_link_id": 0, "nodes": [node, note], "links": [], "groups": [],
                 "config": {}, "extra": {"ds": {"scale": 0.85, "offset": [30, 30]}}, "version": 0.4}
        api = {"200": {"class_type": "WinxVideoApp", "inputs": settings}}
        for filename, data in ((name + ".json", graph), (name + "_API.json", api)):
            (ROOT / "examples" / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                                     encoding="utf-8", newline="\n")
        assert node["widgets_values"] == list(api["200"]["inputs"].values())
        assert settings["device"] == "cuda" and settings["interpolation"] == 2
        assert graph["links"] == []
    print("Created 2 editor workflows and 2 API workflows; legacy examples preserved.")


if __name__ == "__main__":
    build()
