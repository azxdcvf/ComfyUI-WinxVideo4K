# ComfyUI-WinxVideo4K

Video4K V9/V10 的画质增强、RIFE 4.6 的真实插帧，以及可调尺寸、慢动作和防抖的视频应用节点。用于搭建上传视频、处理并导出 MP4 的 ComfyUI / RunningHub 工作流。

**节点代码、示例工作流和安装说明位于仓库中，三份模型在 [模型下载页（Releases）](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/tag/models-20261116) 提供。** 克隆代码后仍需下载并安装模型。本仓库不是 Winx 官方项目，也不代表已复刻 Winx 软件的全部处理流程。

## 节点

| 注册类型 | 功能 | 主要参数 |
| --- | --- | --- |
| `WinxVideo4KUpscale` | Video4K V9/V10 ONNX，宽高各 2 倍 | `model_name`、`device`、`tile_size` |
| `WinxRife46` | RIFE 4.6 ONNX，1 至 5 倍帧率，旧版 IMAGE 接口 | `source_fps`、`multiplier`、`device` |
| `WinxVideoApp` | 文件流式处理、可调尺寸、目标帧率或 1–5 倍插帧、慢动作、硬切处理、防抖 | 上传视频和可调应用参数，输出 MP4 与运行报告 |

节点分类：`Winx Video4K`。

## 安装

将本仓库克隆到 `ComfyUI/custom_nodes/ComfyUI-WinxVideo4K/`，保证 `__init__.py` 直接位于该目录内。根目录布局已适配 Git 克隆安装，不需要再移动一层子目录。

```bash
cd "/替换为实际ComfyUI根目录/custom_nodes"
git clone https://github.com/azxdcvf/ComfyUI-WinxVideo4K.git
```

由运行环境维护者使用 **实际运行 ComfyUI 的 Python** 安装本仓库的 `requirements.txt`。当前依赖范围为 `onnxruntime-gpu>=1.20.0,<2.0`，应按目标环境 CUDA/cuDNN 兼容性选择并固定具体版本，不要直接升级平台的 PyTorch 或 CUDA。

请另外准备：

- 从 [Releases 下载模型整包](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/download/models-20261116/winx-video4k-models-20261116.zip)，将其中 `models/` 合并到 ComfyUI 根目录，最终三份模型应位于 `ComfyUI/models/winx_video4k/`；文件名和 SHA256 见 [模型清单](model_manifest.json) 与 [模型说明及单文件下载](docs/MODELS.md)。节点不会自动下载模型。
- [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) 及其依赖，用于视频读取、视频信息和视频合成。
- VHS 可调用的 FFmpeg，用于导出 H.264 MP4 和音频。

安装后重启实际执行任务的 ComfyUI 服务。RunningHub 维护者请参考 [云端安装与验收说明](docs/INSTALL_RUNNINGHUB.md)。

## 新增：1.5 倍尺寸 / 48fps 可调应用（2026-11-20）

新的 [2 秒预览](examples/Winx_App_1p5x_48fps_Preview.json) 和 [整片工作流](examples/Winx_App_1p5x_48fps_Full.json) 默认 `output_scale=1.5x`、`target_fps=48`、`enhancement=fast`、`max_source_seconds=25`，CUDA、防抖关闭。它们仍使用 `WinxVideoApp`，旧节点和旧工作流文件保留。超过 25 秒或无法确定时长的上传源片会在 AI 推理前拒绝，预览模式也不例外；整片版处理允许范围内的全部视频。

`1.5x` 是宽、高各放大 1.5 倍，例如 1080×1920 → 1620×2880，内容不裁切，像素量约为 2.25 倍。它是输出尺寸，不是“清晰度提升 50%”的计量。尺寸可改回 `source` 或其他预设；AI 增强仍由 `fast` / `quality` / `off` 控制。快速模式的 AI / 插帧工作尺寸仍受原有上限限制，放大到较高输出分辨率时含普通缩放，不保证恢复同等数量的真实细节。

`target_fps=1..120` 指定输出帧率，例如 24→48、25→48、30→48。高于源帧率时，把每个输出时间戳映射到相邻源帧，使用 RIFE 的实际中间时刻；保持播放速度，末尾因帧数取整可能延长不到一个输出帧。目标不高于源帧率时保留/丢弃源帧，不运行 RIFE。`target_fps=0` 恢复旧版 `interpolation=1..5` 整数倍模式；例如 30fps 的 2 倍是 60fps。指定目标帧率时必须关闭慢动作，避免两种时长规则冲突。新字段追加到原字段之后，旧 API 不传入时仍按原倍率运行。

**输出帧率和耗时并非严格线性关系。** 30→48 的非整数倍率可能比 30→60 调用更多次 RIFE，因为能直接复用的源帧更少；运行报告记录 `rife_inferences`。15 秒视频在 10 分钟内完成仍是待云端验证的目标，不能从短片或帧率数字直接保证。部署时须让维护者更新同一个仓库、同步 `output_scale` 选项和两个新字段，再导入这些新工作流；原有三份模型无需重下。

## 速度优先的应用工作流（2026-11-17，保留）

导入 [快速预览工作流](examples/Winx_App_Fast_Preview.json)，在 `WinxVideoApp` 节点上传视频。默认仅处理**源视频前 2 秒**、输出长边 1280、真实 2 倍 RIFE 插帧、防抖关闭。正常模式维持视频时长；慢动作才会延长时长，并同步拉长音频、保留音调。先确认预览质量和云端耗时，再使用 [整片工作流](examples/Winx_App_Fast_Full.json) 或把 `preview_seconds` 改成 0。文件名含 `_API` 的副本供程序调用。

