(function () {
  "use strict";

  const openButton = document.querySelector("[data-pp-menu-open]");
  const sheet = document.querySelector(".pp-mobile-sheet");
  const backdrop = document.querySelector(".pp-sheet-backdrop");
  const closeButtons = document.querySelectorAll("[data-pp-menu-close]");

  function setMenu(open) {
    if (!openButton || !sheet || !backdrop) return;
    sheet.classList.toggle("is-open", open);
    backdrop.hidden = !open;
    requestAnimationFrame(function () { backdrop.classList.toggle("is-open", open); });
    sheet.setAttribute("aria-hidden", String(!open));
    openButton.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("pp-menu-open", open);
  }

  if (openButton) openButton.addEventListener("click", function () { setMenu(true); });
  closeButtons.forEach(function (button) { button.addEventListener("click", function () { setMenu(false); }); });
  document.addEventListener("keydown", function (event) { if (event.key === "Escape") setMenu(false); });

  document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
    button.addEventListener("click", function () {
      const input = document.getElementById(button.getAttribute("aria-controls"));
      if (!input) return;
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
      const icon = button.querySelector("i");
      if (icon) icon.className = show ? "ph ph-eye-slash" : "ph ph-eye";
    });
  });
})();
