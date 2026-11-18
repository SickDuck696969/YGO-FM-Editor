function deckList(root, ids, remove) {
  const counts = new Map();
  ids.forEach((id) => counts.set(id, (counts.get(id) || 0) + 1));
  root.innerHTML = `<div class="list">${[...counts].map(([id, n]) => row(id, `${n} ${n === 1 ? "copy" : "copies"} · remove one`)).join("") || '<p class="empty">Choose cards from the library to fill this deck.</p>'}</div>`;
  function handle(e) {
    const b = e.target.closest("[data-id]");
    if (b) {
      e.preventDefault();
      remove(+b.dataset.id);
    }
  }
  root.onclick = root.oncontextmenu = handle;
}
function addCopy(ids, id) {
  if (ids.length >= 40) throw Error("The deck already has 40 cards.");
  if (ids.filter((v) => v === id).length >= 3)
    throw Error("The deck already has three copies.");
  ids.push(id);
}
function removeCopy(ids, id) {
  const i = ids.indexOf(id);
  if (i >= 0) ids.splice(i, 1);
}
function deckTab() {
  $("#view").innerHTML =
    title("deck", btn("Reset starter deck", "resetDeck")) +
    `<div class="split"><section class="panel"><h2>Card library</h2><small>Click to add. Right-click to remove one copy.</small><div id="deckLibrary"></div></section><section class="panel"><div class="dialoghead"><h2>Starter deck</h2><strong id="deckCount"></strong></div><div id="deckList"></div><div class="actions">${btn("Fill empty slots", "fillDeck")}${btn("Random deck", "randomDeck")}</div><div class="cardform sectionhead">${field("Player name", "player", player, 'maxlength="6"')}${field("Starting starchips", "chips", chips, 'min="0" max="999999"', "number")}</div>${btn("Download new .mcd", "createSave", "primary")}</section></div>`;
  const refresh = () => {
    $("#deckCount").textContent = `${deck.length} / 40`;
    deckList($("#deckList"), deck, (id) => {
      removeCopy(deck, id);
      refresh();
    });
  };
  library(
    $("#deckLibrary"),
    "deck",
    (id) => {
      addCopy(deck, id);
      refresh();
    },
    {
      context: (id) => {
        removeCopy(deck, id);
        refresh();
      },
    },
  );
  refresh();
  function fill() {
    while (deck.length < 40) {
      const id = 1 + Math.floor(Math.random() * 722);
      if (deck.filter((v) => v === id).length < 3) deck.push(id);
    }
    refresh();
  }
  on("fillDeck", fill);
  on("randomDeck", () => {
    deck = [];
    fill();
  });
  on("resetDeck", () => {
    if (confirm("Clear the starter deck and reset the player fields?")) {
      deck = [];
      player = "PLAYER";
      chips = 0;
      render();
    }
  });
  $('[name="player"]').oninput = (e) => {
    player = e.target.value;
  };
  $('[name="chips"]').oninput = (e) => {
    chips = e.target.valueAsNumber;
  };
  on("createSave", async () => {
    const blob = await rpc("newSave", { deck, player, chips });
    downloadNow(blob, baseName + ".mcd");
    notice("New memory card created.");
  });
}
async function openSave(file) {
  if (!file || !clearDraft()) return;
  if (
    save &&
    JSON.stringify(save) !== JSON.stringify(originalSave) &&
    !confirm("Replace the save and discard its pending edits?")
  )
    return;
  await work("Reading memory card…", async () => {
    await ready();
    const data = await rpc("save", {}, [file]);
    data.deck = data.deck.filter(Boolean);
    save = data;
    originalSave = copy(data);
    saveName = file.name;
    go("save");
  });
}
function saveTab() {
  $("#view").innerHTML = title(
    "save",
    btn("Open save file", "openSave", save ? "" : "primary"),
  );
  on("openSave", () => $("#saveFile").click());
  if (!save) {
    $("#view").insertAdjacentHTML(
      "beforeend",
      `<div class="panel stack"><h2>Open a memory card</h2><p>Choose a DuckStation .mcd or a single .mcs save. You can edit a save without opening a disc.</p></div>`,
    );
    return;
  }
  $("#view").insertAdjacentHTML(
    "beforeend",
    `<div class="stack"><section class="panel"><div class="dialoghead"><h2>${esc(saveName)}</h2>${btn("Reset save edits", "resetSave")}</div><div class="cardform sectionhead">${field("Player name", "player", save.player, 'maxlength="6"')}${field("Starchips", "chips", save.chips, 'min="0" max="999999"', "number")}${field("Wins", "wins", save.record[0], 'min="0" max="65535"', "number")}${field("Losses", "losses", save.record[1], 'min="0" max="65535"', "number")}</div>${btn("Download edited save", "saveDownload", "primary")}</section><section class="panel"><h2>Deck and trunk</h2><div class="actions">${btn(`Add to deck (${save.deck.length} / 40)`, "saveDeckAdd")}${btn("Edit trunk copies", "saveTrunk")}</div><details><summary>View deck</summary><div id="saveDeck"></div></details></section><section class="panel"><h2>Campaign milestones</h2><div class="checkgrid checks">${Object.entries(
      meta.milestones,
    )
      .map(
        ([k, v]) =>
          `<label><input type="checkbox" data-m="${k}" ${save.milestones[k] ? "checked" : ""}>${esc(v)}</label>`,
      )
      .join(
        "",
      )}</div></section><section class="panel"><h2>Free Duel opponents</h2><div class="bar">${btn("Unlock all", "unlockAll")}${btn("Lock all", "lockAll")}</div><div class="checkgrid checks">${meta.opponents.map((name, i) => `<label><input type="checkbox" data-op="${i}" ${i === 38 ? "checked disabled" : save.unlocked[i] ? "checked" : ""}>${game ? `<img class="duelist" alt="" src="${game.portraits[i]}">` : ""}${esc(name)}</label>`).join("")}</div></section></div>`,
  );
  for (const el of document.querySelectorAll("#view input[name]"))
    el.oninput = () => {
      if (el.name === "wins" || el.name === "losses")
        save.record[el.name === "wins" ? 0 : 1] = el.valueAsNumber;
      else save[el.name] = el.type === "number" ? el.valueAsNumber : el.value;
    };
  document
    .querySelectorAll("[data-m]")
    .forEach(
      (el) =>
        (el.onchange = () => (save.milestones[el.dataset.m] = el.checked)),
    );
  document
    .querySelectorAll("input[data-op]")
    .forEach(
      (el) =>
        (el.onchange = () => (save.unlocked[+el.dataset.op] = el.checked)),
    );
  on("unlockAll", () => {
    save.unlocked.fill(true);
    render();
  });
  on("lockAll", () => {
    save.unlocked.fill(false);
    render();
  });
  on("resetSave", () => {
    if (confirm("Restore all data from the opened save?")) {
      save = copy(originalSave);
      render();
    }
  });
  deckList($("#saveDeck"), save.deck, (id) => {
    removeCopy(save.deck, id);
    render();
    $("#saveDeck").parentElement.open = true;
  });
  on("saveDeckAdd", () =>
    pick("Add a deck card", (id) => {
      addCopy(save.deck, id);
      render();
    }),
  );
  on("saveTrunk", () =>
    pick("Choose a trunk card", (id) => {
      const value = prompt(
        `Trunk copies of ${cidName(id)} (0–250)`,
        save.trunk[id - 1],
      );
      if (value === null) return;
      const n = Number(value);
      if (!value.trim() || !Number.isInteger(n) || n < 0 || n > 250)
        throw Error("Enter 0–250 copies.");
      save.trunk[id - 1] = n;
      notice("Trunk quantity updated.");
    }),
  );
  on("saveDownload", async () => {
    const blob = await rpc("saveExport", save);
    downloadNow(blob, "Edited - " + saveName);
    notice("Edited save downloaded.");
  });
}
function exportTab() {
  const [kind, count] = game.reward,
    supported = !["occupied", "unsupported"].includes(kind);
  const [sector, offset] = game.layout,
    raw = sector !== 2048;
  $("#view").innerHTML =
    title("export") +
    `<div class="stack"><section class="panel"><h2>Cards per victory</h2><p>${supported ? `Reward override available · ${esc(kind)} routine${count ? ` · ${count} card(s) per win` : ""}.` : "This disc layout can preserve its existing reward routine."}</p><div class="bar"><label><input type="checkbox" id="override" ${reward !== null ? "checked" : ""} ${supported ? "" : "disabled"}> Override drop count</label><input id="count" aria-label="Cards per victory" type="number" min="1" max="100" value="${reward ?? count ?? 1}" ${reward === null ? "disabled" : ""}>${btn("Reset reward", "resetReward")}</div><small>The results screen shows the first reward. Additional cards go to the trunk.</small></section><section class="panel"><h2>Build output</h2><p>${esc(discName)} · ${sector}-byte sectors</p><div class="actions">${btn("Build BPS patch", "buildPatch", "primary")}${btn(raw ? "Build BIN + CUE" : "Build ISO", "buildDisc")}</div><p class="info sectionhead">Apply a BPS patch to the same source image. ${raw ? "For DuckStation, download both disc files into one folder and open the CUE." : "Open the exported ISO in DuckStation."}</p><div class="downloads actions">${downloads.map((d) => `<a class="btn primary" href="${d.url}" download="${esc(d.name)}">Download ${esc(d.name.split(".").at(-1).toUpperCase())}</a>`).join("")}</div></section></div>`;
  $("#override").onchange = (e) => {
    reward = e.target.checked ? count || 1 : null;
    changed();
    render();
  };
  $("#count").oninput = (e) => {
    reward = e.target.valueAsNumber;
    changed();
    $(".downloads").replaceChildren();
  };
  on("resetReward", () => {
    reward = null;
    changed();
    render();
  });
  async function build(format) {
    if (
      reward !== null &&
      (!Number.isInteger(reward) || reward < 1 || reward > 100)
    )
      throw Error("Choose 1–100 cards per victory.");
    const { blob, changed: sectors } = await work("Building output…", () =>
      rpc("export", { count: reward, format }),
    );
    revoke();
    const ext = format === "bps" ? ".bps" : raw ? ".bin" : ".iso";
    downloads = [downloadLink(blob, baseName + ext)];
    if (format === "disc" && raw) {
      const mode =
        sector === 2336
          ? "MODE2/2336"
          : offset === 24
            ? "MODE2/2352"
            : "MODE1/2352";
      downloads.push(
        downloadLink(
          new Blob([
            `FILE "${baseName}.bin" BINARY\n  TRACK 01 ${mode}\n    INDEX 01 00:00:00\n`,
          ]),
          baseName + ".cue",
        ),
      );
    }
    render();
    notice(`Output ready to download · ${sectors} modified sectors.`);
  }
  on("buildPatch", () => build("bps"));
  on("buildDisc", () => build("disc"));
}
$("nav").innerHTML = Object.entries(tabs)
  .map(([k, [name]]) => `<button data-page="${k}">${icon(k)}${name}</button>`)
  .join("");
