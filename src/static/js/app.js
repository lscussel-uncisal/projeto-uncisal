// Interações que exigiriam onclick="" inline — bloqueado pela Content-Security-Policy
// (script-src 'self', sem 'unsafe-inline') — via delegação de evento a partir de atributos
// data-*. Ver docker/nginx/helpdesk.conf para o header CSP.
document.addEventListener("click", function (event) {
  const toggle = event.target.closest("[data-toggle-password]");
  if (toggle) {
    const input = document.getElementById(toggle.getAttribute("data-toggle-password"));
    if (input) {
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      const eye = toggle.querySelector(".icon-eye");
      const eyeOff = toggle.querySelector(".icon-eye-off");
      if (eye) eye.classList.toggle("hidden", !showing);
      if (eyeOff) eyeOff.classList.toggle("hidden", showing);
    }
    return;
  }

  const openModal = event.target.closest("[data-modal-open]");
  if (openModal) {
    const modal = document.getElementById(openModal.getAttribute("data-modal-open"));
    if (modal) modal.showModal();
    return;
  }

  const closeModal = event.target.closest("[data-modal-close]");
  if (closeModal) {
    const modal = document.getElementById(closeModal.getAttribute("data-modal-close"));
    if (modal) modal.close();
  }
});
