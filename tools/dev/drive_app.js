// Dev aid: run JavaScript inside the *real* running Tauri window and print the
// result, so tiles can be inspected and clicked with real IPC (no mocks).
//
//   1. Start the app with WebView2's debug port open (Windows):
//        WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--remote-debugging-port=9333 app-launcher.exe
//   2. node tools/drive_app.js '<async JS expression returning JSON-able>'
//        e.g. '[...document.querySelectorAll(".tile span")].map(e => e.textContent)'
//
// Needs Node 22+ (global WebSocket/fetch). Localhost only; never ship with the
// port enabled.
const expr = process.argv[2];
(async () => {
  const pages = await (await fetch("http://127.0.0.1:9333/json")).json();
  const page = pages.find((p) => p.type === "page");
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  ws.send(JSON.stringify({ id: 1, method: "Runtime.evaluate", params: { expression: expr, awaitPromise: true, returnByValue: true } }));
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id === 1) { console.log(JSON.stringify(d.result.result.value ?? d.result, null, 1)); ws.close(); }
  };
})();
