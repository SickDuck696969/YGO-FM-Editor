"use strict";
const $ = (s) => document.querySelector(s);
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ],
  );
const tabs = {
  home: [
    "Overview",
    "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
    "",
  ],
  cards: [
    "Card studio",
    "M6 3h13v17H6z M3 7v15h12 M9 6h7v7H9z",
    "Edit artwork, stats and Guardian Stars.",
  ],
  fusion: [
    "Fusion lab",
    "M3 5h3l9 14h6 M3 19h3l9-14h6 M18 2l3 3-3 3 M18 16l3 3-3 3",
    "Build and search material combinations.",
  ],
  drops: [
    "Duelist drops",
    "M3 7l9-4 9 4-9 4z M3 12l9 4 9-4 M3 17l9 4 9-4",
    "Tune each opponent’s reward pools.",
  ],
  deck: [
    "Starter deck",
    "M3 8l9-4 9 4-9 4z M3 12l9 4 9-4 M3 16l9 4 9-4",
    "Build a 40-card deck for a fresh save.",
  ],
  save: [
    "Save editor",
    "M4 3h13l3 3v15H4z M8 3v6h8V3 M8 21v-7h8v7",
    "Edit a memory card, trunk and campaign.",
  ],
  export: [
    "Rewards & export",
    "M4 14v6h16v-6 M12 16V3 M8 7l4-4 4 4",
    "Set duel rewards and download your edits.",
  ],
};
const icon = (k) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${tabs[k][1]}"/></svg>`;
const baseName = "Yu-Gi-Oh! - Forbidden Memories";
let page = "home",
  game = null,
  meta = null,
  save = null,
  originalSave = null,
  saveName = "",
  discName = "",
  active = 1,
  dirty = false,
  formDirty = false;
let deck = [],
  player = "PLAYER",
  chips = 0,
  slots = [1, 2, 3],
  materialSets = [null, null],
  opponent = 0,
  rank = 0,
  weights = [];
let reward = null,
  downloads = [],
  artCache = {},
  replacements = {},
  fusionQuery = "",
  fusionScope = "everywhere",
  fusionPage = 0;
let job = 0,
  worker,
  serial = 0,
  pending = new Map(),
  revision = 0,
  noticeTimer,
  onImage;
const browsers = {};
const copy = (v) => structuredClone(v);
const cidName = (id) =>
  game?.cards[id - 1]?.name || meta?.names[id] || `Card ${id}`;
const btn = (text, id, cl = "") =>
  `<button id="${id}" class="${cl}">${esc(text)}</button>`;
