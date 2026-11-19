let pending;

document.addEventListener("change", (event) => {
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
  swap(next);
  history.replaceState(null, "", response.url);
});

function swap(next) {
  const open = new Set(
    [...document.querySelectorAll("details[open]")].map((d) => d.dataset.key),
  );
  const focused = document.activeElement;
  document.getElementById("app").replaceWith(next);
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
