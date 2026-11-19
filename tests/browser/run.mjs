// Runs the browser tests: starts the app with gunicorn and a headless Chrome,
// then runs each test in a fresh tab.
//
// Usage:  node tests/browser/run.mjs   (from the repo root)

import { spawn } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

import { Page } from "./page.mjs";
import { tests } from "./tests.mjs";

const python = process.env.PYTHON ?? ".venv/bin/python";
const chrome = process.env.CHROME ?? "google-chrome";

function freePort() {
  return new Promise((resolve, reject) => {
    const server = createServer();
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() =>
        typeof address === "object" && address
          ? resolve(address.port)
          : reject(new Error("No port")),
      );
    });
  });
}

async function reachable(url) {
  const response = await fetch(url);
  await response.arrayBuffer();
  return response.ok ? true : undefined;
}

async function poll(get) {
  for (let attempt = 0; attempt < 100; attempt++) {
    const value = await get().catch(() => undefined);
    if (value !== undefined) return value;
    await sleep(100);
  }
  throw new Error("Timed out waiting to start");
}

const children = [];
const profile = mkdtempSync(join(tmpdir(), "holidaycal-chrome-"));
let failures = 0;

try {
  const appPort = await freePort();
  const debugPort = await freePort();
  const baseUrl = `http://127.0.0.1:${appPort}/`;
  children.push(
    spawn(python, ["-m", "gunicorn", "-b", `127.0.0.1:${appPort}`, "holidaycal.main:app"], {
      stdio: "ignore",
    }),
    spawn(
      chrome,
      [
        "--headless=new",
        "--no-sandbox",
        `--remote-debugging-port=${debugPort}`,
        `--user-data-dir=${profile}`,
        "--window-size=1280,900",
        "about:blank",
      ],
      { stdio: "ignore" },
    ),
  );
  await poll(() => reachable(baseUrl));
  const debug = `http://127.0.0.1:${debugPort}`;
  await poll(() => reachable(`${debug}/json/version`));

  // One tab for every test: the config lives in the URL, so each test starts
  // from scratch at "/". Input events only reach Chrome's initial tab.
  const targets = await (await fetch(`${debug}/json/list`)).json();
  const tab = targets.find((target) => target.type === "page");
  const page = await Page.open(tab.webSocketDebuggerUrl, baseUrl);
  try {
    for (const test of tests) {
      console.log(`# ${test.name}`);
      try {
        await page.goto("/");
        await test.run(page, (name, ok) => {
          console.log(`${ok ? "PASS" : "FAIL"} ${name}`);
          if (!ok) failures++;
        });
      } catch (error) {
        console.log(`FAIL ${error instanceof Error ? error.message : String(error)}`);
        failures++;
      }
    }
  } finally {
    page.close();
  }
} finally {
  for (const child of children) child.kill();
  await sleep(200);
  rmSync(profile, { recursive: true, force: true });
}

console.log(failures ? `${failures} browser check(s) failed.` : "All browser checks passed.");
process.exitCode = failures ? 1 : 0;
