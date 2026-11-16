import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "WinxVideo4K.StreamingApp",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "WinxVideoApp") return;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = created?.apply(this, arguments);
            const videoWidget = this.widgets.find((widget) => widget.name === "video");
            const button = this.addWidget("button", "上传视频 / Upload video", null, () => {
                const input = document.createElement("input");
                input.type = "file";
                input.accept = "video/*,.mkv,.m4v,.ts,.m2ts";
                input.onchange = async () => {
                    const file = input.files?.[0];
                    if (!file) return;
                    try {
                        const body = new FormData();
                        body.append("image", file);
                        body.append("type", "input");
                        const response = await api.fetchApi("/upload/image", { method: "POST", body });
                        if (!response.ok) throw new Error(`Upload failed (${response.status})`);
                        const data = await response.json();
                        const filename = data.subfolder ? `${data.subfolder}/${data.name}` : data.name;
                        if (!filename) throw new Error("Upload did not return a filename");
                        if (!videoWidget.options.values.includes(filename)) videoWidget.options.values.push(filename);
                        videoWidget.value = filename;
                        videoWidget.callback?.(filename);
                        app.graph.setDirtyCanvas(true, true);
                    } catch (error) {
                        window.alert(String(error));
                    }
                };
                input.click();
            });
            button.serialize = false;
            this.size = [Math.max(this.size[0], 460), this.computeSize()[1]];
            return result;
        };

        const executed = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            const result = executed?.apply(this, arguments);
            const preview = message.gifs?.[0];
            if (!preview) return result;
            if (!this.winxPreview) {
                const video = document.createElement("video");
                video.controls = true;
                video.preload = "metadata";
                video.style.cssText = "width:100%;height:100%;object-fit:contain;background:#111";
                const widget = this.addDOMWidget("winx_preview", "video", video, { serialize: false });
                widget.computeSize = (width) => [width, 260];
                widget.serialize = false;
                this.winxPreview = video;
            }
            const params = new URLSearchParams({ filename: preview.filename, subfolder: preview.subfolder || "", type: preview.type });
            this.winxPreview.src = api.apiURL(`/view?${params}`);
            this.setSize(this.computeSize());
            app.graph.setDirtyCanvas(true, true);
            return result;
        };

        const removed = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            if (this.winxPreview) {
                this.winxPreview.pause();
                this.winxPreview.removeAttribute("src");
                this.winxPreview.load();
            }
            return removed?.apply(this, arguments);
        };
    },
});
