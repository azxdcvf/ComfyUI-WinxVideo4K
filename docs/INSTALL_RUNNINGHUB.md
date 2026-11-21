# RunningHub / 云端 ComfyUI 安装与验收

本仓库的 `__init__.py`、`runtime.py` 和 `requirements.txt` 直接位于根目录，可作为普通 ComfyUI 自定义节点仓库克隆安装。三份模型从 [GitHub Releases](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/tag/models-20261116) 另外下载；不能仅导入工作流 JSON 或克隆代码代替模型和依赖安装。

仓库地址：<https://github.com/azxdcvf/ComfyUI-WinxVideo4K>。

2026-11-22 的 AI 应用启动校验修复需要同步 `streaming.py`、`video_output.py` 与 `__init__.py`，并注册新节点 `WinxVideoFromPath`。具体步骤、原错误及本地验证见 [应用启动校验修复](RUNNINGHUB_APP_LINK_FIX.md)。本次不更换模型和运行库；仅更新编辑器 JSON 不能代替执行实例代码更新。

## 已安装旧版时更新新版流式应用

新增注册类型为 **`WinxVideoApp`**，原有 `WinxVideo4KUpscale` / `WinxRife46` 和示例仍保留。更新不需要重新下载已安装且校验正确的三份模型。

2026-11-20 的更新继续使用 `WinxVideoApp`，没有新模型或新依赖。需要同步 `output_scale` 的 `1.5x` 选项，以及追加的可选整数字段 `target_fps`（0–120，节点默认 0）和 `max_source_seconds`（0–25，节点默认 0）。新应用工作流分别传入 48 和 25。不能仅更新编辑器中的字段；实际执行实例也必须更新 `streaming.py`。旧工作流不传两个字段时，仍走原整数倍插帧且不启用新增时长限制。

更新后先导入 `examples/Winx_App_1p5x_48fps_Preview.json`：1.5 倍尺寸、48fps、快速增强、源片最长 25 秒、只处理前 2 秒。另有 Full 版本。平台应用参数映射见 [APP_FIELDS.md](APP_FIELDS.md)。`target_fps>0` 要求关闭慢动作，输出尺寸与画质增强模式独立；目标帧率低于/等于源帧率时不运行 RIFE。云端执行会计费，代码更新不会自动发起任务。

```bash
cd "/替换为实际ComfyUI根目录/custom_nodes/ComfyUI-WinxVideo4K"
git pull --ff-only
```

请维护者先确认工作区没有未提交的平台修改，再更新相应实际执行实例；同时发布/允许编辑器使用新类型 `WinxVideoApp`，重启 ComfyUI 并刷新节点列表和浏览器。代码新增 `streaming.py` 与 `web/` 上传及预览扩展，不要只复制旧 `__init__.py`。如果平台有单独的应用节点注册，需同步其字段与 `VHS_FILENAMES` / MP4 输出识别。

需要可执行的 **FFmpeg 与 ffprobe**，默认按环境变量 `WINX_FFMPEG_PATH` / `WINX_FFPROBE_PATH`、兼容的 VHS 路径、同目录 ffprobe 或 PATH 查找。仅有 imageio 的 FFmpeg 而没有 ffprobe 也不够。模型推理依赖没有新增，继续复用原有 ONNX Runtime GPU / PyTorch / NumPy 环境。

快速防抖要求 FFmpeg 的 `deshake`。两遍防抖要求 `vidstabdetect` 和 `vidstabtransform`（通常需要编译启用 libvidstab），缺失时会在 AI 推理前报错，不会假装完成防抖。若暂不提供这些滤镜，应用保留 `stabilization=off`，并隐藏不可用选项。

`encoder=auto` 会尝试实际调用 `h264_nvenc` 编码一帧，不可用则选择 `libx264 veryfast`。如果平台禁用 NVENC 或 FFmpeg 未编译相应支持，不影响 AI 的 CUDA 设置；编码器可固定为 `libx264`。

