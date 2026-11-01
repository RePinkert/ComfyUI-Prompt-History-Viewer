import json
import os
import time
import html as html_lib

from aiohttp import web
from server import PromptServer

import folder_paths

LOG_FILE_NAME = "prompt_history_log.jsonl"
VIEW_FILE_NAME = "prompt_history.html"

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


def _output_dir():
    try:
        return folder_paths.get_output_directory()
    except Exception:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "output")


def _log_path():
    return os.path.join(_output_dir(), LOG_FILE_NAME)


def _esc(text):
    return html_lib.escape(text or "", quote=True)


def _preview(text):
    """Entry body: full text, wrapped (matches Ditto, which shows the whole item)."""
    return text or ""


def _read_log(path):
    entries = []
    if not os.path.exists(path):
        return entries
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Prompt History</title>
<style>
  :root {
    --bg: #1f1f1f;
    --bg-alt: #262626;
    --fg: #dcdcdc;
    --fg-dim: #8f8f8f;
    --accent: #4a9eff;
    --border: #343434;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; height: 100%;
    background: var(--bg); color: var(--fg);
    font-family: "Segoe UI", "Microsoft YaHei", system-ui, sans-serif;
    font-size: 14px;
  }
  body { display: flex; flex-direction: column; }
  header {
    display: flex; align-items: baseline; gap: 12px;
    padding: 10px 14px; background: var(--bg-alt);
    border-bottom: 1px solid var(--border); flex: 0 0 auto;
  }
  header h1 { margin: 0; font-size: 15px; font-weight: 600; letter-spacing: .3px; }
  header .meta { color: var(--fg-dim); font-size: 12px; }
  #list { flex: 1 1 auto; overflow-y: auto; padding: 6px; }
  .entry {
    display: flex; gap: 10px; align-items: flex-start;
    background: var(--bg-alt); border: 1px solid var(--border);
    border-radius: 4px; padding: 8px 10px; margin-bottom: 5px;
    cursor: pointer; transition: background .12s ease, border-color .12s ease;
    user-select: none;
  }
  .entry:hover { background: #2f2f2f; border-color: #4a4a4a; }
  .entry.copied { border-color: var(--accent); background: #2b3440; }
  .idx { color: var(--fg-dim); font-size: 12px; min-width: 26px; text-align: right; padding-top: 2px; }
  .body { flex: 1 1 auto; min-width: 0; }
  .preview { line-height: 1.5; word-break: break-word; white-space: pre-wrap; }
  .ts { color: var(--fg-dim); font-size: 11px; margin-top: 4px; }
  .badge {
    display: none; color: var(--accent); font-size: 11px; white-space: nowrap; padding-top: 2px;
  }
  .entry.copied .badge { display: inline; }
  footer {
    flex: 0 0 auto; display: flex; align-items: center; gap: 10px;
    padding: 8px 12px; background: var(--bg-alt);
    border-top: 1px solid var(--border);
  }
  #search {
    flex: 0 0 260px; background: #1a1a1a; color: var(--fg);
    border: 1px solid var(--border); border-radius: 3px;
    padding: 6px 9px; font-size: 13px; outline: none;
  }
  #search:focus { border-color: var(--accent); }
  #count { color: var(--fg-dim); font-size: 12px; }
  .empty { color: var(--fg-dim); padding: 24px; text-align: center; }
  .toast {
    position: fixed; right: 16px; bottom: 52px; background: var(--accent);
    color: #10161d; padding: 7px 14px; border-radius: 4px; font-size: 13px;
    opacity: 0; transition: opacity .2s ease; pointer-events: none;
  }
  .toast.show { opacity: 1; }
  #manual {
    display: none; position: fixed; left: 12px; right: 12px; bottom: 56px;
    height: 120px; background: #1a1a1a; color: var(--fg);
    border: 1px solid var(--accent); border-radius: 4px; padding: 8px;
    font-size: 13px; z-index: 100; resize: vertical;
  }
</style>
</head>
<body>
<header>
  <h1>Prompt History</h1>
  <span class="meta">__META__</span>
</header>
<div id="list">__ENTRIES__</div>
<footer>
  <input id="search" type="text" placeholder="搜索" autocomplete="off">
  <span id="count"></span>
