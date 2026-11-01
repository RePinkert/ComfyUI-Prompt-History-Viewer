import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

// Ditto-style history panel rendered on the node itself.
// Entries come from /api/prompt_history/entries (newest first) and are pulled
// in 50 at a time; scrolling to the bottom asks the server for the next page.

const PAGE_SIZE = 50;
const MIN_SIZE = [360, 480];
const STYLE_ID = "prompt-history-viewer-style";

function ensureStyles() {
	if (document.getElementById(STYLE_ID)) return;
	const style = document.createElement("style");
	style.id = STYLE_ID;
	style.textContent = `
.phv-root {
	display: flex;
	flex-direction: column;
	width: 100%;
	height: 100%;
	min-height: 0;
	box-sizing: border-box;
	overflow: hidden;
	background: var(--comfy-menu-secondary-bg, #292929);
	color: var(--fg-color, #dcdcdc);
	font-size: 11px;
	line-height: 1.45;
}
.phv-head {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 4px 6px;
	border-bottom: 1px solid var(--border-color, #4e4e4e);
	background: var(--comfy-menu-bg, #353535);
	flex: 0 0 auto;
}
.phv-title { font-weight: 600; white-space: nowrap; }
.phv-count { color: var(--descrip-text, #999); margin-left: auto; white-space: nowrap; }
.phv-search {
	flex: 1 1 auto;
	min-width: 0;
	box-sizing: border-box;
	padding: 2px 5px;
	border: 1px solid var(--border-color, #4e4e4e);
	border-radius: 3px;
	background: var(--comfy-input-bg, #222);
	color: var(--fg-color, #dcdcdc);
	font: inherit;
}
.phv-search:focus { outline: 1px solid var(--primary-bg, #236692); }
.phv-list {
	flex: 1 1 auto;
	min-height: 0;
	overflow-y: auto;
	overflow-x: hidden;
}
.phv-entry {
	display: flex;
	gap: 6px;
	padding: 4px 6px;
	border-bottom: 1px solid var(--border-color, #4e4e4e);
	cursor: pointer;
}
.phv-entry:hover { background: var(--comfy-menu-bg, #353535); }
.phv-entry.copied { background: var(--primary-bg, #236692); color: var(--primary-fg, #fff); }
.phv-idx {
	flex: 0 0 auto;
	min-width: 22px;
	text-align: right;
	color: var(--descrip-text, #999);
	font-variant-numeric: tabular-nums;
}
.phv-entry.copied .phv-idx, .phv-entry.copied .phv-ts { color: var(--primary-fg, #fff); }
.phv-body { flex: 1 1 auto; min-width: 0; }
.phv-text {
	white-space: pre-wrap;
	word-break: break-word;
	display: -webkit-box;
	-webkit-line-clamp: 4;
	-webkit-box-orient: vertical;
	overflow: hidden;
}
.phv-entry.expanded .phv-text { -webkit-line-clamp: unset; }
.phv-ts { color: var(--descrip-text, #999); font-size: 10px; margin-top: 2px; }
.phv-empty { padding: 10px 6px; color: var(--descrip-text, #999); text-align: center; }
.phv-foot {
	flex: 0 0 auto;
	padding: 3px 6px;
	border-top: 1px solid var(--border-color, #4e4e4e);
	color: var(--descrip-text, #999);
	text-align: center;
}
`;
	document.head.appendChild(style);
}

async function copyToClipboard(text) {
	try {
		if (navigator.clipboard && window.isSecureContext) {
			await navigator.clipboard.writeText(text);
			return true;
		}
	} catch (err) {
		/* fall through to the textarea fallback */
	}
	const ta = document.createElement("textarea");
	ta.value = text;
	ta.style.position = "fixed";
	ta.style.left = "-9999px";
	document.body.appendChild(ta);
	ta.select();
	let ok = false;
	try {
		ok = document.execCommand("copy");
	} catch (err) {
		ok = false;
	}
	document.body.removeChild(ta);
	return ok;
}

