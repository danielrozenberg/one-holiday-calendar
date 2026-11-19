// A small driver for one headless Chrome tab over the DevTools protocol.

export class Page {
  #socket;
  #nextId = 0;
  #waiting = new Map();
  #listeners = new Map();

  constructor(socket, baseUrl) {
    this.#socket = socket;
    this.baseUrl = baseUrl;
    socket.addEventListener("message", (message) => {
      const reply = JSON.parse(String(message.data));
      if (reply.id !== undefined) {
        this.#waiting.get(reply.id)?.(reply);
        this.#waiting.delete(reply.id);
      } else if (reply.method) {
        for (const listener of this.#listeners.get(reply.method) ?? []) listener();
        this.#listeners.delete(reply.method);
      }
    });
  }

  static async open(debuggerUrl, baseUrl) {
    const socket = new WebSocket(debuggerUrl);
    await new Promise((resolve, reject) => {
      socket.addEventListener("open", resolve);
      socket.addEventListener("error", reject);
    });
    const page = new Page(socket, baseUrl);
    await page.send("Page.enable");
    await page.send("Network.enable");
    return page;
  }

  close() {
    this.#socket.close();
  }

  async send(method, params = {}) {
    const id = ++this.#nextId;
    const reply = await new Promise((resolve) => {
      this.#waiting.set(id, resolve);
      this.#socket.send(JSON.stringify({ id, method, params }));
    });
    if (reply.error) throw new Error(`${method}: ${reply.error.message}`);
    return reply.result ?? {};
  }

  #once(event) {
    return new Promise((resolve) => {
      this.#listeners.set(event, [...(this.#listeners.get(event) ?? []), resolve]);
    });
  }

  /** Evaluates a JavaScript expression in the page and returns its value. */
  async evaluate(expression) {
    const reply = await this.send("Runtime.evaluate", {
      expression,
      awaitPromise: true,
      returnByValue: true,
    });
    if (reply.exceptionDetails) {
      const { exception, text } = reply.exceptionDetails;
      throw new Error(exception?.description ?? text);
    }
    return reply.result.value;
  }

  async goto(path) {
    const loaded = this.#once("Page.loadEventFired");
    await this.send("Page.navigate", { url: new URL(path, this.baseUrl).href });
    await loaded;
  }

  /** Runs a page action and waits for the in-place update it triggers. */
  async update(action) {
    await this.expectUpdate();
    await this.evaluate(`{ ${action} }`);
    await this.updated();
  }

  /** Starts listening for the next in-place update; await `updated()` after. */
  async expectUpdate() {
    await this.evaluate(`window.nextUpdate = new Promise((resolve, reject) => {
      document.addEventListener("app:updated", resolve, { once: true });
      setTimeout(() => reject(new Error("No page update")), 5000);
    }); undefined`);
  }

  async updated() {
    await this.evaluate("window.nextUpdate");
  }

  /** Adds a country code or "@religion" through the hidden select. */
  async add(kind) {
    await this.update(`
      const select = document.getElementById("add");
      select.value = ${JSON.stringify(kind)};
      select.form.requestSubmit();
    `);
  }

  /** Returns the viewport centre of the element an expression selects. */
  async centre(element) {
    return this.evaluate(`(() => {
      const element = ${element};
      element.scrollIntoView({ block: "center" });
      const box = element.getBoundingClientRect();
      return [box.left + Math.min(box.width / 2, 20), box.top + box.height / 2];
    })()`);
  }

  async mouse(x, y, click = false) {
    await this.send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    if (!click) return;
    for (const type of ["mousePressed", "mouseReleased"]) {
      await this.send("Input.dispatchMouseEvent", {
        type,
        x,
        y,
        button: "left",
        clickCount: 1,
      });
    }
  }

  async hover(element) {
    const [x, y] = await this.centre(element);
    await this.mouse(x, y);
  }

  async click(element) {
    const [x, y] = await this.centre(element);
    await this.mouse(x, y, true);
  }

  async type(text) {
    await this.send("Input.insertText", { text });
  }

  async press(key, keyCode) {
    await this.send("Input.dispatchKeyEvent", {
      type: "keyDown",
      key,
      code: key,
      windowsVirtualKeyCode: keyCode,
    });
  }
}

/** Selects the preview row of a holiday by its name. */
export const row = (name) =>
  `[...document.querySelectorAll("tr.previewable")].find(
    (r) => r.cells[1].textContent.trim() === ${JSON.stringify(name)})`;
