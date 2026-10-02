// Mermaid parse/render oracle for the conformance test suite.
//
// Runs as a long-lived server: each line on stdin is a JSON array of
// {id, text, render?} objects, and each line on stdout is the matching
// JSON array of {id, ok, error, visibleText}.  Loading Mermaid costs a
// couple of seconds, and a suite of a few hundred parametrised cases
// cannot afford to pay that per test, so the process is started once and
// reused.
//
// The point of this script is that it uses the *real* Mermaid package, so
// a conformance test asserts what Mermaid actually does rather than what
// we believe it does.
//
// `mermaid.parse` answers "does this diagram compile"; `mermaid.render`
// additionally proves that an escape sequence reaches the reader as the
// character it stands for.  Rendering needs far more of a browser than
// parsing does, hence the shims below.

import { createInterface } from "node:readline";
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!DOCTYPE html><body></body>", { pretendToBeVisual: true });

globalThis.window = dom.window;
globalThis.document = dom.window.document;
// navigator is a getter-only property on globalThis in modern Node.
Object.defineProperty(globalThis, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
globalThis.Element = dom.window.Element;
globalThis.SVGElement = dom.window.SVGElement;

// jsdom implements no layout engine, so every geometry query Mermaid makes
// while measuring text has to be stubbed. The numbers only need to be
// self-consistent: the tests read the text content of the SVG, not its
// coordinates.
if (typeof globalThis.CSSStyleSheet === "undefined") {
  globalThis.CSSStyleSheet = class CSSStyleSheet {
    constructor() {
      this.cssRules = [];
    }
    insertRule(rule) {
      this.cssRules.push(rule);
      return 0;
    }
  };
}
const svgProto = dom.window.SVGElement.prototype;
svgProto.getBBox = function getBBox() {
  const text = this.textContent || "";
  return { x: 0, y: 0, width: Math.max(1, text.length * 8), height: 16 };
};
svgProto.getComputedTextLength = function getComputedTextLength() {
  return Math.max(1, (this.textContent || "").length * 8);
};
svgProto.getSubStringLength = function getSubStringLength(_start, length) {
  return Math.max(1, length * 8);
};
svgProto.getScreenCTM = function getScreenCTM() {
  return { a: 1, b: 0, c: 0, d: 1, e: 0, f: 0 };
};
dom.window.SVGSVGElement.prototype.createSVGPoint = function createSVGPoint() {
  return { x: 0, y: 0, matrixTransform: () => ({ x: 0, y: 0 }) };
};

const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false, securityLevel: "loose", suppressErrorRendering: true });

function readStdin() {
  return new Promise((resolve, reject) => {
    let buf = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (buf += chunk));
    process.stdin.on("end", () => resolve(buf));
    process.stdin.on("error", reject);
  });
}

// Text that Mermaid drew, with <br> turned into a real newline so a test
// can assert that a line break survived.
function visibleText(svg) {
  const frag = JSDOM.fragment(`<div>${svg}</div>`);
  const div = frag.firstChild;
  for (const noise of div.querySelectorAll("style, defs, marker")) noise.remove();
  for (const br of div.querySelectorAll("br")) br.replaceWith("\n");
  return div.textContent.replace(/[ \t]+/g, " ").trim();
}

async function handle(cases) {
  const results = [];
  for (const c of cases) {
    try {
      await mermaid.parse(c.text);
      let text = null;
      if (c.render) {
        const id = "oracle" + Math.random().toString(36).slice(2);
        text = visibleText((await mermaid.render(id, c.text)).svg);
      }
      results.push({ id: c.id, ok: true, error: null, visibleText: text });
    } catch (err) {
      const message = String((err && err.message) || err).split("\n")[0];
      results.push({ id: c.id, ok: false, error: message, visibleText: null });
    }
  }
  return results;
}

// One request per line, answered in order. The "ready" handshake lets the
// client distinguish a slow start-up from a crash.
const rl = createInterface({ input: process.stdin });
process.stdout.write(JSON.stringify({ ready: true }) + "\n");

let queue = Promise.resolve();
for await (const line of rl) {
  if (!line.trim()) continue;
  const cases = JSON.parse(line);
  queue = queue.then(async () => {
    process.stdout.write(JSON.stringify(await handle(cases)) + "\n");
  });
  await queue;
}
