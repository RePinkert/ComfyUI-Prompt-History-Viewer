# ComfyUI Prompt History Viewer — 生成记录 (历史 / Ditto)

一个轻量的 ComfyUI 自定义节点：把每次生成的 prompt 追加到带时间戳的 JSONL 历史日志，并自动重新生成一个 **Ditto 风格的 HTML 查看页**（最新在前，点击条目即可复制）。

## 功能

- 每次出图自动把 prompt 写入 `output/prompt_history_log.jsonl`（含时间戳与序号）
- 自动生成 / 刷新 `output/prompt_history.html` 查看页，双击即可用浏览器打开
- 内置分页搜索 API（`/prompt_history/entries`，支持 `q` / `limit` / `offset`）

## 安装

方式一（推荐，通过 ComfyUI-Manager）：
在 Manager 中搜索 `comfyui-prompt-history-viewer`，点 Install。

方式二（手动）：
```bash
cd ComfyUI/custom_nodes
git clone https://github.com/RePinkert/comfyui-prompt-history-viewer.git
```

无额外 Python 依赖。

## 使用

1. 在节点菜单 `utils` 分类下添加 **生成记录 (历史 / Ditto)** 节点
2. 把 CLIP Text Encode（或任意 STRING）连入 `text` 输入
3. 每次队列执行后，prompt 会追加进日志并刷新 HTML 查看表

## 文件结构

```
__init__.py            # 节点注册 + 前端目录
prompt_history_node.py # 节点与服务端 API
web/js/                # 前端扩展
```

## License

MIT
