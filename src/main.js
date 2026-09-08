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

// installedApps: the fixed result of the catalog + is_installed check,
// computed once at startup. overrides: user hide/rename/recategorize edits,
// persisted via save_overrides and re-applied on top of installedApps
// every render — catalog.json itself is never touched at runtime.
let installedApps = [];
let overrides = {};
let editMode = false;

function cliToolsVisible() {
  try {
    return localStorage.getItem("cliToolsVisible") !== "false";
  } catch {
    return true;
  }
}

function setCliToolsVisible(visible) {
  try {
    localStorage.setItem("cliToolsVisible", visible ? "true" : "false");
  } catch {
    // localStorage unavailable (e.g. private-browsing-style restrictions) —
    // the toggle just won't persist across restarts, no big deal.
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
  if (app.cli) return "assets/icons/category/cli-tool.png";
  return `assets/icons/${app.icon}`;
}

function effective(app) {
  const o = overrides[app.id] || {};
  return {
    ...app,
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

function makeIcon(app) {
  const img = document.createElement("img");
  img.src = iconPath(app);
  img.alt = "";
  img.onerror = () => {
    img.onerror = null;
    img.src = categoryIconPath(app.category);
  };
  return img;
}

function makeEditForm(app, onDone) {
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
    onDone();
  });

  const cancelBtn = document.createElement("button");
  cancelBtn.type = "button";
  cancelBtn.textContent = "✕";
  cancelBtn.title = "Cancel (Esc)";
  cancelBtn.className = "edit-cancel";
  cancelBtn.addEventListener("click", onDone);

  const resetBtn = document.createElement("button");
  resetBtn.type = "button";
  resetBtn.textContent = "↺";
  resetBtn.title = "Remove all customizations for this app";
  resetBtn.className = "edit-reset";
  resetBtn.addEventListener("click", () => {
    clearOverride(app.id);
    onDone();
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
  button.append(makeIcon(app));
  const label = document.createElement("span");
  label.textContent = app.name;
  button.append(label);

  button.addEventListener("click", async () => {
    if (editMode) return;
    try {
      await invoke("launch_app", { bin: app.bin, cli: !!app.cli });
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
  const toggleBtn = document.createElement("button");
  toggleBtn.type = "button";
  toggleBtn.className = "cli-toggle";
  const visible = cliToolsVisible();
  toggleBtn.textContent = visible ? "Hide" : "Show";
  toggleBtn.addEventListener("click", () => {
    setCliToolsVisible(!cliToolsVisible());
    render();
  });
  heading.append(icon, label, toggleBtn);
  section.appendChild(heading);

  if (visible) {
    const note = document.createElement("p");
    note.className = "cli-note";
    note.textContent = "Terminal-only tools — opens in a terminal instead of a normal window.";
    section.appendChild(note);

    const grid = document.createElement("div");
    grid.className = "grid";
    for (const app of cliApps) {
      grid.appendChild(makeTile(app));
    }
    section.appendChild(grid);
  }

  return section;
}

function renderCategories(grouped, hiddenApps, cliApps) {
  categoriesEl.replaceChildren();
  let renderedAny = false;

  for (const category of CATEGORY_ORDER) {
    const apps = grouped.get(category);
    if (!apps || apps.length === 0) continue;
    renderedAny = true;

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
    categoriesEl.appendChild(section);
  }

  if (cliApps.length > 0) {
    renderedAny = true;
    categoriesEl.appendChild(makeCliSection(cliApps));
  }

  if (!renderedAny) {
    const empty = document.createElement("p");
    empty.id = "empty-state";
    empty.textContent = "No catalog apps found installed on this machine.";
    categoriesEl.appendChild(empty);
  }

  if (editMode) {
    categoriesEl.appendChild(makeHiddenPanel(hiddenApps));
  }

  const noResults = document.createElement("p");
  noResults.id = "no-results";
  noResults.hidden = true;
  noResults.textContent = "No apps match your search.";
  categoriesEl.appendChild(noResults);
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
}

function render() {
  const merged = installedApps.map(effective);
  const visible = merged.filter((app) => !app.hidden);
  const hiddenApps = merged.filter((app) => app.hidden);

  // CLI tools get their own section instead of being scattered across the
  // 10 regular categories — grouped together since they're a different
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

  renderCategories(grouped, hiddenApps, cliApps);
  if (searchEl.value) applySearch(searchEl.value);
}

async function main() {
  let catalog;
  try {
    const res = await fetch("./data/catalog.json");
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
    candidates.map((entry) => invoke("is_installed", { bin: entry.bin }))
  );
  installedApps = candidates.filter((_, i) => checks[i]);

  render();

  searchEl.addEventListener("input", () => applySearch(searchEl.value));
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
