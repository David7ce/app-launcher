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

function showError(message) {
  errorBannerEl.textContent = message;
  errorBannerEl.hidden = false;
}

function categoryIconPath(category) {
  return `assets/icons/category/${category}.svg`;
}

function iconPath(app) {
  if (app.cli) return "assets/icons/category/cli-tool.svg";
  return `assets/icons/${app.icon}`;
}

function makeTile(app) {
  const button = document.createElement("button");
  button.className = "tile";
  button.type = "button";
  button.dataset.name = app.name.toLowerCase();

  const img = document.createElement("img");
  img.src = iconPath(app);
  img.alt = "";
  img.onerror = () => {
    img.onerror = null;
    img.src = categoryIconPath(app.category);
  };

  const label = document.createElement("span");
  label.textContent = app.name;

  button.append(img, label);
  button.addEventListener("click", async () => {
    try {
      await invoke("launch_app", { bin: app.bin });
    } catch (err) {
      showError(`Couldn't launch ${app.name}: ${err}`);
    }
  });

  return button;
}

function renderCategories(grouped) {
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

  if (!renderedAny) {
    const empty = document.createElement("p");
    empty.id = "empty-state";
    empty.textContent = "No catalog apps found installed on this machine.";
    categoriesEl.appendChild(empty);
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

  for (const section of categoriesEl.querySelectorAll("section.category")) {
    let sectionHasVisible = false;
    for (const tile of section.querySelectorAll(".tile")) {
      const matches = !q || tile.dataset.name.includes(q);
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

async function main() {
  let catalog;
  try {
    const res = await fetch("./data/catalog.json");
    catalog = await res.json();
  } catch (err) {
    showError(`Couldn't load the app catalog: ${err}`);
    return;
  }

  const visible = catalog.filter((entry) => !entry.hidden);
  const checks = await Promise.all(
    visible.map((entry) => invoke("is_installed", { bin: entry.bin }))
  );

  const grouped = new Map();
  visible.forEach((entry, i) => {
    if (!checks[i]) return;
    if (!grouped.has(entry.category)) grouped.set(entry.category, []);
    grouped.get(entry.category).push(entry);
  });

  for (const apps of grouped.values()) {
    apps.sort((a, b) => a.name.localeCompare(b.name));
  }

  renderCategories(grouped);
  searchEl.addEventListener("input", () => applySearch(searchEl.value));
}

main();
