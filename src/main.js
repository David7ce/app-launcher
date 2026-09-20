const CATEGORY_ORDER = [
  "Development",
  "Education",
  "Graphics",
  "Internet",
  "Games",
  "Multimedia",
  "Office",
  "Science",
  "System",
  "Utilities",
];

const CATEGORY_ICONS = {
  Development: "\u{1F4BB}", // 💻
  Education: "\u{1F393}", // 🎓
  Graphics: "\u{1F3A8}", // 🎨
  Internet: "\u{1F310}", // 🌐
  Games: "\u{1F3AE}", // 🎮
  Multimedia: "\u{1F3AC}", // 🎬
  Office: "\u{1F4C4}", // 📄
  Science: "\u{1F52C}", // 🔬
  System: "\u{2699}\u{FE0F}", // ⚙️
  Utilities: "\u{1F9F0}", // 🧰
};

const { invoke } = window.__TAURI__.core;

const categoriesEl = document.getElementById("categories");
const errorBannerEl = document.getElementById("error-banner");
const searchEl = document.getElementById("search");
const editToggleEl = document.getElementById("edit-toggle");
const pillEls = [...document.querySelectorAll(".pill")];
const messagesEl = document.getElementById("messages");

// installedApps: the fixed result of the catalog + is_installed check,
// computed once at startup. overrides: user hide/rename/recategorize edits,
// persisted via save_overrides and re-applied on top of installedApps
// every render — catalog.json itself is never touched at runtime.
let installedApps = [];
let overrides = {};
let editMode = false;

// Which kinds of tile to show: everything, only GUI apps, or only CLI tools.
// A display preference like the search box, so it lives in localStorage and not
// in overrides.json.
const VIEWS = ["all", "gui", "cli"];

function currentView() {
  try {
    const view = localStorage.getItem("view");
    return VIEWS.includes(view) ? view : "all";
  } catch {
    return "all";
  }
}

function setView(view) {
  try {
    localStorage.setItem("view", view);
  } catch {
    // localStorage unavailable — the choice just won't survive a restart.
  }
}

function showError(message) {
  errorBannerEl.textContent = message;
  errorBannerEl.hidden = false;
}

function categoryIconPath(category) {
  return `assets/icons/category/${category}.png`;
}

function iconPath(app) {
  return `assets/icons/${app.icon}`;
}

// What a tile shows when it has no icon of its own: CLI tools get the terminal
// glyph, everything else its category's.
function fallbackIconPath(app) {
  return app.cli ? "assets/icons/category/cli-tool.png" : categoryIconPath(app.category);
}

function effective(app) {
  const o = overrides[app.id] || {};
  return {
    ...app,
    // The user's rename must not change what the backend looks for: it matches
    // this against the Start Menu on Windows.
    catalogName: app.name,
    name: o.name ?? app.name,
    category: o.category ?? app.category,
    hidden: o.hidden ?? false,
  };
}

async function persistOverrides() {
  try {
    await invoke("save_overrides", { overrides });
  } catch (err) {
    showError(`Couldn't save your changes: ${err}`);
  }
}

function setOverride(id, patch) {
  overrides[id] = { ...overrides[id], ...patch };
  persistOverrides();
}

function clearOverride(id) {
  delete overrides[id];
  persistOverrides();
}

// Icons the backend extracted from the installed app itself, for tiles whose
// shipped icon is missing: id -> data URL, or null while looking / if none.
const localIcons = new Map();

async function fetchLocalIcon(app) {
  localIcons.set(app.id, null);
  try {
    const url = await invoke("get_icon", { id: app.id, bin: app.bin, name: app.catalogName });
    if (!url) return;
    localIcons.set(app.id, url);
    // A re-render may have replaced the tile that asked, so update by id.
    for (const img of document.querySelectorAll("img[data-icon-id]")) {
      if (img.dataset.iconId === app.id) img.src = url;
    }
  } catch {
    // No local icon — the category glyph stays.
  }
}

