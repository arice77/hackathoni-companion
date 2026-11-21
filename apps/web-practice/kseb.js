const form = document.getElementById("quickpay");
const error = form.querySelector(".error");
const bill = document.querySelector(".bill");
const field = (name) => form.elements[name].value.trim();

document.getElementById("refresh").addEventListener("click", (event) => event.preventDefault()); // same practice image
document.querySelector(".info a").addEventListener("click", (event) => event.preventDefault());

function problem() {
  if (!/^\d{13}$/.test(field("consumerNumber"))) return "Invalid Consumer Number. Please check and re-enter.";
  if (!/^\d{10}$/.test(field("phone"))) return "You must enter a valid Indian mobile number without country code";
  if (field("code").toUpperCase() !== "PRACTICE") return "Please enter text as shown in image";
  return "";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault(); // nothing is sent: the browser never posts the fields
  const message = problem();
  error.hidden = !message;
  error.textContent = message;
  if (message) return;
  try {
    const response = await fetch("/kseb-receipt", { method: "POST" }); // empty body, local receipt only
    if (!response.ok) throw new Error("Receipt not saved");
    form.hidden = true;
    bill.hidden = false;
  } catch {
    error.hidden = false;
    error.textContent = "Could not save the practice receipt. Try Submit to see the bill again.";
  }
});
