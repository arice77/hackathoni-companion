const form = document.querySelector("form");
const result = document.querySelector(".result");

form.addEventListener("submit", async (event) => {
  event.preventDefault(); // nothing is sent: the browser never posts the fields
  try {
    const response = await fetch("/pizza-receipt", { method: "POST" }); // empty body, local receipt only
    if (!response.ok) throw new Error("Receipt not saved");
    const heading = document.createElement("h2");
    heading.textContent = "Order received (practice)";
    result.replaceChildren(heading);
  } catch {
    const note = document.createElement("p");
    note.textContent = "Could not save the practice receipt. Try Submit order again.";
    result.replaceChildren(note);
  }
});
