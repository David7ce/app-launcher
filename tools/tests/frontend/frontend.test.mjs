// Runs the real src/index.html + src/main.js under jsdom, with the Tauri bridge
// stubbed. Run from this folder:  npm ci && npm test
import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import { JSDOM } from "jsdom";

const SRC = new URL("../../../src/", import.meta.url);
const INDEX_HTML = fs.readFileSync(new URL("index.html", SRC), "utf8").replace(/<script src="main.js"><\/script>/, "");
const MAIN_JS = fs.readFileSync(new URL("main.js", SRC), "utf8");

const entry = (id, name, category, extra = {}) => ({
  id, name, vendor: "", category, bin: { linux: id }, icon: `${id}.png`, hidden: false, cli: false, ...extra,
});

const CATALOG = [
  entry("gimp", "GIMP", "Graphics"),
  entry("inkscape", "Inkscape", "Graphics"),
  entry("firefox", "Firefox", "Internet"),
  entry("vscode", "Visual Studio Code", "Development"),
  entry("git", "Git", "Development", { cli: true }),
  entry("ripgrep", "ripgrep", "Utilities", { cli: true }),
  entry("notinstalled", "Not Installed", "Office"),
  // Renamed since an earlier release: edits saved under "win-camera" must follow it.
  entry("camera", "Camera", "Multimedia", { bin: { windows: "" }, aka: ["win-camera"] }),
];

/** Load the page and wait for the first render. */
async function launch({ overrides = {}, view, width = 1400 } = {}) {
  const dom = new JSDOM(INDEX_HTML, { runScripts: "outside-only", url: "http://localhost/" });
  const { window } = dom;
  if (view) window.localStorage.setItem("view", view);

  const state = { overrides: structuredClone(overrides), calls: [] };
  window.fetch = async () => ({ ok: true, json: async () => CATALOG });
  window.__TAURI__ = {
    core: {
      invoke: async (cmd, args) => {
        state.calls.push([cmd, args]);
        if (cmd === "load_overrides") return structuredClone(state.overrides);
        if (cmd === "save_overrides") { state.overrides = structuredClone(args.overrides); return; }
        if (cmd === "is_installed") return args.name !== "Not Installed";
        return null; // get_icon: nothing found; launch_app: ok
      },
    },
  };
  // jsdom has no layout: fake a width, and a height that grows with the number of
  // cards in a column, so the column dealing has something to balance.
  Object.defineProperty(window.HTMLElement.prototype, "clientWidth", { configurable: true, get: () => width });
  Object.defineProperty(window.HTMLElement.prototype, "offsetHeight", {
    configurable: true,
    get() { return this.classList.contains("col") ? this.children.length * 100 : 0; },
  });

  window.eval(MAIN_JS);
  await until(() => window.document.querySelector("#categories .tile"));
  return { window, doc: window.document, state };
}

async function until(fn, tries = 200) {
  for (let i = 0; i < tries; i++) {
    const value = fn();
    if (value) return value;
    await new Promise((r) => setTimeout(r, 5));
  }
  throw new Error("timed out waiting for the page");
}

const cardTitles = (doc) => [...doc.querySelectorAll("#categories section.category h2")].map((h) => h.textContent.trim());
const tileNames = (doc) => [...doc.querySelectorAll("#categories .tile-wrapper:not([hidden]) .tile span")].map((s) => s.textContent);
const clickPill = (doc, view) => doc.querySelector(`.pill[data-view="${view}"]`).click();
const tile = (doc, name) => [...doc.querySelectorAll("#categories .tile")].find((t) => t.querySelector("span").textContent === name);

test("CLI Tools is the first card, then the categories in their fixed order", async () => {
  // One column, so the DOM order is the logical order (with several columns it runs down each).
  const { doc } = await launch({ width: 300 });
  const titles = cardTitles(doc);
  assert.match(titles[0], /^\S*\s*CLI Tools \(2\)$/);
  // The card title is an emoji glued to the label, so drop everything before the first letter.
  assert.deepEqual(titles.slice(1).map((t) => t.replace(/^[^A-Za-z]+/, "")), ["Development", "Graphics", "Internet", "Multimedia"]);
});

test("only installed apps are shown, and the pills count what is visible", async () => {
  const { doc } = await launch();
  assert.ok(!tileNames(doc).includes("Not Installed"));
  const counts = Object.fromEntries([...doc.querySelectorAll(".pill")].map((p) => [p.dataset.view, p.querySelector(".count").textContent]));
  assert.deepEqual(counts, { all: "7", gui: "5", cli: "2" });
});

test("GUI and CLI pills each show only their kind, and the choice is remembered", async () => {
  const { doc, window } = await launch();
  clickPill(doc, "gui");
  assert.ok(!cardTitles(doc).some((t) => t.includes("CLI Tools")));
  assert.equal(window.localStorage.getItem("view"), "gui");
  assert.ok(doc.querySelector('.pill[data-view="gui"]').classList.contains("active"));

  clickPill(doc, "cli");
  assert.equal(cardTitles(doc).length, 1);
  assert.deepEqual(tileNames(doc).sort(), ["Git", "ripgrep"]);
});

