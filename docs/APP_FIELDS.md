# 视频增强和插帧应用字段

目标：RunningHub 国际站 `runninghub.ai`。本文件为人工配置参考，不是平台可直接导入的应用定义。

先完成 [云端安装与验收说明](INSTALL_RUNNINGHUB.md) 中的节点安装和 CUDA 短片验收，再配置应用。

## 1.5 倍尺寸 / 48fps 预设（2026-11-20）

编辑器导入 `examples/Winx_App_1p5x_48fps_Preview.json` 或 `examples/Winx_App_1p5x_48fps_Full.json`。仍是 **200 · WinxVideoApp**，原有字段顺序不变，末尾追加 `target_fps` 和 `max_source_seconds`。平台维护者需同步节点定义，包括 `output_scale` 的新选项 `1.5x`。旧示例和旧 API 继续按原倍率工作。

| 应用控件 | 节点字段 | 新预设默认 / 说明 |
| --- | --- | --- |
| 输出尺寸 | `output_scale` | `1.5x`，宽、高各 1.5 倍，像素约 2.25 倍；允许选 `source` 等其他尺寸，不作为清晰度百分比 |
| 画质增强 | `enhancement` | `fast`；可选 `quality` 原尺寸增强或 `off` 关闭增强。快速模式计算尺寸受限，较大输出含普通缩放 |
| 输出帧率 | `target_fps` | 默认 48，可设 1–120；高于源帧率时用 RIFE 按实际时间戳插帧。低于/等于源帧率时丢帧/保留原帧，不运行 RIFE |
| 整数倍模式 | `target_fps` / `interpolation` | 把 `target_fps` 设为 0 后，使用原有 `interpolation=1..5`。目标帧率非 0 时忽略倍率，要求 `slow_motion=false` |
| 最长上传源片 | `max_source_seconds` | 新应用固定为 25 并隐藏；超过上限或时长未知会在 AI 推理前拒绝，不能用 2 秒预览绕过。0 只用于保持旧工作流无限制的行为 |
| 处理范围 | `preview_seconds` | Preview 为 2，Full 为 0；0 表示处理整个允许的视频 |

应用中可隐藏 `interpolation`、`slow_motion=false`、`max_source_seconds=25`、`device=cuda`、`tile_size=512`、`stabilization=off`、`encoder=auto`，向用户提供视频、增强模式、输出尺寸和输出帧率即可。若需要露出整数倍后备选项，应让界面在切换后同步设 `target_fps=0`，避免两个控件含义冲突。

48fps 是整数帧率，但 30→48 是 1.6 倍，可能比 30→60 的 2 倍方案需要更多次 RIFE 推理。目标帧率模式的末尾取整误差小于一个输出帧，不改变播放速度，音轨按成片长度对齐。默认 1.5 倍 / 48fps 的完整视频云端耗时尚未验证，15 秒 / 10 分钟为目标而非已经通过的保证。

## 原流式预设 `WinxVideoApp`（2026-11-17，保留）

编辑器工作流：`examples/Winx_App_Fast_Preview.json`；整片：`examples/Winx_App_Fast_Full.json`。两者执行节点均为 **200 · WinxVideoApp**。以下是人工配置映射，不能当作 RunningHub 应用定义直接导入。

| 应用控件 | 200 号节点字段 | 默认 / 说明 |
| --- | --- | --- |
| 上传视频 | `video` | 必填，平台上传后传入实际文件名；支持 input 子目录，不能填电脑 D 盘路径 |
| 画质增强 | `enhancement` | `fast` 快速；`quality` 原尺寸增强；`off` 关闭 AI 增强 |
| 增强模型 | `model_name` | V9 / V10；显示真实文件名或版本名，不命名为 Gen Detail / Real Smooth |
| 输出尺寸 | `output_scale` | 默认 `1280_long_edge`；`source` 原尺寸；`2x`/`3x`/`4x`；`720p`/`1080p`/`1440p`/`2160p` 按短边计算，保持横竖方向 |
| 真实插帧倍率 | `interpolation` | 默认 2；1 关闭，2/3/4/5 倍；30fps 源片对应 60/90/120/150fps，25fps 源片对应 50/75/100/125fps |
| 慢动作 | `slow_motion` | 默认 false；true 时在源帧率播放插入的帧，视频和声音同步延长，声音保留音调 |
| 跳过场景变换 | `skip_scene_transitions` | 默认 true；在检测到硬切处保持前帧，不跨镜头 AI 插帧；启发式检测也可能误判闪光或快速运镜 |
| 防抖 | `stabilization` | 默认 `off`；`fast` 单遍；`two_pass` 两遍分析，须有 vidstab 滤镜且更费时 |
| 处理源片秒数 | `preview_seconds` | 预览版 2；整片版 0。2 表示前两秒源片，5 倍慢动作输出约 10 秒，0 表示整片 |
| 导出压缩质量 | `crf` | 默认 20；更低通常文件更大，不代表 AI 恢复出更多真实细节 |
| 输出视频 | 第 0 个输出 `video` | `VHS_FILENAMES`，选最终 MP4；同时返回 `gifs` 预览元数据，需平台核对输出识别 |
| 运行报告 | 第 1 个输出 `report` | JSON 文本，包括实际 AI/插帧尺寸、帧数、时长、编码器、耗时 |

