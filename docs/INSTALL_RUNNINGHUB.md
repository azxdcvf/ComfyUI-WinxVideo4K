# RunningHub / 云端 ComfyUI 安装与验收

本仓库的 `__init__.py`、`runtime.py` 和 `requirements.txt` 直接位于根目录，可作为普通 ComfyUI 自定义节点仓库克隆安装。模型另行交接；不能仅导入工作流 JSON 代替节点和依赖安装。

仓库地址：<https://github.com/azxdcvf/ComfyUI-WinxVideo4K>。

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

首版一次持有输入、增强和补帧后的全部帧；分块不解决整片主机内存占用。不连接 VHS `meta_batch`，长片流式处理与跨段补帧未实现。

通过短片验证后，再参考 [应用字段映射](APP_FIELDS.md) 配置视频上传与 MP4 输出。原版 `frame_load_cap=0` 表示整片，增加处理范围前请先评估资源。公开或商业发布前另需确认模型授权。
