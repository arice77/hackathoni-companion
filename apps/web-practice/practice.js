const byId = (id) => document.getElementById(id);
const form = document.querySelector("form");
const screens = [...document.querySelectorAll("[data-screen]")];
const progress = [...document.querySelectorAll("nav li")];
const status = byId("status");
const nameField = byId("business-name");
const declaration = byId("declaration");
const save = byId("save");

function showScreen(index) {
  screens.forEach((screen, position) => {
    screen.hidden = position !== index;
    if (position === index) progress[position].setAttribute("aria-current", "step");
    else progress[position].removeAttribute("aria-current");
  });
  byId("screen-title").textContent = screens[index].dataset.screen;
  status.textContent = "Ready for practice";
  window.scrollTo(0, 0);
}

form.addEventListener("submit", (event) => event.preventDefault());
byId("sample-details").addEventListener("click", () => {
  nameField.value = "TEST Lantern Shop";
  nameField.setCustomValidity("");
  byId("district").value = "Alappuzha";
  byId("category").value = "Retail";
});
byId("details-next").addEventListener("click", () => {
  nameField.setCustomValidity(nameField.value.trim() ? "" : "Enter a made-up business name.");
  if (form.reportValidity()) showScreen(1);
});
nameField.addEventListener("input", () => nameField.setCustomValidity(""));
byId("attach-sample").addEventListener("click", () => {
  byId("document-note").textContent = "Sample attached · no file uploaded";
  byId("documents-next").disabled = false;
});
byId("documents-next").addEventListener("click", () => showScreen(2));
declaration.addEventListener("change", () => { save.disabled = !declaration.checked; });
save.addEventListener("click", async () => {
  save.disabled = true;
  declaration.disabled = true;
  status.textContent = "Saving the practice receipt…";
  try {
    const response = await fetch("/receipt", { method: "POST" });
    if (!response.ok) throw new Error("Receipt not saved");
    status.textContent = "Training complete · practice receipt saved locally";
  } catch {
    declaration.disabled = false;
    save.disabled = !declaration.checked;
    status.textContent = "Could not save the practice receipt. Try Save again.";
  }
});