高级参数可隐藏：`device=cuda`、`tile_size=512`、`encoder=auto`。显存不足时由维护者改 `tile_size=256`；不要用静默 CPU 回退来掩盖 CUDA 故障。`auto` 编码会先尝试实际 NVENC 小帧编码，失败后使用 CPU 的 x264 veryfast；两种编码都与 AI 推理设备的选择独立。

快速模式先把 AI 输入缩小至长边至多 640，AI 2 倍输出和插帧工作长边至多约 1280。最终选择更大尺寸时使用普通缩放。质量模式在原尺寸进行 AI 增强，通常更耗时。1×增强是在增强后缩回原尺寸；3×/4×尺寸超过模型原生 2×的部分使用普通缩放。这些模式不声称复刻 Winx 专有网络或其底层 GPU 优化。

建议应用说明：

> 上传视频，调节增强、输出尺寸和真实 RIFE 插帧倍率。默认快速模式、输出长边 1280、2 倍插帧、防抖关闭，先处理源片前 2 秒确认质量和耗时。将处理秒数改为 0 才处理整片。高分辨率、高倍率插帧和两遍防抖会增加耗时与平台费用。快速模式会缩小 AI 工作尺寸，细节效果与质量模式不同。

代码更新、节点安装、工作流导入、GPU 试跑和正式应用发布分别需要核实。2026-11-20 原流式预设已有一次 2 秒 RunningHub 成功记录：长边 1280、2 倍插帧，输出 720×1280 / 60fps，平台记录 51 秒。它不能证明新增 1.5 倍 / 48fps 参数已在云端安装或通过整片验收。

## 旧版 IMAGE 工作流字段（保留）

| 应用界面 | 节点 | 字段 | 建议配置 |
| --- | --- | --- | --- |
| 上传视频 | 7 · `VHS_LoadVideo` | `video` | 必填，视频文件 |
| 增强模型 | 101 · `WinxVideo4KUpscale` | `model_name` | V9 / V10，首版默认 V9；显示真实版本名，不预先承诺两者效果差异 |
| 补帧倍率 | 102 · `WinxRife46` | `multiplier` | 默认 2；可选 1、2、3、4、5；1 表示跳过补帧 |
| 处理帧数上限 | 7 · `VHS_LoadVideo` | `frame_load_cap` | 测试期固定 50；增加前先评估内存，0 表示整片 |
| 导出质量 | 12 · `VHS_VideoCombine` | `crf` | 默认 18，首版可隐藏 |
| 输出视频 | 12 · `VHS_VideoCombine` | `Filenames` | 根据平台输出选择器指向最终 MP4 |

工作流内固定：`101.device=cuda`、`102.device=cuda`、`101.tile_size=256`、`7.force_rate=0`、`7.custom_width=0`、`7.custom_height=0`、`7.skip_first_frames=0`、`7.select_every_nth=1`、`7.format=None`。

保留 `10.loaded_fps → 102.source_fps → 12.frame_rate` 的连线。原音轨从 `7.audio` 连接到 `12.audio`。

建议应用说明：

> 上传短视频，用 Video4K 将宽高各增强到 2 倍，再用 RIFE 4.6 提升帧率并输出带声音的 MP4。默认 2 倍补帧，例如 25fps 变为 50fps。测试期最多处理前 50 帧。

测试工作流输出的是加载到的片段；保留 50 帧上限时，应用界面应明确告知这个限制。首版尚无长片流式或跨段处理，不能直接承诺任意时长。

增强模型与 Winx `.drp` 的权重完全等价性未证明；公开或商业发布前还需确认所用模型授权。
