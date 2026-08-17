(() => {
  const savedTheme = localStorage.getItem("gadzivo-theme") || "sunset";
  document.body.dataset.theme = savedTheme;

  const panel = document.getElementById("themePanel");
  document.getElementById("themeToggle")?.addEventListener("click", () => panel.classList.toggle("open"));
  document.getElementById("closeTheme")?.addEventListener("click", () => panel.classList.remove("open"));
  document.querySelectorAll("[data-theme]").forEach((button) => {
    button.addEventListener("click", () => {
      document.body.dataset.theme = button.dataset.theme;
      localStorage.setItem("gadzivo-theme", button.dataset.theme);
      panel.classList.remove("open");
    });
  });

  const splash = document.getElementById("splash");
  if (splash) {
    if (sessionStorage.getItem("gadzivo-welcomed")) {
      splash.classList.add("hide");
    } else {
      window.setTimeout(() => splash.classList.add("hide"), 1250);
      sessionStorage.setItem("gadzivo-welcomed", "yes");
    }
  }
})();
