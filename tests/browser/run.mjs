// Runs the browser tests: starts the app with gunicorn and a headless Chrome,
// then runs each test in a fresh tab.
//
// Usage:  node tests/browser/run.mjs   (from the repo root)

import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as sleep } from "node:timers/promises";

import { Page } from "./page.mjs";
import { tests } from "./tests.mjs";

const python =
  process.env.PYTHON ??
  (existsSync(".venv/bin/python") ? ".venv/bin/python" : "python");
const chrome = process.env.CHROME ?? "google-chrome";
const TEST_TIMEOUT_MS = 60_000;

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
    if (startError) throw startError;
    const value = await get().catch(() => undefined);
    if (value !== undefined) return value;
    await sleep(100);
  }
  throw new Error("Timed out waiting to start");
}

const children = [];
const profile = mkdtempSync(join(tmpdir(), "one-holiday-calendar-chrome-"));
let failures = 0;
let startError;

// Stops the app and Chrome however the run ends: done, failed or interrupted.
process.on("exit", () => {
  for (const child of children) {
    try {
      // Each child leads its own process group, which takes Chrome's helper
      // processes and gunicorn's workers down with it.
      process.kill(-child.pid, "SIGKILL");
    } catch {
      // Already gone, or never started.
    }
  }
  rmSync(profile, { recursive: true, force: true });
});
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => process.exit(130));
}

function start(command, args) {
  const child = spawn(command, args, { stdio: "ignore", detached: true });
  child.on("error", (error) => {
    startError = new Error(`Could not start ${command}: ${error.message}`);
  });
  child.on("exit", (code) => {
    startError ??= new Error(`${command} exited early with code ${code}`);
  });
  // Detached children would otherwise keep this process alive.
  child.unref();
  children.push(child);
}

try {
  const appPort = await freePort();
  const debugPort = await freePort();
  const baseUrl = `http://127.0.0.1:${appPort}/`;
  start(python, ["-m", "gunicorn", "-b", `127.0.0.1:${appPort}`, "one_holiday_calendar.main:app"]);
  start(chrome, [
    "--headless=new",
    "--no-sandbox",
    `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profile}`,
    "--window-size=1280,900",
    "about:blank",
  ]);
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
        // A test that hangs fails instead of blocking the run.
        let timer;
        const timeout = new Promise((_, reject) => {
          timer = setTimeout(
            () => reject(new Error(`Timed out after ${TEST_TIMEOUT_MS / 1000}s`)),
            TEST_TIMEOUT_MS,
          );
        });
        try {
          await Promise.race([
            (async () => {
              await page.goto("/");
              await test.run(page, (name, ok) => {
                console.log(`${ok ? "PASS" : "FAIL"} ${name}`);
                if (!ok) failures++;
              });
            })(),
            timeout,
          ]);
        } finally {
          clearTimeout(timer);
        }
      } catch (error) {
        console.log(`FAIL ${error instanceof Error ? error.message : String(error)}`);
        failures++;
      }
    }
  } finally {
    page.close();
  }
} catch (error) {
  console.log(`FAIL ${error.message}`);
  failures++;
}

console.log(failures ? `${failures} browser check(s) failed.` : "All browser checks passed.");
process.exitCode = failures ? 1 : 0;