先导入 `examples/Winx_App_Fast_Preview.json`，上传低分辨率带声音的短视频，保持默认 `preview_seconds=2`、`enhancement=fast`、`output_scale=1280_long_edge`、`interpolation=2`、`device=cuda`、`stabilization=off`。执行本身由账户按平台规则计费；仓库没有自动提交云端任务。记录 GPU 利用率、节点总耗时及实际余额变化，核对成片时长、声音、输出尺寸与帧率后再处理整片。

本地验证使用真实 ONNX / FFmpeg 和 ComfyUI PromptExecutor 小样。2026-11-20，原 `fast` / 长边 1280 / 2 倍插帧的 RunningHub Standard 两秒任务成功，平台耗时 51 秒，输出 720×1280、60fps、120 帧并带声音。新增的 1.5 倍尺寸和目标 48fps 参数尚需平台更新与云端验收，完整视频速度和正式应用发布尚未验证。两遍防抖因本地缺滤镜尚未验证成片。

---

## 以下为保留的旧版安装与验证说明

```bash
cd "/替换为实际ComfyUI根目录/custom_nodes"
git clone https://github.com/azxdcvf/ComfyUI-WinxVideo4K.git
```

## 1. 安装目录

最终目录应为：

```text
<COMFY_ROOT>/
  custom_nodes/
    ComfyUI-WinxVideo4K/
      __init__.py
      runtime.py
      requirements.txt
      README.md
      examples/
      docs/
    ComfyUI-VideoHelperSuite/
  models/
    winx_video4k/
      Video4K_V9_video_V9_x2_S2GAN_latest.onnx
      Video4K_V10_video_V10_x2_S2GAN_417000.onnx
      rife_v4.6_winx_fp16weights.onnx
```

仓库里的 `model_manifest.json` 路径以 ComfyUI 根目录为基准。请不要把三份模型放到本仓库内的 `models/`，也不要多套一层重复的节点目录。平台使用统一模型存储时，需要正确挂载/映射到实际运行环境可读的 `winx_video4k` 目录，并持久化保存。

下载 [模型整包](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/download/models-20261116/winx-video4k-models-20261116.zip)，把包内 `models/` 合并到实际 ComfyUI 根目录。单文件下载地址与校验说明见 [模型说明](MODELS.md)。三个文件需要保持原文件名和大小写，并确认 Standard 等实际任务实例的模型挂载也已生效。

## 2. GPU 依赖

请在实际运行 ComfyUI 的 Python 环境中安装本仓库的 `requirements.txt`。根据目标 Python、驱动、PyTorch、CUDA 和 cuDNN，按 [ONNX Runtime 官方兼容表](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html) 选择具体的 `onnxruntime-gpu` 版本并固定。

当前范围 `>=1.20.0,<2.0` 不是已验证的云端版本锁定。请勿因此直接升级平台 PyTorch 或 CUDA。已有 CPU 版 ONNX Runtime 或同名模块包冲突时，由维护者核对处理，不在共享环境中直接批量卸载。

Linux 维护者可参考下列命令，前三个变量必须替换为实际值后再执行：

```bash
COMFY_ROOT="/替换为实际ComfyUI根目录"
COMFY_PYTHON="/替换为运行ComfyUI的Python完整路径"
ORT_VERSION="替换为核对兼容的具体版本号"
"$COMFY_PYTHON" -m pip install -r "$COMFY_ROOT/custom_nodes/ComfyUI-WinxVideo4K/requirements.txt" "onnxruntime-gpu==$ORT_VERSION"
"$COMFY_PYTHON" -c "import sys, torch, onnxruntime as ort; print('python:', sys.executable); print('torch:', torch.__version__); print('torch_cuda:', torch.version.cuda); print('cudnn:', torch.backends.cudnn.version()); print('ort:', ort.__version__); print('providers:', ort.get_available_providers())"
```