`fast` 将 AI 输入长边限制到至多 640，2 倍增强结果的长边至多 1280；更大的最终尺寸会进行普通缩放。`quality` 使用原尺寸进行 AI 增强；`off` 关闭 AI 增强，仍可插帧、缩放与防抖。尺寸 1×/2×/3×/4× 与插帧倍率是独立参数；3×/4×尺寸超过模型原生 2×的部分属于普通缩放。快速模式以细节保留换取更少计算，不承诺与质量模式或 Winx 专有模型效果相同。

新节点只保留相邻帧，复用任务内的模型会话并及时编码输出，不依赖 VHS `meta_batch` 或重复提交任务。**流式主要降低内存；实际提速来自较小的 AI/插帧尺寸、合理的倍率与关闭额外处理，不能据此承诺具体速度倍数。** 运行报告会记录实际 AI 输入、插帧尺寸、编码器、帧数和总耗时。`encoder=auto` 先实际试编码 NVENC，不可用则使用 `libx264 veryfast`；AI 的 `device=cuda` 不会因此改成 CPU。

新增节点需要 FFmpeg 与 ffprobe。快速防抖需要 `deshake`；两遍防抖需要 `vidstabdetect` / `vidstabtransform`，会额外增加分析时间。所需滤镜缺失时，在 AI 推理前明确报错；默认不启用防抖。

应用字段见 [应用参数说明](docs/APP_FIELDS.md)，环境与更新步骤见 [RunningHub 安装说明](docs/INSTALL_RUNNINGHUB.md)。**更新仓库和导入 JSON 不等于 RunningHub 已安装/注册新节点或已发布应用。新节点仍需平台维护者同步代码、注册 `WinxVideoApp`，然后进行云端短片验收。**

## 保留：旧版 IMAGE 工作流

```text
VHS_LoadVideo → WinxVideo4KUpscale → WinxRife46 → VHS_VideoCombine
          └→ VHS_VideoInfo.loaded_fps ──┘          ↑
          └──────────────── audio ────────────────┘
```

优先导入 [最多读取 50 帧的编辑器工作流](examples/Winx_Video4K_RIFE46_RunningHub_AI_首测50帧.json)，在读取节点上传自己的低分辨率短视频，保持两个自定义节点 `device=cuda`，再提交运行。

`VHS_VideoInfo.loaded_fps` 已连接到补帧节点；补帧节点返回的帧率已连接到合成节点。默认宽高各 2 倍、2 倍补帧，例如 25fps → 50fps。末帧保持原始显示时间，输出总帧数为已加载帧数乘倍率，画面时长对应加载片段。原音轨已连接，但音频经过 VHS/FFmpeg 处理，不保证压缩音轨字节原样复制。

`examples/` 同时包含原版编辑器图、API 图及各自的 50 帧首测副本。文件名含 `API` 的版本用于程序调用；`upload_video.mp4` 是待上传文件的占位名。原版的 `frame_load_cap=0` 表示读取整片，首次请使用 50 帧副本。

## 运行范围

- 默认 `device=cuda`，`tile_size=256`。CUDA provider 不可用或初始化失败会报错，不自动把整项任务转为 CPU；部分形状操作仍可能由 ONNX Runtime 分配给 CPU。
- 旧版 `WinxVideo4KUpscale` / `WinxRife46` 一次持有输入、增强和补帧后的帧；分块只控制增强推理峰值，不解决整片内存，不支持 VHS `meta_batch`。长片请使用新增 `WinxVideoApp`，不要直接把旧 RIFE 接到分批节点上。
- “Video4K”是模型名称，输出尺寸是输入宽高的 2 倍，不会把任何输入固定变为 3840×2160。
- Video4K 候选与 Winx `.drp` 内权重的完全等价性未证明；模型含随机噪声算子，尚未验证逐次确定性与完整视频的时序表现。模型来源、RIFE 转换范围与授权说明见 [模型说明](docs/MODELS.md)。

## 验证状态

截至 2026-11-11，已有本地 CPU 的模型推理、尺寸处理、节点集成及真实 ComfyUI `PromptExecutor` + VHS 整图测试：128×96、25 帧/25fps → 256×192、50 帧/50fps、1 秒并带测试音轨。RIFE 在一组 128×128 实际帧上，转换 ONNX 与 NCNN 的 8 位 RGB 输出一致；该结论限于此组输入与 CPU 后端。

2026-11-17，`WinxVideoApp` 的本地 CPU 小样通过：真实 RIFE 1×/2×/3×/5×帧数、帧率、时长与调用次数，慢动作音轨长度，预览裁切，V9/V10 增强、快速防抖、竖屏旋转、硬切处理、无音轨输入、取消后子进程及临时文件清理，以及实际 ComfyUI `PromptExecutor` 整图执行。验证命令入口为 [tests/validate_streaming.py](tests/validate_streaming.py)。

2026-11-20，已有用户授权的一次 RunningHub Standard 短片成功记录：原流式预设 `fast`、长边 1280、2 倍插帧、CUDA、防抖关闭；处理 2 秒，平台任务耗时 51 秒，成片 720×1280、60fps、120 帧、2 秒并带 AAC 音轨。这项结果不证明原尺寸、高质量、1.5 倍尺寸、目标 48fps、15/25 秒整片或正式应用发布的速度和效果。

本地 FFmpeg 缺少 vidstab，两遍防抖仅验证了缺失滤镜时会提前报错，未验证其成片。新参数的本地 CPU 验证入口仍为 `tests/validate_streaming.py`，包含实际 1.5 倍尺寸 + 48fps 输出、非整数插帧时刻、分数源帧率、降帧率、音轨和 25 秒源片限制，以及新旧 ComfyUI PromptExecutor 图执行。新增参数的 RunningHub 安装与云端运行仍需核实，不能把仓库更新视为云端已生效。
