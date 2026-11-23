# MP4 / ZIP 输出开关（2026-11-23）

AI 应用出现两份相同视频，是因为 `WinxVideoApp` 返回成片预览后，下游 `VHS_SelectFilename → WinxVideoFromPath → SaveVideo` 又返回同一成片。新版独立工作流移除了这条重复保存链路，保留原有示例文件。

导入 `examples/Winx_App_Adjustable_25s_OutputSwitch_RunningHub.json`；程序调用对应 `_API.json`。默认 fast、宽高各 1.5 倍、48fps、最多处理前 25 秒，短片按实际长度处理。源视频路径仍经 `RB_GetFilename` 适配 RunningHub 根目录上传。

## 应用输入

| 节点 | 字段 | 用途 | 默认 |
| --- | --- | --- | --- |
| 206 LoadVideo | file | 上传视频 | 由用户上传 |
| 208 PrimitiveString | value | fast / quality / off | fast |
| 210 PrimitiveString | value | 输出尺寸 | 1.5x |
| 202 PrimitiveInt | value | 目标帧率 | 48 |
| 216 PrimitiveBoolean | value | ZIP输出（关闭=MP4；开启=ZIP） | false |

216 的 BOOLEAN 输出接到 200 `WinxVideoApp.zip_output`。应用字段必须为 BOOLEAN，默认值 `false`，不能传入字符串 `"false"`。封面、标签和发布范围由原应用保持。

## 代码与输出协议

`WinxVideoApp` 在可选字段末尾追加 `zip_output`，默认 `False`；不传入该字段的旧工作流继续输出 MP4。模型、增强与插帧流程和原有 `(VHS_FILENAMES, STRING)` 两个输出口保持兼容。

- 关闭：`ui.gifs` 只含本次 MP4 的一个文件描述符。
- 开启：`ui.images` 只含本次 ZIP 的一个文件描述符，字段为 `filename`、`subfolder`、`type="output"`。此文件描述符形式参考已安装的 `solarL_SaveImagesToZip`。平台应按 `.zip` 后缀返回可下载附件，不能强制作为图片预览或改名为 MP4。
- ZIP 使用 Python 标准库 `zipfile.ZIP_STORED`，只打包本次成片，不重编码；解包后 MP4 字节与打包前一致。不会扫描整个 output 目录，也不删除历史成品。ZIP 不用于再次缩小 MP4 体积。
- ZIP 先写入同目录的 `.part.zip`，成功关闭后原子改名；本次失败的临时 ZIP 会清理。
- 输出口的 `VHS_FILENAMES` 仍指向原 MP4，便于旧调用者保持兼容。因此新版应用图必须移除额外 `SaveVideo` 输出，否则仍会返回视频副本。
- 普通 ComfyUI 编辑器增加 ZIP 下载链接；切换到 ZIP 时清空旧视频预览。

## RunningHub 维护者同步步骤

1. 在平台实际使用的 `custom_nodes/ComfyUI-WinxVideo4K` 更新仓库；如有平台本地改动，先合并并保留上传/COS 适配。
2. 本次变更文件为 `streaming.py`、`web/winx_video_app.js`，以及新增示例、文档和本地测试。**无需重下三份模型，无需新增 Python 依赖。**
3. 同步节点索引，使 `/object_info/WinxVideoApp` 中包含 `input.optional.zip_output = ["BOOLEAN", {"default": false, ...}]`；同样更新并重启实际执行任务的 GPU 实例。编辑器出现开关不足以证明执行镜像已更新。
4. 导入新版独立工作流。应用的五个输入按上表映射，默认关闭 ZIP。
5. 分别用短片验收关闭/开启两种模式：关闭只能出现一个 MP4，开启只能出现一个 ZIP；ZIP 可下载、可解压、内含一个可播放且带原音轨的增强视频。帧率与尺寸须符合所选参数，不能同时显示两个 MP4 或 MP4+ZIP。
6. 验收后更新原 AI 应用对应的工作流快照；保留已验证的 V4 以便回退。

仅更新 GitHub 或保存草稿不等于 RunningHub 执行实例和正式应用已同步。ZIP 附件在目标平台的下载行为仍需云端验收。

## 本地验证入口

`tests/validate_output_switch.py` 使用真实 ComfyUI `validate_prompt` / `PromptExecutor`、Video4K/RIFE ONNX 和 FFmpeg，分别检查旧 API 省略字段、BOOLEAN 关闭、BOOLEAN 开启三种情况；检查单一 UI 输出、1.5 倍尺寸、48fps、音轨、ZIP 完整性与 MP4 字节一致性。此脚本不提交云端任务。

```text
python tests/validate_output_switch.py --comfy /本地ComfyUI \
  --models /三份模型所在目录 --ffmpeg /FFmpeg目录/ffmpeg \
  --output /本地测试输出目录
```

现成方案参考：`wzcnly/comfyUI-solarL-Zip` 的 `nodes.py` 文件描述符；`7BEII/Comfyui_PDuse` 的 ZIP 节点仅返回文字说明，无法直接解决本应用的单一附件输出；`fudosanit/ComfyUI-ZipOutput` 会扫描 output 且默认删除旧 ZIP，未采用其实现。
