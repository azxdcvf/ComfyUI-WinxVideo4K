# 安装并通过云端试跑后配置应用

目标：RunningHub 国际站 `runninghub.ai`。本文件为人工配置参考，不是平台可直接导入的应用定义。

先完成 [云端安装与验收说明](INSTALL_RUNNINGHUB.md) 中的节点安装和 CUDA 短片验收，再配置应用。

| 应用界面 | 节点 | 字段 | 建议配置 |
| --- | --- | --- | --- |
| 上传视频 | 7 · `VHS_LoadVideo` | `video` | 必填，视频文件 |
| 增强模型 | 101 · `WinxVideo4KUpscale` | `model_name` | V9 / V10，首版默认 V9；显示真实版本名，不预先承诺两者效果差异 |
| 补帧倍率 | 102 · `WinxRife46` | `multiplier` | 默认 2；可选 1、2、4；1 表示跳过补帧 |
| 处理帧数上限 | 7 · `VHS_LoadVideo` | `frame_load_cap` | 测试期固定 50；增加前先评估内存，0 表示整片 |
| 导出质量 | 12 · `VHS_VideoCombine` | `crf` | 默认 18，首版可隐藏 |
| 输出视频 | 12 · `VHS_VideoCombine` | `Filenames` | 根据平台输出选择器指向最终 MP4 |

工作流内固定：`101.device=cuda`、`102.device=cuda`、`101.tile_size=256`、`7.force_rate=0`、`7.custom_width=0`、`7.custom_height=0`、`7.skip_first_frames=0`、`7.select_every_nth=1`、`7.format=None`。

保留 `10.loaded_fps → 102.source_fps → 12.frame_rate` 的连线。原音轨从 `7.audio` 连接到 `12.audio`。

建议应用说明：

> 上传短视频，用 Video4K 将宽高各增强到 2 倍，再用 RIFE 4.6 提升帧率并输出带声音的 MP4。默认 2 倍补帧，例如 25fps 变为 50fps。测试期最多处理前 50 帧。

测试工作流输出的是加载到的片段；保留 50 帧上限时，应用界面应明确告知这个限制。首版尚无长片流式或跨段处理，不能直接承诺任意时长。

增强模型与 Winx `.drp` 的权重完全等价性未证明；公开或商业发布前还需确认所用模型授权。
