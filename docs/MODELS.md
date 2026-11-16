# 模型安装、来源与验证范围

三份模型通过 [GitHub Releases](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/tag/models-20261116) 提供，不存入代码的 Git 历史，也不在节点运行时自动下载。下载后放入 `ComfyUI/models/winx_video4k/`，按根目录的 [model_manifest.json](../model_manifest.json) 校验。

## 下载

可下载 [模型整包](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/download/models-20261116/winx-video4k-models-20261116.zip)，将其中的 `models/` 合并到实际 ComfyUI 根目录，或按下表下载单个文件。下载文件名和大小写保持不变。

| 文件 | 直接下载 | 字节数 |
| --- | --- | --- |
| `Video4K_V9_video_V9_x2_S2GAN_latest.onnx` | [V9 ONNX](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/download/models-20261116/Video4K_V9_video_V9_x2_S2GAN_latest.onnx) | 17,014,765 |
| `Video4K_V10_video_V10_x2_S2GAN_417000.onnx` | [V10 ONNX](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/download/models-20261116/Video4K_V10_video_V10_x2_S2GAN_417000.onnx) | 22,759,276 |
| `rife_v4.6_winx_fp16weights.onnx` | [RIFE 4.6 ONNX](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/download/models-20261116/rife_v4.6_winx_fp16weights.onnx) | 21,297,017 |

校验文件：[SHA256SUMS.txt](https://github.com/azxdcvf/ComfyUI-WinxVideo4K/releases/download/models-20261116/SHA256SUMS.txt)，包含三个单文件与模型整包的 SHA256。

解压整包时，应将包内 `models/winx_video4k/` 对应到实际 ComfyUI 的同名路径。请勿把模型放到节点仓库自己的 `models/` 目录。平台使用任务容器或统一模型存储时，还需确认执行实例可读到该目录。

## 文件用途

| 文件 | 用途 |
| --- | --- |
| `Video4K_V9_video_V9_x2_S2GAN_latest.onnx` | V9 增强，宽高各 2 倍，默认选择 |
| `Video4K_V10_video_V10_x2_S2GAN_417000.onnx` | V10 增强，宽高各 2 倍，可选 |
| `rife_v4.6_winx_fp16weights.onnx` | RIFE 4.6 补帧，已移入本地 NCNN 卷积权重 |

请保持文件名不变。将普通公开 RIFE ONNX 重命名为第三个文件名，不能替代权重转换。

## Video4K V9/V10

增强候选来自同厂 VideoProc 的 [第三方公开模型存档](https://huggingface.co/Builderstar/videoproc-ai-model-zoo)。输入为单帧 RGB、float32、NCHW、[0,1]，输出宽高各 2 倍；节点会进行所需补边与裁回。

未证明这些候选与 Winx `.onnx.drp` 内权重完全相同，未取得 Winx 内部颜色、分块和后处理参数。模型包含随机噪声算子，尚未验证逐次确定性或完整视频的时序效果。仓库不对 V9/V10 预先承诺哪种画质更好。

公开存档模型卡标注 `license: other`。本项目未确认模型公开或商业应用发布授权，代码仓库公开不等于取得模型分发授权。

## RIFE 4.6

图模板复用 [vs-mlrt](https://github.com/AmusementClub/vs-mlrt) 的 `external-models` 发布包 `rife_v2_v4.7z` 内 `rife_v2/rife_v4.6.onnx`。已将本地 NCNN 原权重的 44 层卷积及偏置写入 ONNX，处理了 NCNN 已融合的 ResConv beta。

原 NCNN 二进制权重 SHA256：

```text
f334ed2260149ce0188a6dcf049844e8b0cdd912e01cbcfb63553157d2508958
```

此前校验与 [nihui/rife-ncnn-vulkan](https://github.com/nihui/rife-ncnn-vulkan) 的 RIFE 4.6 权重一致。一组 128×128 实际视频帧的 CPU 对照中，转换 ONNX 与官方 NCNN 参考程序保存为 8 位 RGB 后逐像素一致；该结论限于该组输入与后端，不代表设备、尺寸及补边处理在所有条件下完全等价。

安装使用已转换的三份 ONNX 即可，不需要部署 Winx Windows EXE，也不需要服务器再转换 `.drp`。

## 运行验证

截至 2026-11-11，本地已完成 V9/V10 checker 与 CPU 多尺寸推理、奇数尺寸补边裁回、真实 ComfyUI `tiled_scale`、RIFE 补帧倍率/尾帧时长及真实 `PromptExecutor` + VHS 整图视频测试。

整图 CPU 测试输入为 128×96、25 帧/25fps，输出为 256×192、50 帧/50fps、1 秒且带测试音轨。测试片循环使用三个真实帧并添加生成的 440Hz 测试音，不能替代完整原片画质对照。

尚未验证：CUDA、RunningHub 云端执行、完整长视频负载、Winx GUI 成片对照、公开应用发布。