document.addEventListener("click", (e) => {
  const b = e.target.closest("[data-page]");
  if (b) go(b.dataset.page);
});
$(".brand").onclick = (e) => {
  e.preventDefault();
  go("home");
};
$("#openTop").onclick = () => $("#discFile").click();
on("closePick", () => $("#picker").close());
on(
  "discFile",
  async (e) => {
    const files = [...e.target.files];
    e.target.value = "";
    await openDisc(files);
  },
  "change",
);
on(
  "saveFile",
  async (e) => {
    const f = e.target.files[0];
    e.target.value = "";
    await openSave(f);
  },
  "change",
);
on(
  "imageFile",
  async (e) => {
    const f = e.target.files[0];
    e.target.value = "";
    if (f && onImage) await work("Reading artwork…", () => onImage(f));
  },
  "change",
);
window.addEventListener("beforeunload", (e) => {
  if (
    dirty ||
    formDirty ||
    deck.length ||
    (save && JSON.stringify(save) !== JSON.stringify(originalSave))
  ) {
    e.preventDefault();
    e.returnValue = "";
  }
});
fetch("./themes.json")
  .then((r) => r.json())
  .then((themes) => {
    const keys = ["base", "panel", "surface", "field", "text", "accent", "ink"],
      s = $("#theme");
    for (const name of Object.keys(themes)) s.add(new Option(name, name));
    function apply() {
      keys.forEach((k, i) =>
        themes[s.value]
          ? document.documentElement.style.setProperty(
              "--" + k,
              themes[s.value][i],
            )
          : document.documentElement.style.removeProperty("--" + k),
      );
      document.documentElement.style.colorScheme =
        themes[s.value] && parseInt(themes[s.value][0].slice(1, 3), 16) > 155
          ? "light"
          : "dark";
    }
    try {
      const saved = localStorage.getItem("fm-theme");
      if (themes[saved]) s.value = saved;
    } catch {}
    apply();
    s.onchange = () => {
      apply();
      try {
        localStorage.setItem("fm-theme", s.value);
      } catch {}
    };
  })
  .catch(fail);
render();