test("a remembered view is restored on start", async () => {
  const { doc } = await launch({ view: "cli" });
  assert.equal(cardTitles(doc).length, 1);
  assert.ok(doc.querySelector('.pill[data-view="cli"]').classList.contains("active"));
});

test("search combines with the pills", async () => {
  const { doc } = await launch();
  const search = doc.getElementById("search");
  search.value = "git";
  search.dispatchEvent(new doc.defaultView.Event("input"));
  assert.deepEqual(tileNames(doc), ["Git"]);

  clickPill(doc, "gui"); // Git is a CLI tool, so nothing matches any more
  assert.deepEqual(tileNames(doc), []);
  assert.equal(doc.getElementById("no-results").hidden, false);
});

test("cards are dealt into as many columns as fit, evenly", async () => {
  const { doc } = await launch({ width: 1400 });
  const columns = [...doc.querySelectorAll("#categories .col")];
  assert.equal(columns.length, 4); // floor((1400 + 14) / (270 + 14))
  const sizes = columns.map((c) => c.children.length);
  assert.equal(sizes.reduce((a, b) => a + b, 0), 5);
  assert.ok(Math.max(...sizes) - Math.min(...sizes) <= 1, `uneven: ${sizes}`);
  assert.equal((await launch({ width: 300 })).doc.querySelectorAll("#categories .col").length, 1);
});

test("the editor renames and recategorises a tile immediately, and Reset undoes it", async () => {
  const { doc, state } = await launch();
  doc.getElementById("edit-toggle").click();
  const wrapper = tile(doc, "GIMP").closest(".tile-wrapper");
  wrapper.querySelector(".tile-edit").click();
  doc.querySelector(".edit-name").value = "GIMP Renamed";
  doc.querySelector(".edit-category").value = "Internet";
  doc.querySelector(".edit-save").click();

  assert.ok(tile(doc, "GIMP Renamed"), "the renamed tile should be shown right away");
  const inInternet = [...doc.querySelectorAll("#categories section.category")]
    .find((s) => s.querySelector("h2").textContent.includes("Internet"));
  assert.ok(inInternet.textContent.includes("GIMP Renamed"));
  assert.deepEqual(state.overrides.gimp, { name: "GIMP Renamed", category: "Internet" });

  tile(doc, "GIMP Renamed").closest(".tile-wrapper").querySelector(".tile-edit").click();
  doc.querySelector(".edit-reset").click();
  assert.ok(tile(doc, "GIMP"));
  assert.equal(state.overrides.gimp, undefined);
});

test("hiding a tile moves it to the Hidden apps panel, and Unhide brings it back", async () => {
  const { doc, state } = await launch();
  doc.getElementById("edit-toggle").click();
  tile(doc, "Firefox").closest(".tile-wrapper").querySelector(".tile-hide").click();
  assert.ok(!tile(doc, "Firefox"));
  assert.equal(state.overrides.firefox.hidden, true);
  assert.match(doc.querySelector(".hidden-panel").textContent, /Firefox/);

  [...doc.querySelectorAll(".hidden-row button")].find((b) => b.textContent === "Unhide").click();
  assert.ok(tile(doc, "Firefox"));
});

test("edits saved under an old id move to the app's new id", async () => {
  const { doc, state } = await launch({ overrides: { "win-camera": { name: "My Camera" }, gimp: { hidden: true } } });
  assert.ok(tile(doc, "My Camera"), "the rename should apply under the new id");
  assert.equal(state.overrides["win-camera"], undefined);
  assert.deepEqual(state.overrides.camera, { name: "My Camera" });
  assert.deepEqual(state.overrides.gimp, { hidden: true }); // unrelated edits untouched
  assert.ok(!tile(doc, "GIMP"));
});

test("launching passes the catalog name, not the user's rename", async () => {
  const { doc, state } = await launch({ overrides: { gimp: { name: "Paint Thing" } } });
  tile(doc, "Paint Thing").click();
  const call = state.calls.find(([cmd]) => cmd === "launch_app");
  assert.equal(call[1].name, "GIMP");
  assert.equal(call[1].cli, false);
  tile(doc, "Git").click();
  assert.equal(state.calls.filter(([cmd]) => cmd === "launch_app").at(-1)[1].cli, true);
});

test("a missing icon falls back to the category glyph, or the terminal glyph for CLI tools", async () => {
  const { doc, state } = await launch();
  const gimp = tile(doc, "GIMP").querySelector("img");
  const git = tile(doc, "Git").querySelector("img");
  assert.match(gimp.getAttribute("src"), /assets\/icons\/gimp\.png$/);

  gimp.onerror();
  git.onerror();
  assert.match(gimp.getAttribute("src"), /assets\/icons\/category\/Graphics\.png$/);
  assert.match(git.getAttribute("src"), /assets\/icons\/category\/cli-tool\.png$/);
  // ...and the backend is asked for an icon of its own, once per app.
  const asked = state.calls.filter(([cmd]) => cmd === "get_icon").map(([, a]) => a.id).sort();
  assert.deepEqual(asked, ["gimp", "git"]);
});