function makeIcon(app) {
  const img = document.createElement("img");
  img.dataset.iconId = app.id;
  img.src = localIcons.get(app.id) || iconPath(app);
  img.alt = "";
  img.onerror = () => {
    img.onerror = null;
    img.src = fallbackIconPath(app);
    if (!localIcons.has(app.id)) fetchLocalIcon(app);
  };
  return img;
}

// onCancel just swaps the tile back; save/reset re-render instead, since the
// old tile still shows the pre-edit name/category.
function makeEditForm(app, onCancel) {
  const form = document.createElement("div");
  form.className = "tile tile-edit-form";

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = app.name;
  nameInput.className = "edit-name";

  const select = document.createElement("select");
  select.className = "edit-category";
  for (const category of CATEGORY_ORDER) {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = `${CATEGORY_ICONS[category] || ""} ${category}`;
    if (category === app.category) option.selected = true;
    select.appendChild(option);
  }

  const buttons = document.createElement("div");
  buttons.className = "edit-form-buttons";

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.textContent = "✓";
  saveBtn.title = "Save";
  saveBtn.className = "edit-save";
  saveBtn.addEventListener("click", () => {
    const patch = {};
    if (nameInput.value.trim() && nameInput.value.trim() !== app.name) {
      patch.name = nameInput.value.trim();
    }
    if (select.value !== app.category) {
      patch.category = select.value;
    }
    if (Object.keys(patch).length > 0) setOverride(app.id, patch);
    render();
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.textContent = "✕";
  cancelBtn.title = "Cancel (Esc)";
  cancelBtn.className = "edit-cancel";
  cancelBtn.addEventListener("click", onCancel);

  const resetBtn = document.createElement("button");
  resetBtn.type = "button";
  resetBtn.textContent = "↺";
  resetBtn.title = "Remove all customizations for this app";
  resetBtn.className = "edit-reset";
  resetBtn.addEventListener("click", () => {
    clearOverride(app.id);
    render();
  });

  buttons.append(saveBtn, cancelBtn, resetBtn);
  form.append(makeIcon(app), nameInput, select, buttons);
  return form;
}

function makeTile(app) {
  const wrapper = document.createElement("div");
  wrapper.className = "tile-wrapper";

  const button = document.createElement("button");
  button.className = "tile";
  button.type = "button";
  button.dataset.name = app.name.toLowerCase();
  button.title = app.name; // labels are clamped to two lines
  button.append(makeIcon(app));
  const label = document.createElement("span");
  label.textContent = app.name;
  button.append(label);

  button.addEventListener("click", async () => {
    if (editMode) return;
    try {
      await invoke("launch_app", { bin: app.bin, cli: !!app.cli, name: app.catalogName });
    } catch (err) {
      showError(`Couldn't launch ${app.name}: ${err}`);
    }
  });

  wrapper.appendChild(button);

  if (editMode) {
    const toolbar = document.createElement("div");
    toolbar.className = "tile-toolbar";

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "tile-action tile-edit";
    editBtn.textContent = "✎"; // ✎
    editBtn.title = "Rename / recategorize";
    editBtn.addEventListener("click", () => {
      const form = makeEditForm(app, () => {
        form.replaceWith(wrapper);
      });
      wrapper.replaceWith(form);
    });

    const hideBtn = document.createElement("button");
    hideBtn.type = "button";
    hideBtn.className = "tile-action tile-hide";
    hideBtn.textContent = "×"; // ×
    hideBtn.title = "Hide this app";
    hideBtn.addEventListener("click", () => {
      setOverride(app.id, { hidden: true });
      render();
    });

    toolbar.append(editBtn, hideBtn);
    wrapper.appendChild(toolbar);
  }

  return wrapper;
}

function makeHiddenPanel(hiddenApps) {
  const section = document.createElement("section");
  section.className = "category hidden-panel";

  const heading = document.createElement("h2");
  heading.textContent = `Hidden apps (${hiddenApps.length})`;
  section.appendChild(heading);

  if (hiddenApps.length === 0) {
    const p = document.createElement("p");
    p.className = "hidden-empty";
    p.textContent = "Nothing hidden.";
    section.appendChild(p);
    return section;
  }

  const list = document.createElement("div");
  list.className = "hidden-list";
  for (const app of hiddenApps) {
    const row = document.createElement("div");
    row.className = "hidden-row";
    const name = document.createElement("span");
    name.textContent = app.name;
    const unhideBtn = document.createElement("button");
    unhideBtn.type = "button";
    unhideBtn.textContent = "Unhide";
    unhideBtn.addEventListener("click", () => {
      setOverride(app.id, { hidden: false });
      render();
    });
    row.append(name, unhideBtn);
    list.appendChild(row);
  }
  section.appendChild(list);
  return section;
}

function makeCliSection(cliApps) {
  const section = document.createElement("section");
  section.className = "category cli-section";

  const heading = document.createElement("h2");
  const icon = document.createElement("span");
  icon.className = "category-icon";
  icon.textContent = "⌨️"; // ⌨️
  icon.setAttribute("aria-hidden", "true");
  const label = document.createElement("span");
  label.textContent = `CLI Tools (${cliApps.length})`;
  heading.append(icon, label);
  heading.title = "Terminal-only tools — clicking one opens it in a terminal window";
  section.appendChild(heading);

  const grid = document.createElement("div");
  grid.className = "grid";
  for (const app of cliApps) {
    grid.appendChild(makeTile(app));
  }
  section.appendChild(grid);

  return section;
}

function renderPills(view, counts) {
  for (const pill of pillEls) {
    const active = pill.dataset.view === view;
    pill.classList.toggle("active", active);
    pill.setAttribute("aria-pressed", String(active));
    pill.querySelector(".count").textContent = counts[pill.dataset.view];
  }
}

// Cards are dealt into columns by hand rather than with CSS multi-column: that
// balances *height*, but tall cards can't split, so it happily leaves the
// right-hand columns empty. Putting each card in the currently shortest column
// fills the whole width, so more of the launcher is visible at once.
const MIN_CARD_WIDTH = 270;
const CARD_GAP = 14;
let cards = [];
let columnCount = 0;

function layoutCards() {
  const width = categoriesEl.clientWidth;
  columnCount = Math.max(1, Math.floor((width + CARD_GAP) / (MIN_CARD_WIDTH + CARD_GAP)));
  const columns = Array.from({ length: columnCount }, () => {
    const column = document.createElement("div");
    column.className = "col";
    return column;
  });
  categoriesEl.replaceChildren(...columns);
  for (const card of cards) {
    // Measured as they go in, so a card lands where there is actually room.
    const shortest = columns.reduce((a, b) => (a.offsetHeight <= b.offsetHeight ? a : b));
    shortest.appendChild(card);
  }
}

function renderCategories(grouped, hiddenApps, cliApps, view) {
  cards = [];
  messagesEl.replaceChildren();

  // CLI Tools is the first card, then the regular categories in their fixed order.
  if (view !== "gui" && cliApps.length > 0) cards.push(makeCliSection(cliApps));

  for (const category of view === "cli" ? [] : CATEGORY_ORDER) {
    const apps = grouped.get(category);
    if (!apps || apps.length === 0) continue;

    const section = document.createElement("section");
    section.className = "category";

    const heading = document.createElement("h2");
    const icon = document.createElement("span");
    icon.className = "category-icon";
    icon.textContent = CATEGORY_ICONS[category] || "";
    icon.setAttribute("aria-hidden", "true");
    const label = document.createElement("span");
    label.textContent = category;
    heading.append(icon, label);

    const grid = document.createElement("div");
    grid.className = "grid";
    for (const app of apps) {
      grid.appendChild(makeTile(app));
    }

    section.append(heading, grid);
    cards.push(section);
  }

  if (cards.length === 0) {
    const empty = document.createElement("p");
    empty.id = "empty-state";
    empty.textContent =
      view === "cli" ? "No CLI tools found on this machine." : "No catalog apps found installed on this machine.";
    messagesEl.appendChild(empty);
  }

  if (editMode) cards.push(makeHiddenPanel(hiddenApps));

  const noResults = document.createElement("p");
  noResults.id = "no-results";
  noResults.hidden = true;
  noResults.textContent = "No apps match your search.";
  messagesEl.appendChild(noResults);

  layoutCards();
}

function applySearch(query) {
  const q = query.trim().toLowerCase();
  const noResultsEl = document.getElementById("no-results");
  let anyVisible = false;

  for (const section of categoriesEl.querySelectorAll("section.category:not(.hidden-panel)")) {
    let sectionHasVisible = false;
    for (const tile of section.querySelectorAll(".tile-wrapper")) {
      const matches = !q || tile.querySelector(".tile").dataset.name.includes(q);
      tile.hidden = !matches;
      if (matches) sectionHasVisible = true;
    }
    section.hidden = !sectionHasVisible;
    if (sectionHasVisible) anyVisible = true;
  }

  if (noResultsEl) {
    noResultsEl.hidden = anyVisible || !q;
  }
  // Filtering empties some cards, so re-deal the rest to keep columns even.
  layoutCards();
}

function render() {
  const merged = installedApps.map(effective);
  const visible = merged.filter((app) => !app.hidden);
  const hiddenApps = merged.filter((app) => app.hidden);

  // CLI tools get their own card, shown first, instead of being scattered across
  // the 10 regular categories — grouped together since they're a different
  // kind of tile (opens a terminal, not a normal app window).
  const cliApps = visible.filter((app) => app.cli).sort((a, b) => a.name.localeCompare(b.name));
  const guiApps = visible.filter((app) => !app.cli);

  const grouped = new Map();
  for (const app of guiApps) {
    if (!grouped.has(app.category)) grouped.set(app.category, []);
    grouped.get(app.category).push(app);
  }
  for (const apps of grouped.values()) {
    apps.sort((a, b) => a.name.localeCompare(b.name));
  }

  const view = currentView();
  renderPills(view, { all: visible.length, gui: guiApps.length, cli: cliApps.length });
  renderCategories(grouped, hiddenApps, cliApps, view);
  if (searchEl.value) applySearch(searchEl.value);
}

async function main() {
  let catalog;
  try {
    const res = await fetch("./data/catalog.json");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    catalog = await res.json();
  } catch (err) {
    showError(`Couldn't load the app catalog: ${err}`);
    return;
  }

  try {
    overrides = await invoke("load_overrides");
  } catch (err) {
    overrides = {};
  }

  const candidates = catalog.filter((entry) => !entry.hidden);
  const checks = await Promise.all(
    // One failing lookup must not take the whole dashboard down with it.
    candidates.map((entry) => invoke("is_installed", { bin: entry.bin, name: entry.name }).catch(() => false))
  );
  installedApps = candidates.filter((_, i) => checks[i]);

  render();

  searchEl.addEventListener("input", () => applySearch(searchEl.value));
  // Only a change in how many columns fit needs a re-deal, not every pixel.
  window.addEventListener("resize", () => {
    const fits = Math.max(1, Math.floor((categoriesEl.clientWidth + CARD_GAP) / (MIN_CARD_WIDTH + CARD_GAP)));
    if (fits !== columnCount) layoutCards();
  });
  for (const pill of pillEls) {
    pill.addEventListener("click", () => {
      setView(pill.dataset.view);
      render();
    });
  }
  editToggleEl.addEventListener("click", () => {
    editMode = !editMode;
    editToggleEl.classList.toggle("active", editMode);
    editToggleEl.textContent = editMode ? "Done" : "✎ Edit";
    render();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const openForm = document.querySelector(".tile-edit-form");
    if (openForm) {
      openForm.querySelector(".edit-cancel")?.click();
    } else if (editMode) {
      editToggleEl.click();
    }
  });
}

main();