</footer>
<div class="toast" id="toast">已复制</div>
<textarea id="manual" spellcheck="false"></textarea>
<script>
(function () {
  var ENTRIES = __DATA__;
  var list = document.getElementById('list');
  var search = document.getElementById('search');
  var count = document.getElementById('count');
  var toast = document.getElementById('toast');

  function showManualCopy(text) {
    var box = document.getElementById('manual');
    box.value = text;
    box.style.display = 'block';
    box.focus();
    box.select();
  }

  function copyFallback(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }

  function copyText(text) {
    // 1) modern clipboard API (works on file:// in Chrome/Edge - secure context)
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        showToast('已复制该条提示词');
      }, function () {
        if (copyFallback(text)) { showToast('已复制该条提示词'); }
        else { showManualCopy(text); showToast('自动复制被浏览器阻止，请按 Ctrl+C'); }
      });
      return;
    }
    // 2) execCommand fallback
    if (copyFallback(text)) {
      showToast('已复制该条提示词');
    } else {
      showManualCopy(text);
      showToast('自动复制被浏览器阻止，请按 Ctrl+C');
    }
  }

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(function () { toast.classList.remove('show'); }, 1400);
  }

  function markCopied(el) {
    var prev = list.querySelector('.entry.copied');
    if (prev) prev.classList.remove('copied');
    el.classList.add('copied');
    setTimeout(function () { el.classList.remove('copied'); }, 1200);
  }

  list.addEventListener('click', function (ev) {
    var el = ev.target.closest('.entry');
    if (!el) return;
    var idx = parseInt(el.getAttribute('data-index'), 10);
    var item = ENTRIES[idx];
    if (!item) return;
    markCopied(el);
    copyText(item.text);
  });

  function applyFilter() {
    var q = search.value.trim().toLowerCase();
    var shown = 0;
    var nodes = list.querySelectorAll('.entry');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var hay = el.getAttribute('data-search') || '';
      var hit = !q || hay.indexOf(q) !== -1;
      el.style.display = hit ? '' : 'none';
      if (hit) shown++;
    }
    count.textContent = q ? (shown + ' / ' + ENTRIES.length) : (ENTRIES.length + ' 条');
  }

  search.addEventListener('input', applyFilter);
  applyFilter();
})();
</script>
</body>
</html>
"""


def _render_html(entries):
    newest_first = sorted(
        entries, key=lambda e: (e.get("epoch", 0), e.get("seq", 0)), reverse=True
    )

    blocks = []
    data = []
    for i, e in enumerate(newest_first):
        text = e.get("text", "")
        ts = e.get("ts", "")
        data.append({"text": text, "ts": ts})
        blocks.append(
            '<div class="entry" data-index="{i}" data-search="{search}">'
            '<div class="idx">{num}</div>'
            '<div class="body">'
            '<div class="preview">{preview}</div>'
            '<div class="ts">{ts}</div>'
            '</div>'
            '<div class="badge">已复制</div>'
            '</div>'.format(
                i=i,
                num=i + 1,
                search=_esc(text.lower()),
                preview=_esc(_preview(text)),
                ts=_esc(ts),
            )
        )

    if blocks:
        entries_html = "\n".join(blocks)
    else:
        entries_html = '<div class="empty">暂无记录</div>'

    meta = "共 {0} 条 · 更新于 {1}".format(
        len(newest_first),
        time.strftime("%Y-%m-%d %H:%M:%S"),
    )

    return (
        HTML_TEMPLATE
        .replace("__ENTRIES__", entries_html)
        .replace("__META__", _esc(meta))
        .replace("__DATA__", json.dumps(data, ensure_ascii=False))
    )


def _history_page(query, offset, limit):
    """Newest-first slice of the history log, filtered by a case-insensitive query.

    Entry numbers stay tied to the unfiltered log (1 = newest), so they match
    the standalone HTML viewer regardless of the active search.
    """
    entries = _read_log(_log_path())
    entries.reverse()

    numbered = [
        {"n": i + 1, "ts": e.get("ts", ""), "text": e.get("text", "")}
        for i, e in enumerate(entries)
    ]

    if query:
        needle = query.lower()
        numbered = [e for e in numbered if needle in e["text"].lower()]

    total = len(numbered)
    return total, numbered[offset:offset + limit]


@PromptServer.instance.routes.get("/prompt_history/entries")
def get_prompt_history_entries(request):
    try:
        limit = int(request.query.get("limit", DEFAULT_PAGE_SIZE))
        offset = int(request.query.get("offset", 0))
    except ValueError:
        limit, offset = DEFAULT_PAGE_SIZE, 0
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    total, entries = _history_page(request.query.get("q", ""), offset, limit)
    return web.json_response({"total": total, "offset": offset, "entries": entries})


class PromptHistorySaveNode:
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "utils"
    DESCRIPTION = (
        "Appends the input prompt to a timestamped history log and regenerates a "
        "Ditto-style HTML viewer (newest first, click an entry to copy it)."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"forceInput": True, "multiline": True}),
            },
        }

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def save(self, text=None, **kwargs):
        text = text if isinstance(text, str) else ""

        out_dir = _output_dir()
        os.makedirs(out_dir, exist_ok=True)
        log_path = os.path.join(out_dir, LOG_FILE_NAME)
        view_path = os.path.join(out_dir, VIEW_FILE_NAME)

        if text.strip():
            existing = _read_log(log_path)
            entry = {
                "epoch": time.time(),
                "seq": len(existing),
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "text": text,
            }
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            existing.append(entry)
            with open(view_path, "w", encoding="utf-8") as f:
                f.write(_render_html(existing))

        return {"ui": {"text": [text]}, "result": (text,)}


NODE_CLASS_MAPPINGS = {
    "PromptHistorySave": PromptHistorySaveNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptHistorySave": "生成记录 (历史 / Ditto)",
}