const on = (id, fn, ev = "click") => {
  const el = document.getElementById(id);
  if (el)
    el.addEventListener(ev, (e) =>
      Promise.resolve()
        .then(() => fn(e))
        .catch(fail),
    );
};
function fail(error) {
  console.error(error);
  notice(error.message || error, true);
}
function notice(text, error = false) {
  clearTimeout(noticeTimer);
  $("#notice").textContent = text;
  $("#notice").setAttribute("role", error ? "alert" : "status");
  noticeTimer = setTimeout(
    () => ($("#notice").textContent = ""),
    error ? 12000 : 4500,
  );
}
function rpc(op, args = {}, files = []) {
  if (!worker) {
    worker = new Worker("./worker.js");
    worker.onmessage = ({ data }) => {
      if (data.progress) {
        $("#busyText").textContent = data.progress;
        return;
      }
      const handle = pending.get(data.id);
      if (!handle) return;
      pending.delete(data.id);
      data.error
        ? handle.reject(Error(data.error))
        : handle.resolve(data.result);
    };
    worker.onerror = (e) => {
      for (const h of pending.values())
        h.reject(Error(e.message || "The browser engine stopped."));
      pending.clear();
      worker.terminate();
      worker = null;
    };
  }
  return new Promise((resolve, reject) => {
    const id = ++serial;
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, op, args, files });
  });
}
async function work(label, fn) {
  job++;
  $("#busy").hidden = false;
  $("#busyText").textContent = label;
  try {
    return await fn();
  } finally {
    if (!--job) $("#busy").hidden = true;
  }
}
async function ready() {
  if (!meta) meta = await rpc("metadata");
}
function revoke() {
  for (const d of downloads) URL.revokeObjectURL(d.url);
  downloads = [];
}
function changed() {
  dirty = true;
  revoke();
}
function downloadLink(blob, name) {
  return { url: URL.createObjectURL(blob), name };
}
function downloadNow(blob, name) {
  const link = downloadLink(blob, name),
    a = document.createElement("a");
  a.href = link.url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(link.url), 60000);
}
function clearDraft() {
  if (formDirty && !confirm("Discard the unapplied card fields?")) return false;
  formDirty = false;
  return true;
}
function go(k) {
  if (!tabs[k] || !clearDraft()) return;
  page = k;
  render();
}
function field(label, name, val, attrs = "", type = "text") {
  return `<label class="field">${esc(label)}<input name="${name}" type="${type}" value="${esc(val)}" ${attrs}></label>`;
}
function select(label, name, list, value) {
  return `<label class="field">${esc(label)}<select name="${name}">${list.map((v, i) => `<option value="${i}" ${i === value ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>`;
}
function title(k, extra = "") {
  return `<div class="title"><div><h1>${tabs[k][0]}</h1><p>${tabs[k][2]}</p></div>${extra}</div>`;
}
const thumb = (id) => {
  if (!game) return "";
  const i = id - 1;
  const override = replacements[id];
  return `<i class="thumb" aria-hidden="true" style="${override ? `background-image:url('${override}');background-size:40px 32px` : `background-position:${-(i % 16) * 40}px ${-Math.floor(i / 16) * 32}px`}"></i>`;
};
function badge(key, i, labels) {
  const src = game.icons[key]?.[i],
    label = esc(labels[i] ?? "");
  return src
    ? `<img class="tagicon" src="${src}" alt="${label}" title="${label}">`
    : label;
}
function row(id, sub = "", selected = false, toggle = false) {
  const c = game?.cards[id - 1];
  return `<button class="row ${selected ? "selected" : ""}" data-id="${id}" ${toggle ? `aria-pressed="${selected}"` : ""}>${thumb(id)}<span><strong>${esc(cidName(id))}</strong><small>${sub || (!c ? `#${id}` : `#${id} · ${badge("type", c.type_id, meta.types)} ${badge("attribute", c.attribute, meta.attributes)} ${badge("guardian", c.gs1, meta.stars)} ${badge("guardian", c.gs2, meta.stars)} · ★ ${c.level} · ${c.atk} / ${c.def_}`)}</small></span></button>`;
}
function paginate(total, pg, n) {
  return `<div class="pagebar"><button data-prev ${pg === 0 ? "disabled" : ""}>← Previous</button><span>${total ? `${pg * n + 1}–${Math.min((pg + 1) * n, total)} of ${total.toLocaleString()}` : "0 matches"}</span><button data-next ${(pg + 1) * n >= total ? "disabled" : ""}>Next →</button></div>`;
}
function library(root, key, choose, options = {}) {
  const {
    ids = null,
    context = null,
    summary = null,
    selected = 0,
    tile,
    onMatches,
  } = options;
  const state = (browsers[key] ||= {
    q: "",
    sort: "id",
    page: 0,
    types: [],
    attributes: [],
    levels: [],
    minAtk: "",
    maxAtk: "",
    minDef: "",
    maxDef: "",
  });
  const opts = (list, vals) =>
    list
      .map(
        (v, i) =>
          `<option value="${i}" ${vals.includes(i) ? "selected" : ""}>${esc(v)}</option>`,
      )
      .join("");
  const filter = game
    ? `<details><summary>Card filters</summary><div class="filtergrid">${[
        ["Types", "types", meta.types],
        ["Attributes", "attributes", meta.attributes],
        ["Levels", "levels", Array.from({ length: 13 }, (_, i) => i)],
      ]
        .map(
          ([s, k, v]) =>
            `<label class="field">${s}<select multiple size="3" name="${k}">${opts(v, state[k])}</select></label>`,
        )
        .join("")}${[
        ["Min ATK", "minAtk"],
        ["Max ATK", "maxAtk"],
        ["Min DEF", "minDef"],
        ["Max DEF", "maxDef"],
      ]
        .map(([s, k]) => field(s, k, state[k], 'min="0" max="5110"', "number"))
        .join("")}</div><button data-clear>Clear filters</button></details>`
    : "";
  root.innerHTML = `<div class="bar"><input type="search" aria-label="Search cards" placeholder="Search cards by name or ID" value="${esc(state.q)}"><select aria-label="Sort cards">${["id", "name", ...(game ? ["atk", "def_"] : [])].map((k) => `<option value="${k}" ${state.sort === k ? "selected" : ""}>${{ id: "Card ID", name: "Name", atk: "ATK", def_: "DEF" }[k]}</option>`).join("")}</select></div>${filter}<div class="results"></div>`;
  function draw() {
    let match = (ids ?? Array.from({ length: 722 }, (_, i) => i + 1)).filter(
      (id) => {
        const c = game?.cards[id - 1];
        return (
          (cidName(id).toLowerCase().includes(state.q.toLowerCase()) ||
            String(id) === state.q) &&
          (!c ||
            ((!state.types.length || state.types.includes(c.type_id)) &&
              (!state.attributes.length ||
                state.attributes.includes(c.attribute)) &&
              (!state.levels.length || state.levels.includes(c.level)) &&
              ["Atk", "Def"].every((s) => {
                const v = s === "Atk" ? c.atk : c.def_;
                return (
                  (!state["min" + s] || v >= +state["min" + s]) &&
                  (!state["max" + s] || v <= +state["max" + s])
                );
              })))
        );
      },
    );
    match.sort((a, b) =>
      state.sort === "name"
        ? cidName(a).localeCompare(cidName(b))
        : state.sort === "id"
          ? a - b
          : (game?.cards[b - 1][state.sort] || 0) -
              (game?.cards[a - 1][state.sort] || 0) || a - b,
    );
    const n = 36;
    state.page = Math.max(
      0,
      Math.min(state.page, Math.ceil(match.length / n) - 1),
    );
    const results = root.querySelector(".results");
    results.innerHTML = `<div class="list ${tile ? "fusion-grid" : ""}">${
      (tile ? match : match.slice(state.page * n, (state.page + 1) * n))
        .map((id) =>
          tile
            ? tile(id)
            : row(
                id,
                summary?.(id),
                selected instanceof Set ? selected.has(id) : id === selected,
                selected instanceof Set,
              ),
        )
        .join("") || '<div class="empty">No matching cards.</div>'
    }</div>${tile ? "" : paginate(match.length, state.page, n)}`;
    onMatches?.(match, results);
    if (!tile) {
      results.querySelector("[data-prev]").onclick = () => {
        state.page--;
        draw();
      };
      results.querySelector("[data-next]").onclick = () => {
        state.page++;
        draw();
      };
    }
    results.querySelector(".list").onclick = (e) => {
      const b = e.target.closest("[data-id]");
      if (b) Promise.resolve(choose(+b.dataset.id)).catch(fail);
    };
    if (context)
      results.querySelector(".list").oncontextmenu = (e) => {
        const b = e.target.closest("[data-id]");
        if (b) {
          e.preventDefault();
          context(+b.dataset.id);
        }
      };
  }
  root.querySelector("[type=search]").oninput = (e) => {
    state.q = e.target.value;
    state.page = 0;
    draw();
  };
  root.querySelector(".bar select").onchange = (e) => {
    state.sort = e.target.value;
    state.page = 0;
    draw();
  };
  for (const el of root.querySelectorAll("[name]"))
    el.oninput = () => {
      state[el.name] = el.multiple
        ? [...el.selectedOptions].map((o) => +o.value)
        : el.value;
      state.page = 0;
      draw();
    };
  if (game)
    root.querySelector("[data-clear]").onclick = () => {
      delete browsers[key];
      library(root, key, choose, options);
    };
  draw();
}
function pick(label, callback, ids = null) {
  $("#pickTitle").textContent = label;
  delete browsers.picker;
  library(
    $("#pickContent"),
    "picker",
    async (id) => {
      $("#picker").close();
      await callback(id);
    },
    { ids },
  );
  $("#picker").showModal();
  $("#pickContent input").focus();
}
function chooseImage(fn) {
  onImage = fn;
  $("#imageFile").click();
}
function home() {
  $("#view").innerHTML =
    `<section class="hero"><div><div class="overline">Yu-Gi-Oh! · PlayStation</div><h1>Forbidden<br>Memories</h1><p>${game ? `Editing ${esc(discName)}` : "Open your USA game disc to edit cards, build fusions and tune duel rewards."}</p>${btn(game ? "Continue editing →" : "Open disc image →", "heroOpen", "primary")}</div><div class="disc-art" aria-hidden="true"></div></section><h2 class="sectionhead">Editing tools</h2><div class="toolsgrid">${Object.keys(
      tabs,
    )
      .slice(1)
      .map(
        (k) =>
          `<button class="tooltile" data-page="${k}">${icon(k)}<span class="arrow">↗</span><strong>${tabs[k][0]}</strong><small>${tabs[k][2]}</small></button>`,
      )
      .join(
        "",
      )}</div><p class="info sectionhead">Disc images and saves stay in this browser. Download your work before closing the tab.</p>`;
  on("heroOpen", () => (game ? go("cards") : $("#discFile").click()));
}
let atlasUrl,
  originalCards = [],
  changedCardsOnly = false;
async function openDisc(files) {
  if (!files.length) return;
  if (
    ((game && (dirty || deck.length)) || formDirty) &&
    !confirm("Replace the current disc and discard its pending edits?")
  )
    return;
  await work("Opening disc and reading game artwork…", async () => {
    await ready();
    const next = await rpc("disc", {}, files);
    game = next;
    originalCards = next.cards.slice();
    changedCardsOnly = false;
    discName =
      files.find((f) => !/\.(cue|ccd)$/i.test(f.name))?.name || files[0].name;
    const imageUrl = URL.createObjectURL(
      await (await fetch(game.atlas)).blob(),
    );
    document.documentElement.style.setProperty("--atlas", `url("${imageUrl}")`);
    if (atlasUrl) URL.revokeObjectURL(atlasUrl);
    atlasUrl = imageUrl;
    delete game.atlas;
    active = 1;
    slots = [1, 2, 3];
    materialSets = [null, null];
    deck = [];
    reward = null;
    opponent = rank = fusionPage = 0;
    replacements = {};
    artCache = {};
    dirty = formDirty = false;
    revoke();
    go("cards");
  });
}
function gate(k) {
  $("#view").innerHTML =
    title(k) +
    `<section class="panel stack"><h2>Open a USA disc image</h2><p>Choose a BIN, IMG or ISO file. For a CUE or CCD, select its data file in the same dialog.</p><div>${btn("Choose disc image", "gateOpen", "primary")}</div></section>`;
  on("gateOpen", () => $("#discFile").click());
}
function render() {
  revision++;
  $("#crumb").textContent = tabs[page][0];
  document.querySelectorAll("nav button").forEach((b) => {
    b.classList.toggle("active", b.dataset.page === page);
    b.setAttribute("aria-current", b.dataset.page === page ? "page" : "false");
  });
  if (page === "home") return home();
  if (page === "save") return saveTab();
  if (!game) return gate(page);
  ({
    cards: cardsTab,
    fusion: fusionTab,
    drops: dropsTab,
    deck: deckTab,
    export: exportTab,
  })[page]();
}
function cardsTab() {
  const c = game.cards[active - 1],
    token = revision;
  $("#view").innerHTML =
    title("cards", btn("Reset all card edits", "resetCards")) +
    `<div class="split"><section class="panel"><h2>Card library</h2><label><input id="changedOnly" type="checkbox" ${changedCardsOnly ? "checked" : ""}> Changed cards only <span id="changeCount"></span></label><div id="library"></div></section><section class="panel"><div class="previewwrap"><div class="preview"><strong>${esc(c.name)}</strong><img id="fullArt" alt="${esc(c.name)} artwork"><small>★ ${c.level} · ${esc(meta.types[c.type_id])}<br>ATK ${c.atk} / DEF ${c.def_}</small></div><div><div class="overline">Card ${String(c.id).padStart(3, "0")}</div><h2>${esc(c.name)}</h2>${btn("Change artwork", "changeArt")}</div></div><form id="cardForm" class="cardform">${field("Name", "name", c.name, 'maxlength="36" required')}${field("Password", "password", c.password, 'pattern="[0-9a-fA-F]{8}" required')}${field("Attack", "atk", c.atk, 'min="0" max="5110" step="10" required', "number")}${field("Defense", "def_", c.def_, 'min="0" max="5110" step="10" required', "number")}${select("Type", "type_id", meta.types, c.type_id)}${select("Attribute", "attribute", meta.attributes, c.attribute)}${select("Guardian Star 1", "gs1", meta.stars, c.gs1)}${select("Guardian Star 2", "gs2", meta.stars, c.gs2)}${field("Level", "level", c.level, 'min="0" max="12" required', "number")}${field("Starchip cost", "star_cost", c.star_cost, 'min="0" max="999999" required', "number")}<label class="field wide">Description<textarea name="description" rows="3">${esc(c.description)}</textarea></label><button class="primary wide">Apply card changes</button></form></section></div>`;
  function refreshLibrary() {
    const changedIds = game.cards
      .filter((card) => {
        const original = originalCards[card.id - 1];
        return (
          replacements[card.id] ||
          Object.keys(original).some((key) => card[key] !== original[key])
        );
      })
      .map((card) => card.id);
    $("#changeCount").textContent = `(${changedIds.length})`;
    library(
      $("#library"),
      "cards",
      (id) => {
        if (clearDraft()) {
          active = id;
          render();
        }
      },
      { selected: active, ids: changedCardsOnly ? changedIds : null },
    );
  }
  $("#changedOnly").onchange = (event) => {
    changedCardsOnly = event.target.checked;
    if (browsers.cards) browsers.cards.page = 0;
    refreshLibrary();
  };
  refreshLibrary();
  const showArt = (src) => {
    if (revision === token) $("#fullArt").src = src;
  };
  if (artCache[active]) showArt(artCache[active]);
  else
    rpc("art", { id: c.id })
      .then((src) => {
        if (revision === token) {
          artCache[c.id] = src;
          showArt(src);
        }
      })
      .catch(fail);
  $("#cardForm").oninput = () => {
    formDirty = true;
  };
  $("#cardForm").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const data = { id: c.id };
      for (const [k, v] of new FormData(e.target))
        data[k] = ["name", "description", "password"].includes(k)
          ? v
          : Number(v);
      game.cards[c.id - 1] = await rpc("card", { card: data });
      formDirty = false;
      changed();
      render();
      notice("Card changes applied.");
    } catch (err) {
      fail(err);
    }
  };
  on("changeArt", () =>
    chooseImage(async (f) => {
      const { image, custom } = await rpc("artEdit", { id: c.id }, [f]);
      artCache[c.id] = image;
      if (custom) replacements[c.id] = image;
      else delete replacements[c.id];
      changed();
      showArt(image);
      refreshLibrary();
    }),
  );
  on("resetCards", async () => {
    if (!confirm("Restore all card fields and artwork from the disc?")) return;
    game.cards = await rpc("resetCards");
    artCache = {};
    replacements = {};
    formDirty = false;
    changed();
    render();
  });
}
