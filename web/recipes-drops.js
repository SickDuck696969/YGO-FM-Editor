function ruleIds(i) {
  const r = rules[i];
  return r
    ? game.cards
        .filter((c) => c[r.key] === r.value && !r.except.includes(c.id))
        .map((c) => c.id)
    : [slots[i]];
}
function fusionTab() {
  const keys = {
    type_id: meta.types,
    attribute: meta.attributes,
    level: Array.from({ length: 13 }, (_, i) => String(i)),
  };
  const modes = [
    ["", "Specific card"],
    ["type_id", "By type"],
    ["attribute", "By attribute"],
    ["level", "By level"],
  ];
  $("#view").innerHTML =
    title("fusion", btn("Reset all recipes", "resetRecipes")) +
    `<div class="stack"><section class="panel"><div class="columns">${slots
      .map((id, i) => {
        const r = rules[i];
        return `<div><h3>${["Material A", "Material B", "Result"][i]}</h3><button data-slot="${i}" class="slot">${thumb(r ? ruleIds(i)[0] || id : id)}<span>${esc(r ? `${keys[r.key][r.value]} · ${ruleIds(i).length} cards` : cidName(id))}</span></button>${i < 2 ? `<div class="bar"><select data-mode="${i}" aria-label="Material rule">${modes.map(([k, v]) => `<option value="${k}" ${k === (r?.key || "") ? "selected" : ""}>${v}</option>`).join("")}</select>${r ? `<select data-val="${i}" aria-label="Material value">${keys[r.key].map((v, j) => `<option value="${j}" ${r.value === j ? "selected" : ""}>${esc(v)}</option>`).join("")}</select><button data-ex="${i}">Exceptions (${r.except.length})</button>` : ""}</div>` : ""}</div>`;
      })
      .join(
        "",
      )}</div><div class="actions">${btn("Add / update recipe", "applyRecipe", "primary")}${btn("Delete recipe", "deleteRecipe")}</div></section><section class="panel"><h2>Recipe library</h2><div class="bar"><input type="search" id="fusionQuery" placeholder="Search recipes" aria-label="Search recipes" value="${esc(fusionQuery)}"><select id="scope" aria-label="Search scope">${["everywhere", "result", "material"].map((v) => `<option ${v === fusionScope ? "selected" : ""}>${v}</option>`).join("")}</select></div><div id="recipes"></div></section></div>`;
  document.querySelectorAll("[data-slot]").forEach(
    (b) =>
      (b.onclick = () => {
        const i = +b.dataset.slot;
        pick(`Choose ${i === 2 ? "result" : "material"}`, (id) => {
          slots[i] = id;
          if (i < 2) rules[i] = null;
          render();
        });
      }),
  );
  document.querySelectorAll("[data-mode]").forEach(
    (s) =>
      (s.onchange = () => {
        rules[+s.dataset.mode] = s.value
          ? { key: s.value, value: 0, except: [] }
          : null;
        render();
      }),
  );
  document.querySelectorAll("[data-val]").forEach(
    (s) =>
      (s.onchange = () => {
        const r = rules[+s.dataset.val];
        r.value = +s.value;
        r.except = [];
        render();
      }),
  );
  document.querySelectorAll("[data-ex]").forEach(
    (b) =>
      (b.onclick = () => {
        const r = rules[+b.dataset.ex];
        $("#pickTitle").textContent = "Material exceptions";
        delete browsers.exceptions;
        const ids = game.cards
          .filter((c) => c[r.key] === r.value)
          .map((c) => c.id);
        function draw() {
          library(
            $("#pickContent"),
            "exceptions",
            (id) => {
              r.except = r.except.includes(id)
                ? r.except.filter((k) => k !== id)
                : [...r.except, id];
              draw();
            },
            {
              ids,
              summary: (id) =>
                r.except.includes(id)
                  ? "Excluded · click to include"
                  : "Included · click to exclude",
            },
          );
        }
        draw();
        $("#picker").showModal();
        $("#picker").addEventListener(
          "close",
          () => {
            if (page === "fusion") render();
          },
          { once: true },
        );
      }),
  );
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
        rules = [null, null];
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
