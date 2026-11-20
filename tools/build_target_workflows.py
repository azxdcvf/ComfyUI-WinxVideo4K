"""Reuse the existing streaming graph; preserve all previous workflow exports."""
import json
from pathlib import Path

from build_app_workflows import DEFAULTS


ROOT = Path(__file__).resolve().parent.parent


def build():
    for suffix, seconds in (("Preview", 2.0), ("Full", 0.0)):
        settings = {**DEFAULTS, "output_scale": "1.5x", "preview_seconds": seconds,
                    "target_fps": 48, "max_source_seconds": 25}
        graph = json.loads((ROOT / "examples" / "Winx_App_Fast_Preview.json").read_text(encoding="utf-8"))
        node, note = graph["nodes"]
        node.update(title="上传视频 · 1.5倍尺寸 / 48fps真实插帧", size=[580, 730],
                    widgets_values=list(settings.values()))
        note.update(title="新版参数 · 2026-11-20", size=[730, 510])
        note["widgets_values"] = [
            ("只处理源片前2秒，先检查效果。\n" if seconds else "处理整片；云端运行会计费。\n")
            + "默认宽高各1.5倍、目标48fps、fast增强、CUDA、防抖关闭。\n"
            + "输出尺寸和清晰度不同：1.5x是宽高各乘1.5，像素量约2.25倍，不代表清晰度增加50%。\n"
            + "output_scale可改source（原尺寸）、1.5x、2x或其他尺寸。\n"
            + "target_fps=48直接按输出时间戳进行真实RIFE插帧，如30→48、24→48。\n"
            + "目标帧率低于/等于源帧率时采用丢帧/保留原帧，不运行RIFE。\n"
            + "target_fps=0才使用interpolation整数倍率，2代表30→60、24→48。\n"
            + "fast的AI输入长边至多640、插帧至多1280，更大输出含普通缩放；quality使用原尺寸AI输入、更慢。\n"
            + "max_source_seconds=25限制上传源片，超过25秒会在AI推理前拒绝，即使只预览2秒也一样。\n"
            + "48fps的非整数转换不保证比60fps快，实际速度取决于所需RIFE调用和处理尺寸。\n"
            + "15秒片在10分钟内完成尚未在这些新参数下云测，不能作为保证。旧工作流保留。"
        ]
        api = {"200": {"class_type": "WinxVideoApp", "inputs": settings}}
        name = f"Winx_App_1p5x_48fps_{suffix}"
        for filename, data in ((name + ".json", graph), (name + "_API.json", api)):
            (ROOT / "examples" / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                                                     encoding="utf-8", newline="\n")
        assert node["widgets_values"] == list(api["200"]["inputs"].values())
        assert settings["target_fps"] == 48 and settings["max_source_seconds"] == 25
    print("Created 1.5x / 48fps preview and full workflows, plus API copies; previous exports preserved.")


if __name__ == "__main__":
    build()
