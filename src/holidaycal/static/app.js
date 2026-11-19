if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js");
}

let pending;

document.documentElement.classList.add("js");

document.addEventListener("change", (event) => {
  if (event.target.matches(".combobox-input")) return;
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
  if (response.status === 400) {
    showError(form, await response.text());
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
  history.replaceState(null, "", response.url);
  await transition(() => swap(next));
  // Fired once the page takes input again, after any transition.
  document.dispatchEvent(new Event("app:updated"));
});

function showError(form, message) {
  let error = form.querySelector(".form-error");
  if (!error) {
    error = document.createElement("p");
    error.className = "form-error";
    error.setAttribute("role", "alert");
    form.prepend(error);
  }
  error.textContent = message;
}

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

// Event format card: previews the hovered or focused holiday.

async function transition(update) {
  if (document.startViewTransition) {
    await document.startViewTransition(update).finished;
  } else {
    update();
  }
}

function showCard(data, hint) {
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
  const label = document.querySelector('[data-field="hint"]');
  if (label) label.textContent = hint ?? label.dataset.defaultHint;
}

function restoreCard() {
  const card = document.querySelector(".gcal");
  if (card) showCard(JSON.parse(card.dataset.card));
}

function preview(row) {
  showCard(JSON.parse(row.dataset.card), "Previewing");
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

// Clicking anywhere on a preview row toggles it, like its eye button.
document.addEventListener("click", (event) => {
  const row = event.target.closest?.("tr.previewable");
  if (!row || event.target.closest("button, a, abbr")) return;
  row.querySelector(".eye")?.click();
});

// "Add" autocomplete over the hidden select, following the ARIA combobox pattern.

const fold = (text) =>
  text.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

function comboboxParts(input) {
  const list = document.getElementById(input.getAttribute("aria-controls"));
  return { list, options: [...list.querySelectorAll('[role="option"]')] };
}

function visibleOptions(input) {
  return comboboxParts(input).options.filter((option) => !option.hidden);
}

function openCombobox(input) {
  const { list, options } = comboboxParts(input);
  const query = fold(input.value.trim());
  for (const option of options) {
    option.hidden = !fold(option.dataset.search).includes(query);
  }
  for (const group of list.querySelectorAll(".combobox-group")) {
    let next = group.nextElementSibling;
    let any = false;
    while (next && !next.classList.contains("combobox-group")) {
      any ||= !next.hidden;
      next = next.nextElementSibling;
    }
    group.hidden = !any;
  }
  list.hidden = false;
  input.setAttribute("aria-expanded", "true");
  setActive(input, visibleOptions(input)[0] ?? null);
}

function closeCombobox(input) {
  comboboxParts(input).list.hidden = true;
  input.setAttribute("aria-expanded", "false");
  setActive(input, null);
}

function setActive(input, option) {
  for (const other of comboboxParts(input).options) {
    other.classList.toggle("active", other === option);
    other.setAttribute("aria-selected", String(other === option));
  }
  if (option) {
    input.setAttribute("aria-activedescendant", option.id);
    option.scrollIntoView({ block: "nearest" });
  } else {
    input.removeAttribute("aria-activedescendant");
  }
}

function choose(input, option) {
  const select = input.closest(".add").querySelector("select");
  select.value = option.dataset.value;
  closeCombobox(input);
  select.form.requestSubmit();
}

document.addEventListener("focusin", (event) => {
  if (event.target.matches?.(".combobox-input")) openCombobox(event.target);
});

document.addEventListener("input", (event) => {
  if (event.target.matches(".combobox-input")) openCombobox(event.target);
});

document.addEventListener("focusout", (event) => {
  if (event.target.matches?.(".combobox-input")) closeCombobox(event.target);
});

document.addEventListener("mousedown", (event) => {
  const option = event.target.closest?.('.combobox-list [role="option"]');
  if (!option) return;
  // Keep focus in the input so focusout doesn't close the list first.
  event.preventDefault();
  const input = document.querySelector(
    `[aria-controls="${option.closest(".combobox-list").id}"]`,
  );
  choose(input, option);
});

document.addEventListener("keydown", (event) => {
  const input = event.target;
  if (!input.matches?.(".combobox-input")) return;
  const options = visibleOptions(input);
  const active = options.findIndex((o) => o.classList.contains("active"));
  switch (event.key) {
    case "ArrowDown":
    case "ArrowUp": {
      event.preventDefault();
      if (comboboxParts(input).list.hidden) openCombobox(input);
      const step = event.key === "ArrowDown" ? 1 : -1;
      const next = (active + step + options.length) % options.length;
      setActive(input, options[next] ?? null);
      break;
    }
    case "Enter":
      event.preventDefault();
      if (options[Math.max(active, 0)]) choose(input, options[Math.max(active, 0)]);
      break;
    case "Escape":
      input.value = "";
      closeCombobox(input);
      break;
  }
});
