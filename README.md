# ComfyUI-WinxVideo4K

Video4K V9/V10 的 2 倍尺寸增强节点，以及使用本地 NCNN 权重转换的 RIFE 4.6 补帧节点。用于搭建上传视频、增强、补帧并导出 MP4 的 ComfyUI 工作流。

**仓库包含节点代码、示例工作流和安装说明，不包含模型权重。** 云平台维护者需要另行安装三份模型。本仓库不是 Winx 官方项目，也不代表已复刻 Winx 软件的全部处理流程。

## 节点

| 注册类型 | 功能 | 主要参数 |
| --- | --- | --- |
| `WinxVideo4KUpscale` | Video4K V9/V10 ONNX，宽高各 2 倍 | `model_name`、`device`、`tile_size` |
| `WinxRife46` | RIFE 4.6 ONNX，1 至 4 倍帧率 | `source_fps`、`multiplier`、`device` |

节点分类：`Winx Video4K`。

## 安装

将本仓库克隆到 `ComfyUI/custom_nodes/ComfyUI-WinxVideo4K/`，保证 `__init__.py` 直接位于该目录内。根目录布局已适配 Git 克隆安装，不需要再移动一层子目录。

```bash
cd "/替换为实际ComfyUI根目录/custom_nodes"
git clone https://github.com/azxdcvf/ComfyUI-WinxVideo4K.git
```

由运行环境维护者使用 **实际运行 ComfyUI 的 Python** 安装本仓库的 `requirements.txt`。当前依赖范围为 `onnxruntime-gpu>=1.20.0,<2.0`，应按目标环境 CUDA/cuDNN 兼容性选择并固定具体版本，不要直接升级平台的 PyTorch 或 CUDA。

请另外准备：

- 三份模型，放到 `ComfyUI/models/winx_video4k/`；文件名和 SHA256 见 [模型清单](model_manifest.json) 与 [模型说明](docs/MODELS.md)。节点不会自动下载模型。
- [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite) 及其依赖，用于视频读取、视频信息和视频合成。
- VHS 可调用的 FFmpeg，用于导出 H.264 MP4 和音频。

安装后重启实际执行任务的 ComfyUI 服务。RunningHub 维护者请参考 [云端安装与验收说明](docs/INSTALL_RUNNINGHUB.md)。

## 工作流

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
- 当前一次持有输入、增强和补帧后的帧。分块只控制增强推理的峰值，不解决整片的主机内存占用。当前不支持 VHS `meta_batch`、长片流式处理或跨段补帧。
- “Video4K”是模型名称，输出尺寸是输入宽高的 2 倍，不会把任何输入固定变为 3840×2160。
- Video4K 候选与 Winx `.drp` 内权重的完全等价性未证明；模型含随机噪声算子，尚未验证逐次确定性与完整视频的时序表现。模型来源、RIFE 转换范围与授权说明见 [模型说明](docs/MODELS.md)。

## 验证状态

截至 2026-11-11，已有本地 CPU 的模型推理、尺寸处理、节点集成及真实 ComfyUI `PromptExecutor` + VHS 整图测试：128×96、25 帧/25fps → 256×192、50 帧/50fps、1 秒并带测试音轨。RIFE 在一组 128×128 实际帧上，转换 ONNX 与 NCNN 的 8 位 RGB 输出一致；该结论限于此组输入与 CPU 后端。

RunningHub 云端安装、CUDA 执行、完整视频负载、Winx GUI 成片对照及应用发布均未验证。云端短片验收完成后，可按 [应用字段映射](docs/APP_FIELDS.md) 配置应用。
