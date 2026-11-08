// Rounds: a diagnostic grouping game. Puzzles are read from puzzles.json (see README).
(() => {
  const MAX_MISTAKES = 4;
  const $ = (id) => document.getElementById(id);
  const els = {
    select: $("puzzle-select"), topic: $("topic"), grid: $("grid"), solved: $("solved"),
    message: $("message"), dots: $("mistake-dots"), shuffle: $("shuffle"), deselect: $("deselect"),
    submit: $("submit"), end: $("end-controls"), restart: $("restart"), next: $("next"),
    loadError: $("load-error"), fileInput: $("file-input"), errorDetail: $("error-detail"),
  };
  const mainControls = els.submit.parentElement;

  let puzzles = [];
  let state = null;

  // ---------- loading & validation ----------
  function validate(data) {
    const errors = [];
    if (!data || !Array.isArray(data.puzzles) || data.puzzles.length === 0) {
      return ['Top level must be { "puzzles": [ ... ] } with at least one puzzle.'];
    }
    const ids = new Set();
    data.puzzles.forEach((p, i) => {
      const where = `Puzzle ${i + 1}${p && p.title ? ` ("${p.title}")` : ""}`;
      if (!p.id) errors.push(`${where}: missing "id".`);
      else if (ids.has(p.id)) errors.push(`${where}: duplicate id "${p.id}".`);
      ids.add(p.id);
      if (!p.title) errors.push(`${where}: missing "title".`);
      if (!Array.isArray(p.groups) || p.groups.length !== 4) {
        errors.push(`${where}: needs exactly 4 groups.`);
        return;
      }
      const seen = new Set();
      p.groups.forEach((g, j) => {
        const gw = `${where}, group ${j + 1}`;
        if (!g.name) errors.push(`${gw}: missing "name".`);
        if (![1, 2, 3, 4].includes(g.difficulty)) errors.push(`${gw}: "difficulty" must be 1, 2, 3, or 4.`);
        if (!Array.isArray(g.items) || g.items.length !== 4) errors.push(`${gw}: needs exactly 4 items.`);
        else g.items.forEach((it) => {
          const key = String(it).trim().toLowerCase();
          if (seen.has(key)) errors.push(`${where}: "${it}" appears more than once.`);
          seen.add(key);
        });
      });
    });
    return errors;
  }

  function useData(data) {
    const errors = validate(data);
    if (errors.length) {
      showLoadError("puzzles.json has problems:\n• " + errors.join("\n• "));
      return;
    }
    els.loadError.hidden = true;
    puzzles = data.puzzles;
    els.select.innerHTML = "";
    puzzles.forEach((p) => els.select.add(new Option(p.title, p.id)));
    const fromHash = decodeURIComponent(location.hash.replace(/^#/, ""));
    start(puzzles.some((p) => p.id === fromHash) ? fromHash : puzzles[0].id);
  }

  function showLoadError(detail) {
    els.loadError.hidden = false;
    els.errorDetail.textContent = detail || "";
  }

  async function load() {
    try {
      const res = await fetch("puzzles.json", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      useData(await res.json());
    } catch (err) {
      showLoadError(err instanceof SyntaxError ? `JSON syntax error: ${err.message}` : "");
    }
  }

  els.fileInput.addEventListener("change", async () => {
    const file = els.fileInput.files[0];
    if (!file) return;
    try { useData(JSON.parse(await file.text())); }
    catch (err) { showLoadError(`JSON syntax error: ${err.message}`); }
  });

  // ---------- game ----------
  const shuffle = (arr) => {
    const a = arr.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  };

  function start(id) {
    const puzzle = puzzles.find((p) => p.id === id);
    els.select.value = id;
    history.replaceState(null, "", "#" + encodeURIComponent(id));
    state = {
      puzzle,
      remaining: shuffle(puzzle.groups.flatMap((g) => g.items)),
      selected: new Set(),
      solved: [],
      mistakes: 0,
      guesses: new Set(),
      over: false,
    };
    els.topic.textContent = puzzle.topic || "";
    els.solved.innerHTML = "";
    setMessage("");
    render();
  }

  function render() {
    els.grid.innerHTML = "";
    state.remaining.forEach((item) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "tile";
      b.textContent = item;
      b.setAttribute("aria-pressed", state.selected.has(item));
      b.disabled = state.over;
      b.addEventListener("click", () => toggle(item));
      els.grid.appendChild(b);
    });
    els.dots.innerHTML = "";
    for (let i = 0; i < MAX_MISTAKES; i++) {
      const d = document.createElement("span");
      if (i < state.mistakes) d.className = "used";
      els.dots.appendChild(d);
    }
    els.dots.setAttribute("aria-label", `${MAX_MISTAKES - state.mistakes} of ${MAX_MISTAKES}`);
    els.submit.disabled = state.selected.size !== 4 || state.over;
    els.deselect.disabled = state.selected.size === 0 || state.over;
    els.shuffle.disabled = state.over;
    mainControls.hidden = state.over;
    els.end.hidden = !state.over;
  }

  function toggle(item) {
    if (state.over) return;
    if (state.selected.has(item)) state.selected.delete(item);
    else if (state.selected.size < 4) state.selected.add(item);
    setMessage("");
    render();
  }

  function setMessage(text) { els.message.textContent = text; }

  function revealGroup(group, missed = false) {
    const div = document.createElement("div");
    div.className = `group d${group.difficulty}${missed ? " missed" : ""}`;
    const h = document.createElement("h3");
    h.textContent = group.name;
    const items = document.createElement("p");
    items.className = "items";
    items.textContent = group.items.join(" · ");
    div.append(h, items);
    if (group.explanation) {
      const det = document.createElement("details");
      det.open = true;
      const sum = document.createElement("summary");
      sum.textContent = "Teaching point";
      const p = document.createElement("p");
      p.textContent = group.explanation;
      det.append(sum, p);
      div.appendChild(det);
    }
    els.solved.appendChild(div);
  }

  function submit() {
    if (state.selected.size !== 4 || state.over) return;
    const guess = [...state.selected];
    const key = guess.slice().sort().join("|");
    if (state.guesses.has(key)) { setMessage("Already guessed!"); return; }
    state.guesses.add(key);

    const match = state.puzzle.groups.find(
      (g) => !state.solved.includes(g) && g.items.every((it) => state.selected.has(it))
    );
    if (match) {
      state.solved.push(match);
      state.remaining = state.remaining.filter((it) => !state.selected.has(it));
      state.selected.clear();
      revealGroup(match);
      if (state.solved.length === 4) {
        state.over = true;
        setMessage(state.mistakes === 0 ? "Perfect diagnosis! 🎉" : `Solved with ${state.mistakes} mistake${state.mistakes > 1 ? "s" : ""}.`);
      } else setMessage("");
      render();
      return;
    }

    state.mistakes++;
    const best = Math.max(...state.puzzle.groups
      .filter((g) => !state.solved.includes(g))
      .map((g) => g.items.filter((it) => state.selected.has(it)).length));
    els.grid.querySelectorAll('.tile[aria-pressed="true"]').forEach((t) => {
      t.classList.remove("shake"); void t.offsetWidth; t.classList.add("shake");
    });
    if (state.mistakes >= MAX_MISTAKES) {
      state.over = true;
      state.selected.clear();
      state.puzzle.groups
        .filter((g) => !state.solved.includes(g))
        .sort((a, b) => a.difficulty - b.difficulty)
        .forEach((g) => revealGroup(g, true));
      state.remaining = [];
      setMessage("Out of mistakes. Review the answers below.");
    } else {
      setMessage(best === 3 ? "One away…" : "Not quite.");
    }
    render();
  }

  // ---------- wiring ----------
  els.submit.addEventListener("click", submit);
  els.shuffle.addEventListener("click", () => { state.remaining = shuffle(state.remaining); render(); });
  els.deselect.addEventListener("click", () => { state.selected.clear(); render(); });
  els.restart.addEventListener("click", () => start(state.puzzle.id));
  els.next.addEventListener("click", () => {
    const i = puzzles.indexOf(state.puzzle);
    start(puzzles[(i + 1) % puzzles.length].id);
  });
  els.select.addEventListener("change", () => start(els.select.value));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !els.submit.disabled && !["SELECT", "BUTTON", "INPUT"].includes(e.target.tagName)) {
      e.preventDefault();
      submit();
    }
  });

  load();
})();
