document.addEventListener("change", (event) => {
  event.target.form?.requestSubmit();
});

document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy]");
  if (!button) return;
  await navigator.clipboard.writeText(button.dataset.copy);
  button.textContent = "Copied";
});
