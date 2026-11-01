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
git clone https://github.com/RePinkert/ComfyUI-Prompt-History-Viewer.git
```

无额外 Python 依赖。

## 使用

### 1. 添加节点

在节点菜单 `utils` 分类下添加 **生成记录 (历史 / Ditto)** 节点。

### 2. 连接任意既有工作流

本节点是**平铺的独立记录节点**：只订阅最终的 prompt 字符串（STRING），不干预生图链路，不需要改采样 / 文本编码 —— 可以直接外接到任何已有工作流。

普通（非子图）工作流：

```
[CLIP Text Encode] ──STRING──▶ ... ──▶ [KSampler]
        │
        └────────STRING──▶ [生成记录 (历史 / Ditto)]
```

### 3. 子图（Subgraph）工作流的接法

如果模板使用了 subgraph（如官方 Krea / Flux 模板会折叠成一个大卡片），prompt 链路在子图内部，无法直接订阅。做法：

1. 双击子图卡片进入内部，找到最终流向（或来自）CLIP Text Encode 的 STRING 链路起点节点
2. 给该节点的 STRING 输出加一条到 **子图输出（Subgraph Output）** 的新链路，输出 pin 类型为 STRING（可命名如 `PROMPT`）
3. 返回外层画布：子图卡片上会出现新的 `PROMPT` 输出脚钉
4. `subgraph.PROMPT ──▶ 生成记录.text`，节点平铺放置在 SaveImage 同级即可

```
[ 子图 ] ──IMAGE──>  [SaveImage]
       │
       └─PROMPT──▶ [生成记录 (历史 / Ditto)]
```

> 参考：官方模板 `image_krea2_turbo_t2i` 已按此方式接入并实测通过。

## 输出文件

| 文件 | 说明 |
|---|---|
| `output/prompt_history_log.jsonl` | 按时间顺序追加的历史日志（供其它工具读取） |
| `output/prompt_history.html` | 可视化查看页，出图后自动刷新，浏览器打开即用 |

HTTP API（默认 `http://127.0.0.1:8188`）：
```
GET /prompt_history/entries?q=<关键词>&limit=<条数>&offset=<偏移>
```

## 文件结构

```
__init__.py            # 节点注册 + 前端目录
prompt_history_node.py # 节点与服务端 API
web/js/                # 前端扩展
```

## License

MIT
