// Browser tests for the config page. Each test starts from an empty config.

import { row } from "./page.mjs";

const names = `[...document.querySelectorAll(".source-name")].map((e) => e.textContent).join()`;
const cardTitle = `document.querySelector('.gcal [data-field="title"]').textContent`;

export const tests = [
  {
    name: "updates in place, keeping open sections and focus",
    async run(page, check) {
      await page.add("CA");
      await page.evaluate("window.marker = 1");
      await page.evaluate(
        `document.querySelector('details[data-key="CA:regions"]').open = true`,
      );
      await page.update(`
        const box = document.querySelector('[data-region="CA:ON"]');
        box.focus();
        box.click();
      `);
      check("no reload", await page.evaluate("window.marker === 1"));
      check("url updated", await page.evaluate(`location.pathname.startsWith("/c/")`));
      check(
        "section stays open",
        await page.evaluate(`document.querySelector('details[data-key="CA:regions"]').open`),
      );
      check("focus restored", await page.evaluate(`document.activeElement.value === "ON"`));
      check(
        "preview updated",
        await page.evaluate(`document.querySelector("table").textContent.includes("Family Day")`),
      );
      await page.update(`document.querySelector('button[name="remove"]').click()`);
      check("removed", (await page.evaluate(names)) === "");
    },
  },
  {
    name: "all regions disables but keeps picked regions",
    async run(page, check) {
      await page.add("CA");
      const on = `document.querySelector('[data-region="CA:ON"]')`;
      const all = `document.querySelector("[data-all-regions]")`;
      await page.update(`${on}.click()`);
      await page.update(`${all}.click()`);
      check("disabled but ticked", await page.evaluate(`${on}.disabled && ${on}.checked`));
      const allUrl = await page.evaluate("location.href");
      await page.update(`${all}.click()`);
      check("enabled and ticked again", await page.evaluate(`!${on}.disabled && ${on}.checked`));
      await page.goto(allUrl);
      check("refresh unticks", await page.evaluate(`${on}.disabled && !${on}.checked`));
    },
  },
  {
    name: "reorders with buttons and the drag handle",
    async run(page, check) {
      for (const kind of ["CA", "US", "DE"]) await page.add(kind);
      await page.update(`document.querySelector('button[name="move"][value="0:down"]').click()`);
      check("move down", (await page.evaluate(names)) === "United States,Canada,Germany");
      await page.update(`
        const sources = document.querySelectorAll(".source");
        const handle = sources[2].querySelector(".handle");
        const box = sources[0].getBoundingClientRect();
        const dataTransfer = new DataTransfer();
        const drag = (target, type, init = {}) => target.dispatchEvent(
          new DragEvent(type, { bubbles: true, cancelable: true, dataTransfer, ...init }));
        drag(handle, "dragstart");
        drag(sources[0], "dragover", { clientY: box.top + 2 });
        drag(sources[0], "drop");
        drag(handle, "dragend");
      `);
      check("drag to top", (await page.evaluate(names)) === "Germany,United States,Canada");
    },
  },
  {
    name: "autocomplete lists everything, filters and adds",
    async run(page, check) {
      await page.add("CA");
      const visible = `[...document.querySelectorAll('#add-options [role="option"]')].filter((o) => !o.hidden).length`;
      const total = await page.evaluate(
        `document.querySelectorAll('#add-options [role="option"]').length`,
      );
      check(
        "added source not offered",
        await page.evaluate(`!document.querySelector('#add-options [data-value="CA"]')`),
      );
      await page.click(`document.querySelector(".combobox-input")`);
      check("focus shows everything", (await page.evaluate(visible)) === total);
      await page.type("germ");
      check("typing filters", (await page.evaluate(visible)) === 1);
      await page.expectUpdate();
      await page.press("Enter", 13);
      await page.updated();
      check("enter adds", (await page.evaluate(names)) === "Canada,Germany");
    },
  },
  {
    name: "hides holidays from the preview, with notices",
    async run(page, check) {
      await page.add("CA");
      await page.evaluate(
        `document.querySelector('details[data-key="CA:regions"]').open = true`,
      );
      await page.update(`document.querySelector('[data-region="CA:ON"]').click()`);
      await page.update(`${row("Family Day")}.querySelector(".eye").click()`);
      check("row stays, dimmed", await page.evaluate(`${row("Family Day")}.classList.contains("is-hidden")`));
      check(
        "eye greyed",
        await page.evaluate(`getComputedStyle(${row("Family Day")}.querySelector(".eye")).filter.includes("grayscale")`),
      );
      const feed = await page.evaluate(
        `fetch(location.pathname + "?format=ics").then((r) => r.text())`,
      );
      check("feed drops it", !feed.includes("SUMMARY:Family Day") && feed.includes("SUMMARY:Canada Day"));
      for (;;) {
        const regional = await page.evaluate(`[...document.querySelectorAll("tr.previewable:not(.is-hidden)")]
          .some((r) => r.querySelector(".regions"))`);
        if (!regional) break;
        await page.update(`[...document.querySelectorAll("tr.previewable:not(.is-hidden)")]
          .find((r) => r.querySelector(".regions")).querySelector(".eye").click()`);
      }
      check(
        "region notice",
        await page.evaluate(`[...document.querySelectorAll(".notice")].some((n) => n.textContent.includes("Ontario"))`),
      );
      await page.update(`document.querySelector('button[name="unhide_all"]').click()`);
      check("show all", await page.evaluate(`!document.querySelector("tr.is-hidden")`));
    },
  },
  {
    name: "previews hovered rows and toggles clicked ones",
    async run(page, check) {
      await page.add("CA");
      await page.add("US");
      const original = await page.evaluate(cardTitle);
      await page.hover(row("Thanksgiving Day"));
      check("hover previews", (await page.evaluate(cardTitle)) === "Thanksgiving Day");
      await page.expectUpdate();
      await page.click(`${row("Thanksgiving Day")}.cells[1]`);
      await page.updated();
      check("click hides", await page.evaluate(`${row("Thanksgiving Day")}.classList.contains("is-hidden")`));
      await page.mouse(5, 5);
      check("leaving restores", (await page.evaluate(cardTitle)) === original);
    },
  },
  {
    name: "keeps the event card's height while previewing",
    async run(page, check) {
      await page.add("US");
      await page.add("@jewish");
      await page.update(`document.querySelector('input[name="combine_multiday"]').click()`);
      const height = `document.querySelector(".event-format").getBoundingClientRect().height`;
      const before = await page.evaluate(height);
      const count = await page.evaluate(`document.querySelectorAll("tr.previewable").length`);
      let changed = 0;
      for (let i = 0; i < count; i++) {
        await page.hover(`document.querySelectorAll("tr.previewable")[${i}]`);
        if ((await page.evaluate(height)) !== before) changed++;
      }
      check(`stable over ${count} rows`, changed === 0);
    },
  },
  {
    name: "subscribe box switches between webcal and https URLs",
    async run(page, check) {
      await page.add("CA");
      const url = `document.querySelector("[data-calendar-url]").value`;
      check("webcal by default", (await page.evaluate(url)).startsWith("webcal://"));
      await page.evaluate(`document.querySelector('[name="url_scheme"][value="https"]').click()`);
      check("https when chosen", (await page.evaluate(url)).startsWith("http"));
      check("feed format", (await page.evaluate(url)).endsWith("?format=ics"));
      await page.add("US");
      check("choice survives updates", (await page.evaluate(url)).startsWith("http"));
    },
  },
  {
    name: "back and forward undo and redo changes",
    async run(page, check) {
      await page.add("CA");
      const withCanada = await page.evaluate("location.href");
      await page.add("US");
      check("two sources", (await page.evaluate(names)) === "Canada,United States");
      await page.update("history.back()");
      check("back undoes", (await page.evaluate(names)) === "Canada");
      check("back restores url", (await page.evaluate("location.href")) === withCanada);
      await page.update("history.back()");
      check("back to empty", (await page.evaluate(names)) === "");
      await page.update("history.forward()");
      check("forward redoes", (await page.evaluate(names)) === "Canada");
    },
  },
  {
    name: "finishes loading a page when the service worker stops",
    async run(page, check) {
      await page.add("US");
      await page.update(`document.querySelector("[data-all-regions]").click()`);
      await page.evaluate("navigator.serviceWorker.ready.then(() => true)");
      const url = await page.evaluate("location.href");
      await page.send("ServiceWorker.enable");
      await page.goto(url, {
        onNavigated: () => page.send("ServiceWorker.stopAllWorkers"),
      });
      check("loaded", (await page.evaluate(names)) === "United States");
    },
  },
  {
    name: "serves pages offline through the service worker",
    async run(page, check) {
      await page.add("CA");
      await page.evaluate("navigator.serviceWorker.ready.then(() => true)");
      const url = await page.evaluate("location.href");
      await page.goto(url);
      check("controlled", await page.evaluate("!!navigator.serviceWorker.controller"));
      await page.send("Network.emulateNetworkConditions", {
        offline: true,
        latency: 0,
        downloadThroughput: -1,
        uploadThroughput: -1,
      });
      try {
        await page.goto(url);
        check("offline page", (await page.evaluate(names)) === "Canada");
        check(
          "offline styles",
          await page.evaluate(`getComputedStyle(document.body).backgroundColor !== "rgba(0, 0, 0, 0)"`),
        );
      } finally {
        await page.send("Network.emulateNetworkConditions", {
          offline: false,
          latency: 0,
          downloadThroughput: -1,
          uploadThroughput: -1,
        });
      }
    },
  },
];