PyTorch 和 NumPy 复用 ComfyUI 环境。节点导入时不会安装依赖、下载或转换模型。三份模型已为可运行的标准 ONNX，不需要 Winx 的 Windows EXE 或 `.drp` 文件。

## 3. VHS 与 FFmpeg

复用平台已有 [VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)，确认 `VHS_LoadVideo`、`VHS_VideoInfo` 和 `VHS_VideoCombine` 可用。若缺失，由维护者安装仓库及其依赖。

确认 FFmpeg 可被 VHS 调用，能输出工作流的 H.264 MP4 及音频。本仓库不包含 VHS、FFmpeg 二进制或 GPU 运行库。

## 4. 重启与识别

重启或重新加载实际执行任务的 ComfyUI 服务，并刷新平台节点定义。平台使用独立节点索引或任务镜像时，也需同步安装。

两个自定义注册类型必须为 `WinxVideo4KUpscale` 与 `WinxRife46`。分类是 `Winx Video4K`，显示名分别为 `Video4K V9/V10 · 2x (ONNX)` 与 `RIFE 4.6 · Frame Interpolation (ONNX)`。

打开工作流检查红框消失、参数可编辑。若页面能搜到节点而任务实例报缺节点，请核对编辑器与执行实例的安装是否一致。

## 5. 真实 GPU 首测

导入 `examples/Winx_Video4K_RIFE46_RunningHub_AI_首测50帧.json`，在读取节点上传低分辨率、25fps 或 30fps、至少含两帧且带声音的短视频。不要直接用长视频进行首次测试。

| 节点 | 首测配置 |
| --- | --- |
| 7 · `VHS_LoadVideo` | `frame_load_cap=50`、`force_rate=0`，宽高不强制缩放，不跳帧 |
| 101 · `WinxVideo4KUpscale` | V9、`device=cuda`、`tile_size=256` |
| 102 · `WinxRife46` | `multiplier=2`、`device=cuda` |
| 12 · `VHS_VideoCombine` | `video/h264-mp4`、CRF 18，保留帧率和音轨连线 |

`VHS_VideoInfo` 的第 5 号输出端口（从 0 编号，`loaded_fps`）接入补帧节点；补帧节点 `frame_rate` 接入合成节点。保持自动连线，不手填 25/50 覆盖。

验收内容：

1. 五个执行节点可识别，三份模型的文件名、大小和 SHA256 与清单一致。
2. 两个自定义节点以 `cuda` 完成真实推理。provider 可用列表只是预检；实际模型执行与 GPU 使用记录才是云端验收依据。
3. 输出 MP4 可播放，宽高各为输入的 2 倍，帧率为实际加载帧率的 2 倍。加载 N 帧时输出 2N 帧，画面时长对应加载片段。
4. 输入有声音时，检查输出声音与画面同步。
5. V9 完成后，可切换 V10 再测试。

保留实际 Python/ORT/CUDA/cuDNN 版本、执行实例/镜像信息、运行日志、耗时、GPU/内存使用记录及输出视频。若失败，请提供从节点导入或 session 初始化开始的完整错误。

CUDA 不可用或初始化失败会报错，不自动把整项任务转为 CPU。模型的部分形状操作仍可能由 ONNX Runtime 分配给 CPU，不声称每个算子均在 GPU。

## 6. 后续应用配置

旧版 IMAGE 工作流一次持有输入、增强和补帧后的全部帧；分块不解决整片主机内存占用。不连接 VHS `meta_batch`。新增的 `WinxVideoApp` 使用文件流式读取和输出，不需要接入 `meta_batch`。

通过短片验证后，再参考 [应用字段映射](APP_FIELDS.md) 配置视频上传与 MP4 输出。原版 `frame_load_cap=0` 表示整片，增加处理范围前请先评估资源。公开或商业发布前另需确认模型授权。
