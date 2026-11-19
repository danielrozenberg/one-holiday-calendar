if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

let pending;

document.addEventListener("change", (event) => {
  const all = event.target.closest?.("[data-all-regions]");
  if (all) {
    // Disabled boxes keep their ticks but are left out of the submitted form.
    for (const box of all.closest(".source").querySelectorAll("[data-region]")) {
      box.disabled = all.checked;
    }
  }
  event.target.form?.requestSubmit();
});

document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (form.id !== "config") return;
  event.preventDefault();
  pending?.abort();
  pending = new AbortController();
  const body = new URLSearchParams(new FormData(form, event.submitter));
  let response;
  try {
    response = await fetch(form.action, {
      method: "POST",
      headers: { Accept: "text/html" },
      body,
      signal: pending.signal,
    });
  } catch (error) {
    if (error.name !== "AbortError") form.submit();
    return;
  }
  if (!response.ok) {
    form.submit();
    return;
  }
  const page = new DOMParser().parseFromString(
    await response.text(),
    "text/html",
  );
  const next = page.getElementById("app");
  if (!next) {
    form.submit();
    return;
  }
  transition(() => {
    swap(next);
    restoreCard();
  });
  history.replaceState(null, "", response.url);
});

function swap(next) {
  const open = new Set(
    [...document.querySelectorAll("details[open]")].map((d) => d.dataset.key),
  );
  const focused = document.activeElement;
  const keptRegions = new Set(
    [...document.querySelectorAll("[data-region]:disabled:checked")].map(
      (box) => box.dataset.region,
    ),
  );
  document.getElementById("app").replaceWith(next);
  for (const box of next.querySelectorAll("[data-region]:disabled")) {
    box.checked ||= keptRegions.has(box.dataset.region);
  }
  for (const details of next.querySelectorAll("details[data-key]")) {
    details.open = open.has(details.dataset.key);
  }
  if (focused?.name) {
    const name = CSS.escape(focused.name);
    const value = CSS.escape(focused.value ?? "");
    (
      next.querySelector(`[name="${name}"][value="${value}"]`) ??
      next.querySelector(`[name="${name}"]`)
    )?.focus();
  }
}

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  await navigator.clipboard.writeText(button.dataset.copy);
  button.textContent = "Copied";
});

let dragged;
let orderBefore;

const sourceOrder = () =>
  [...document.querySelectorAll(".source input[name$='.kind']")]
    .map((input) => input.name)
    .join();

document.addEventListener("dragstart", (event) => {
  const handle = event.target.closest?.(".handle");
  if (!handle) return;
  dragged = handle.closest(".source");
  orderBefore = sourceOrder();
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setDragImage(dragged, 16, 16);
  dragged.classList.add("dragging");
});

document.addEventListener("dragover", (event) => {
  const over = dragged && event.target.closest?.(".source");
  if (!over) return;
  event.preventDefault();
  if (over === dragged) return;
  const box = over.getBoundingClientRect();
  const before = event.clientY < box.top + box.height / 2;
  over.before(dragged);
  if (!before) over.after(dragged);
});

document.addEventListener("drop", (event) => {
  if (dragged) event.preventDefault();
});

document.addEventListener("dragend", () => {
  if (!dragged) return;
  const form = dragged.closest("form");
  dragged.classList.remove("dragging");
  dragged = null;
  if (sourceOrder() !== orderBefore) form.requestSubmit();
});

// Event format card: previews the hovered or pinned holiday.

const PIN_KEY = "pinnedEvent";

function transition(update) {
  if (document.startViewTransition) document.startViewTransition(update);
  else update();
}

function pinnedUid() {
  try {
    return sessionStorage.getItem(PIN_KEY);
  } catch {
    return null;
  }
}

function setPinnedUid(uid) {
  try {
    if (uid) sessionStorage.setItem(PIN_KEY, uid);
    else sessionStorage.removeItem(PIN_KEY);
  } catch {
    // Pinning just won't survive page updates.
  }
}

function pinnedRow() {
  const uid = pinnedUid();
  return uid && document.querySelector(`tr[data-uid="${CSS.escape(uid)}"]`);
}

function showCard(data) {
  const card = document.querySelector(".gcal");
  if (!card || !data) return;
  const style =
    document.querySelector('input[name="title_style"]:checked')?.value ??
    "TITLE_STYLE_PLAIN";
  const fields = { ...data, title: data.titles[style] };
  for (const element of card.querySelectorAll("[data-field]")) {
    element.textContent = element.title = fields[element.dataset.field];
  }
  for (const element of card.querySelectorAll("[data-title-style]")) {
    element.textContent = element.title = data.titles[element.dataset.titleStyle];
  }
}

function setHint(text) {
  const hint = document.querySelector('[data-field="hint"]');
  if (hint) hint.textContent = text ?? hint.dataset.defaultHint;
}

function restoreCard() {
  const row = pinnedRow();
  for (const pin of document.querySelectorAll(".pin")) {
    pin.setAttribute("aria-pressed", String(pin.closest("tr") === row));
  }
  const card = document.querySelector(".gcal");
  showCard(JSON.parse((row ?? card)?.dataset.card ?? "null"));
  setHint(row ? "Pinned" : null);
}

function preview(row) {
  showCard(JSON.parse(row.dataset.card));
  setHint(row === pinnedRow() ? "Pinned" : "Previewing");
}

document.addEventListener("pointerover", (event) => {
  const row = event.target.closest?.("tr.previewable");
  if (row) preview(row);
});

document.addEventListener("pointerout", (event) => {
  const row = event.target.closest?.("tr.previewable");
  if (row && !row.contains(event.relatedTarget)) restoreCard();
});

document.addEventListener("focusin", (event) => {
  const row = event.target.closest?.("tr.previewable");
  if (row) preview(row);
});

document.addEventListener("focusout", (event) => {
  const row = event.target.closest?.("tr.previewable");
  if (row && !row.contains(event.relatedTarget)) restoreCard();
});

document.addEventListener("click", (event) => {
  const row = event.target.closest?.("tr.previewable");
  if (!row) return;
  setPinnedUid(row === pinnedRow() ? null : row.dataset.uid);
  transition(() => {
    restoreCard();
    preview(row);
  });
});

restoreCard();
