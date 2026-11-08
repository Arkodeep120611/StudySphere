// Runs in <head> before first paint to avoid a flash of the wrong theme.
(function () {
  var saved = null;
  try { saved = localStorage.getItem("studysphere-theme"); } catch (e) { /* storage blocked */ }
  var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  var theme = saved === "dark" || saved === "light" ? saved : (prefersDark ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
})();
