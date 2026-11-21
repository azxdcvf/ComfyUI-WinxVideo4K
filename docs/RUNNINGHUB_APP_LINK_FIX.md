# RunningHub AI 应用启动校验修复 · 2026-11-22

## 适用错误

应用提交在执行前失败，响应包含 `prompt_outputs_failed_validation`。200 号 `WinxVideoApp` 提示 `Select a video uploaded into the ComfyUI input directory`；204 号 `VideoLoaderPathPlus` 提示 `NoneType` 没有 `endswith`。页面可能统一显示“任务发起失败，当前AI应用不可用”。

ComfyUI 在运行前用 `None` 代替尚未执行的连线输入。将该值直接当文件名校验，会在前面的节点产生真实路径之前拒绝任务。

## 本仓库的修复

- `streaming.py`：`VALIDATE_INPUTS` 在 `video is None` 时延期校验，`IS_CHANGED` 对此返回 NaN；真正执行时仍检查输入文件、扩展名及 input 目录边界。静态文件输入继续在启动前校验。
- `video_output.py`：新增 `WinxVideoFromPath`，执行时确认文件在 ComfyUI output 目录内，再用 `comfy_api.latest.InputImpl.VideoFromFile` 交接给原生 `SaveVideo`。不读取整段 IMAGE、不重新运行增强或插帧模型。
- `__init__.py`：注册 `WinxVideoFromPath`；已有节点和 `WinxVideoApp` 的两个输出不改名、不改类型。
- 25 秒可调应用示例：仅将原 204 号 `VideoLoaderPathPlus` 换成 `WinxVideoFromPath`，前后连线仍为 `203 → 204 → 205`。其他模板保留。

## RunningHub 维护者操作

在实际 ComfyUI 自定义节点目录的本仓库中更新；存在平台本地修改时先合并，不覆盖未提交修改：

```bash
cd /实际ComfyUI目录/custom_nodes/ComfyUI-WinxVideo4K
git pull --ff-only
```

同步完整仓库，特别是 `streaming.py`、`video_output.py`、`__init__.py`。本次**无需重下三份模型，无需重装 ONNX Runtime、PyTorch 或 CUDA**。

1. 更新 Standard 等真正执行任务的实例/镜像。
2. 注册新类型 **`WinxVideoFromPath`**：必需输入 `file: STRING`，输出 `VIDEO`；显示名 `Winx Output Video · Native VIDEO`。
3. 刷新平台节点索引/编辑器的类型定义，并重启实际 ComfyUI 服务。仅在编辑器添加一个同名节点不能修复执行实例里的旧代码。
4. 打开 `examples/Winx_App_Adjustable_25s_RunningHub.json`，上传视频。替换当前正式图时保留 200–212 节点编号及四个应用输入编号。发布者再更新原 AI 应用的工作流快照；无需重新选择已有封面和标签。

新模板默认 `enhancement=fast`、`output_scale=1.5x`、`target_fps=48`、`preview_seconds=25`、`max_source_seconds=0`、`slow_motion=false`、`device=cuda`。超过 25 秒时截取前 25 秒，不足时按实际完整长度处理。

## 本地验证

回归命令位于 `tests/validate_app_links.py`，需要已配置的 ComfyUI、三份模型、FFmpeg 和 Python 依赖；所有路径由命令参数传入，不提交云端任务。

```bash
python tests/validate_app_links.py \
  --comfy /本地ComfyUI目录 \
  --models /ComfyUI/models/winx_video4k \
  --ffmpeg /ffmpeg完整路径 \
  --output /独立测试输出目录
```

验证实际 ComfyUI 连线校验、静态缺失/越界路径拒绝、动态缓存检查、真实 Video4K/RIFE/FFmpeg 处理、新适配器及原生 SaveVideo。样片为 96×64、24fps、0.25 秒并带声音；输出为 144×96、48fps、12 帧并保留声音。CUDA 性能、云端镜像同步及已发布应用的实际运行仍需在目标环境验证。