function buildPanel(node) {
	ensureStyles();

	const root = document.createElement("div");
	root.className = "phv-root";

	const head = document.createElement("div");
	head.className = "phv-head";

	const search = document.createElement("input");
	search.className = "phv-search";
	search.type = "text";
	search.placeholder = "搜索历史记录";
	search.spellcheck = false;

	const count = document.createElement("span");
	count.className = "phv-count";

	head.append(search, count);

	const list = document.createElement("div");
	list.className = "phv-list";

	const foot = document.createElement("div");
	foot.className = "phv-foot";

	root.append(head, list, foot);

	const state = {
		entries: [],
		total: 0,
		offset: 0,
		query: "",
		loading: false,
		done: false,
		error: "",
		requestId: 0,
	};

	const widget = node.addDOMWidget("history", "div", root, {
		serialize: false,
		getMinHeight: () => 200,
		getMaxHeight: () => 4000,
	});
	widget.serialize = false;
	widget.options.serialize = false;

	const render = () => {
		list.replaceChildren();
		if (!state.entries.length) {
			const empty = document.createElement("div");
			empty.className = "phv-empty";
			empty.textContent = state.query ? "没有匹配的记录" : "暂无记录";
			list.appendChild(empty);
		} else {
			const frag = document.createDocumentFragment();
			for (let i = 0; i < state.entries.length; i++) {
				const entry = state.entries[i];
				const row = document.createElement("div");
				row.className = "phv-entry";
				row.dataset.idx = String(i);

				const idx = document.createElement("div");
				idx.className = "phv-idx";
				idx.textContent = String(entry.n);

				const body = document.createElement("div");
				body.className = "phv-body";

				const text = document.createElement("div");
				text.className = "phv-text";
				text.textContent = entry.text;

				const ts = document.createElement("div");
				ts.className = "phv-ts";
				ts.textContent = entry.ts;

				body.append(text, ts);
				row.append(idx, body);
				frag.appendChild(row);
			}
			list.appendChild(frag);
		}
		count.textContent = state.total > state.entries.length
			? `${state.entries.length} / ${state.total}`
			: String(state.total);
		foot.textContent = state.error
			? state.error
			: state.done
				? (state.entries.length ? "已到末尾" : "")
				: "滚动加载更多…";
	};

	const load = async (reset) => {
		if (reset) {
			// A reset supersedes any in-flight page load.
			state.requestId += 1;
			state.entries = [];
			state.offset = 0;
			state.done = false;
		} else if (state.loading) {
			return;
		}
		const requestId = ++state.requestId;
		state.loading = true;
		state.error = "";

		const params = new URLSearchParams({
			limit: String(PAGE_SIZE),
			offset: String(state.offset),
		});
		if (state.query) params.set("q", state.query);
		foot.textContent = "加载中…";

		try {
			const res = await api.fetchApi(`/prompt_history/entries?${params}`);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();
			if (requestId !== state.requestId) return;
			state.total = data.total ?? 0;
			state.entries.push(...data.entries);
			state.offset += data.entries.length;
			state.done = state.offset >= state.total || data.entries.length < PAGE_SIZE;
		} catch (err) {
			if (requestId !== state.requestId) return;
			state.done = true;
			state.error = `加载失败: ${err.message}`;
		} finally {
			if (requestId === state.requestId) {
				state.loading = false;
				render();
			}
		}
	};

	// Keep the canvas from zooming while the list scrolls under the cursor.
	list.addEventListener("wheel", (event) => event.stopPropagation(), { passive: true });

	list.addEventListener("scroll", () => {
		if (state.loading || state.done) return;
		if (list.scrollTop + list.clientHeight >= list.scrollHeight - 24) load(false);
	});

	list.addEventListener("click", async (event) => {
		const row = event.target.closest(".phv-entry");
		if (!row) return;
		const entry = state.entries[Number(row.dataset.idx)];
		if (!entry) return;
		if (!(await copyToClipboard(entry.text))) return;
		row.classList.add("copied");
		setTimeout(() => row.classList.remove("copied"), 900);
	});

	list.addEventListener("dblclick", (event) => {
		const row = event.target.closest(".phv-entry");
		if (row) row.classList.toggle("expanded");
	});

	let searchTimer = null;
	search.addEventListener("input", () => {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(() => {
			state.query = search.value.trim();
			load(true);
		}, 250);
	});
	search.addEventListener("keydown", (event) => {
		event.stopPropagation();
		if (event.key === "Enter") {
			clearTimeout(searchTimer);
			state.query = search.value.trim();
			load(true);
		}
	});

	node.phvPanel = { state, render, load };

	render();
	load(true);
}

app.registerExtension({
	name: "prompt_history_viewer.Display",

	// Vue-node path: the node class invokes this event from its constructor.
	nodeCreated(node) {
		if (node?.constructor?.comfyClass !== "PromptHistorySave") return;
		if (node.phvPanel) return;
		buildPanel(node);
		node.setSize([Math.max(node.size[0], MIN_SIZE[0]), Math.max(node.size[1], MIN_SIZE[1])]);
	},

	async beforeRegisterNodeDef(nodeType, nodeData) {
		if (nodeData.name !== "PromptHistorySave") return;

		// LiteGraph path: the graph calls this on the node instance.
		const onNodeCreated = nodeType.prototype.onNodeCreated;
		nodeType.prototype.onNodeCreated = function () {
			onNodeCreated?.apply(this, arguments);
			if (this.phvPanel) return;
			buildPanel(this);
			this.setSize([Math.max(this.size[0], MIN_SIZE[0]), Math.max(this.size[1], MIN_SIZE[1])]);
		};

		const onExecuted = nodeType.prototype.onExecuted;
		nodeType.prototype.onExecuted = function (message) {
			onExecuted?.apply(this, arguments);
			this.phvPanel?.load(true);
		};

		const configure = nodeType.prototype.configure;
		nodeType.prototype.configure = function () {
			configure?.apply(this, arguments);
			this.phvPanel?.load(true);
		};
	},
});
