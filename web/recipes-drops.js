function ruleIds(i) {
  return materialSets[i] ?? [slots[i]];
}
function pickFusionSlot(index) {
  const material = index < 2;
  const draft = new Set(material ? ruleIds(index) : [slots[index]]);
  const dialog = $("#picker"),
    pendingArt = new Set();
  let filtered = [],
    matches = [],
    observer;
  $("#pickTitle").textContent = material
    ? `Choose Material ${index === 0 ? "A" : "B"}`
    : "Choose fusion result";
  dialog.classList.add("fusion-picker");
  $("#pickContent").innerHTML =
    `<label class="picker-view"><input type="checkbox" id="selectedOnly"> Show selected only</label><div id="fusionLibrary"></div><footer class="fusion-footer">${material ? '<button id="selectMatches">Select all matches</button><button id="deselectMatches">Deselect all matches</button>' : ""}<span id="chosenCount" role="status"></span>${material ? '<button id="useChosen" class="primary">Use selected cards</button>' : ""}</footer>`;
  function update() {
    const selectedOnly = $("#selectedOnly").checked;
    matches = selectedOnly ? filtered.filter((id) => draft.has(id)) : filtered;
    for (const card of dialog.querySelectorAll(".fusion-tile")) {
      const selected = draft.has(+card.dataset.id);
      card.setAttribute("aria-pressed", String(selected));
      card.hidden = selectedOnly && !selected;
    }
    const empty = dialog.querySelector(".fusion-grid .empty");
    if (empty) {
      empty.hidden = matches.length > 0;
      empty.textContent = selectedOnly
        ? "No selected cards match this view."
        : "No matching cards.";
    }
    $("#chosenCount").textContent = material
      ? `${draft.size} selected · ${matches.length} matching`
      : `${matches.length} matching`;
    if (material) {
      $("#useChosen").disabled = !draft.size;
      $("#selectMatches").disabled = !matches.some((id) => !draft.has(id));
      $("#deselectMatches").disabled = !matches.some((id) => draft.has(id));
    }
  }
  function tile(id) {
    const c = game.cards[id - 1],
      pos = id - 1;
    const color =
      ["#449e79", "#bc5d87", "#6e8db4", "#449e79"][c.type_id - 20] || "#bf9b62";
    return `<button data-id="${id}" class="fusion-tile" aria-pressed="${draft.has(id)}" style="--frame:${color}"><strong>${esc(c.name)}</strong><span class="face-art" style="background-position:${((pos % 16) * 100) / 15}% ${(Math.floor(pos / 16) * 100) / 45}%"></span><span class="face-info">★ ${c.level} · ${esc(meta.types[c.type_id])}<br>${esc(meta.attributes[c.attribute])} · ${esc(meta.stars[c.gs1])} / ${esc(meta.stars[c.gs2])}<br>ATK ${c.atk} · DEF ${c.def_}</span></button>`;
  }
  const cache = artCache;
  function paint(button) {
    const src = cache[button.dataset.id];
    if (src)
      button.querySelector(".face-art").style.background =
        `center / cover url("${src}")`;
  }
  function observeArtwork(grid) {
    observer?.disconnect();
    observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter(
            (entry) => entry.isIntersecting && grid.contains(entry.target),
          )
          .map((entry) => entry.target);
        const ids = visible
          .map((button) => +button.dataset.id)
          .filter((id) => !cache[id] && !pendingArt.has(id));
        visible.forEach(paint);
        if (!ids.length) return;
        ids.forEach((id) => pendingArt.add(id));
        rpc("pickerArt", { ids })
          .then((images) => {
            Object.assign(cache, images);
            if (dialog.open)
              for (const id of ids) {
                const button = dialog.querySelector(
                  `.fusion-tile[data-id="${id}"]`,
                );
                if (button) paint(button);
              }
          })
          .catch(fail)
          .finally(() => ids.forEach((id) => pendingArt.delete(id)));
      },
      { root: grid, rootMargin: "120px" },
    );
    grid
      .querySelectorAll(".fusion-tile")
      .forEach((button) => observer.observe(button));
  }
  $("#selectedOnly").onchange = () => {
    update();
    dialog.querySelector(".fusion-grid").scrollTop = 0;
  };
  delete browsers.fusionPicker;
  library(
    $("#fusionLibrary"),
    "fusionPicker",
    (id) => {
      if (!material) {
        slots[index] = id;
        dialog.close();
        return;
      }
      if (draft.has(id)) draft.delete(id);
      else draft.add(id);
      update();
    },
    {
      tile,
      onMatches(all, results) {
        filtered = all;
        const grid = results.querySelector(".fusion-grid");
        if (!grid.querySelector(".empty"))
          grid.insertAdjacentHTML(
            "beforeend",
            '<div class="empty" hidden></div>',
          );
        update();
        observeArtwork(grid);
      },
    },
  );
  if (material) {
    $("#selectMatches").onclick = () => {
      matches.forEach((id) => draft.add(id));
      update();
    };
    $("#deselectMatches").onclick = () => {
      matches.forEach((id) => draft.delete(id));
      update();
    };
    $("#useChosen").onclick = () => {
      materialSets[index] = [...draft];
      slots[index] = materialSets[index][0];
      dialog.close();
    };
  }
  dialog.addEventListener(
    "close",
    () => {
      observer?.disconnect();
      dialog.classList.remove("fusion-picker");
      if (page === "fusion") render();
    },
    { once: true },
  );
  dialog.showModal();
  $("#fusionLibrary input[type=search]").focus();
}
function pairCount() {
  const a = ruleIds(0),
    b = new Set(ruleIds(1));
  const shared = a.filter((id) => b.has(id)).length;
  return a.length * b.size - (shared * (shared - 1)) / 2;
}
function fusionTab() {
  $("#view").innerHTML =
    title("fusion", btn("Reset all recipes", "resetRecipes")) +
    `<div class="stack"><section class="panel"><div class="columns">${slots
      .map((id, i) => {
        const ids = i < 2 ? ruleIds(i) : [id];
        const label =
          cidName(id) + (ids.length > 1 ? ` + ${ids.length - 1} more` : "");
        return `<div><h3>${["Material A", "Material B", "Result"][i]}</h3><button data-slot="${i}" class="slot">${thumb(id)}<span>${esc(label)}</span></button></div>`;
      })
      .join(
        "",
      )}</div><div class="actions">${btn("Add / update recipe", "applyRecipe", "primary")}${btn("Delete recipe", "deleteRecipe")}<small>${pairCount().toLocaleString()} unique material pairs</small></div></section><section class="panel"><h2>Recipe library</h2><div class="bar"><input type="search" id="fusionQuery" placeholder="Search recipes" aria-label="Search recipes" value="${esc(fusionQuery)}"><select id="scope" aria-label="Search scope">${["everywhere", "result", "material"].map((v) => `<option ${v === fusionScope ? "selected" : ""}>${v}</option>`).join("")}</select></div><div id="recipes"></div></section></div>`;
  for (const button of document.querySelectorAll("[data-slot]"))
    button.onclick = () => pickFusionSlot(+button.dataset.slot);
  async function changeRecipe(remove) {
    const a = ruleIds(0),
      b = ruleIds(1);
    if (
      remove &&
      a.length * b.length > 1 &&
      !confirm(
        `Delete existing recipes for up to ${a.length * b.length} pairs?`,
      )
    )
      return;
    game.recipes = await work("Updating fusion table…", () =>
      rpc("recipe", { a, b, result: remove ? null : slots[2] }),
    );
    changed();
    render();
    notice("Fusion table updated.");
  }
  on("applyRecipe", () => changeRecipe(false));
  on("deleteRecipe", () => changeRecipe(true));
  on("resetRecipes", async () => {
    if (confirm("Restore every recipe from the disc?")) {
      game.recipes = await rpc("resetRecipes");
      changed();
      render();
    }
  });
  function list() {
    const q = fusionQuery.toLowerCase().trim();
    const matches = game.recipes.filter(
      (v) =>
        !q ||
        (fusionScope === "result"
          ? [v[2]]
          : fusionScope === "material"
            ? v.slice(0, 2)
            : v
        ).some(
          (id) => cidName(id).toLowerCase().includes(q) || String(id) === q,
        ),
    );
    const n = 40;
    fusionPage = Math.max(
      0,
      Math.min(fusionPage, Math.ceil(matches.length / n) - 1),
    );
    $("#recipes").innerHTML = `<div class="list">${
      matches
        .slice(n * fusionPage, n * (fusionPage + 1))
        .map(
          (v) =>
            `<button data-recipe="${v}" class="row recipe">${v.map((id) => `<span>${thumb(id)}${esc(cidName(id))}</span>`).join("")}</button>`,
        )
        .join("") || '<p class="empty">No matching recipes.</p>'
    }</div>${paginate(matches.length, fusionPage, n)}`;
    $("#recipes [data-prev]").onclick = () => {
      fusionPage--;
      list();
    };
    $("#recipes [data-next]").onclick = () => {
      fusionPage++;
      list();
    };
    $("#recipes .list").onclick = (e) => {
      const b = e.target.closest("[data-recipe]");
      if (b) {
        slots = b.dataset.recipe.split(",").map(Number);
        materialSets = [null, null];
        render();
      }
    };
  }
  $("#fusionQuery").oninput = (e) => {
    fusionQuery = e.target.value;
    fusionPage = 0;
    list();
  };
  $("#scope").onchange = (e) => {
    fusionScope = e.target.value;
    fusionPage = 0;
    list();
  };
  list();
}
function dropsTab() {
  const token = revision,
    op = opponent,
    r = rank;
  $("#view").innerHTML =
    title("drops", btn("Reset all drop edits", "resetDrops")) +
    `<div class="split duels"><section class="panel"><h2>Opponents</h2><div id="opps" class="list">${meta.opponents.map((name, i) => `<button class="row ${op === i ? "selected" : ""}" data-op="${i}"><img class="duelist" alt="" src="${game.portraits[i]}">${esc(name)}</button>`).join("")}</div></section><section class="panel"><div class="previewwrap"><img class="portrait" alt="" src="${game.portraits[op]}"><div><h2>${esc(meta.opponents[op])}</h2>${btn("Change portrait", "portrait")}</div></div><div class="bar"><select id="rank" aria-label="Reward rank">${["S/A POW", "B/C/D", "S/A TEC"].map((v, i) => `<option value="${i}" ${r === i ? "selected" : ""}>${v}</option>`).join("")}</select>${btn("Add card", "addDrop")}${btn("Balance to 2048", "balance")}</div><small id="total"></small><div id="dropRows"></div></section></div>`;
  $("#opps").onclick = (e) => {
    const b = e.target.closest("[data-op]");
    if (b) {
      opponent = +b.dataset.op;
      render();
      $("#opps .selected")?.scrollIntoView({ block: "nearest" });
    }
  };
  $("#rank").onchange = (e) => {
    rank = +e.target.value;
    render();
  };
  on("portrait", () =>
    chooseImage(async (f) => {
      game.portraits[op] = await rpc("portraitEdit", { id: op }, [f]);
      changed();
      render();
    }),
  );
  on("resetDrops", async () => {
    if (confirm("Restore every drop pool and portrait from the disc?")) {
      game.portraits = await rpc("resetDrops");
      changed();
      render();
    }
  });
  async function persist(next) {
    const updated = await rpc("setDrops", {
      opponent: op,
      rank: r,
      weights: next,
    });
    changed();
    if (token === revision) {
      weights = updated;
      draw();
    }
  }
  async function edit(id) {
    const answer = prompt(
      `Drop weight for ${cidName(id)} (0–2048). Zero removes the card.`,
      weights[id - 1],
    );
    if (answer === null) return;
    const v = Number(answer);
    if (!Number.isInteger(v) || v < 0 || v > 2048 || !answer.trim())
      throw Error("Enter a whole number from 0 to 2048.");
    const next = weights.slice();
    next[id - 1] = v;
    await persist(next);
  }
  function draw() {
    const ids = weights.flatMap((v, i) => (v ? [i + 1] : []));
    $("#total").textContent =
      `Pool weight ${weights.reduce((a, b) => a + b, 0)} / 2048 · Click a card to edit its weight`;
    library($("#dropRows"), "drops", edit, {
      ids,
      summary: (id) =>
        `Weight ${weights[id - 1]} · ${((weights[id - 1] * 100) / 2048).toFixed(2)}%`,
    });
  }
  $("#addDrop").disabled = $("#balance").disabled = true;
  rpc("drops", { opponent: op, rank: r })
    .then((data) => {
      if (token !== revision) return;
      weights = data;
      draw();
      $("#addDrop").disabled = $("#balance").disabled = false;
    })
    .catch(fail);
  on("addDrop", () => pick("Add a drop card", edit));
  on("balance", async () => {
    const total = weights.reduce((a, b) => a + b, 0);
    if (!total) throw Error("Add a card before balancing.");
    const active = weights.filter(Boolean).length;
    const exact = weights.map((w) => (w ? (w / total) * (2048 - active) : 0));
    const next = exact.map((v, i) => (weights[i] ? 1 + Math.floor(v) : 0));
    const spare = 2048 - next.reduce((a, b) => a + b, 0);
    weights
      .map((w, i) => ({ w, i, frac: exact[i] % 1 }))
      .filter((x) => x.w)
      .sort((a, b) => b.frac - a.frac)
      .slice(0, spare)
      .forEach((x) => next[x.i]++);
    await persist(next);
  });
}
