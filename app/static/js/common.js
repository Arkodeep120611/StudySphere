/* Shared helpers for StudySphere pages. Exposes window.SS. */
(function () {
  "use strict";

  var SS = (window.SS = window.SS || {});

  SS.esc = function (value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  };

  SS.csrfToken = function () {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  };

  /**
   * JSON API helper. Throws an Error with .status and a user-readable message.
   * Pass { body } for JSON or { formData } for multipart uploads.
   */
  SS.api = async function (url, options) {
    options = options || {};
    var method = (options.method || "GET").toUpperCase();
    var headers = { Accept: "application/json" };
    var init = { method: method, headers: headers, credentials: "same-origin" };

    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    } else if (options.formData) {
      init.body = options.formData;
    }
    if (method !== "GET") {
      headers["X-CSRFToken"] = SS.csrfToken();
    }

    var response;
    try {
      response = await fetch(url, init);
    } catch (networkError) {
      throw new Error("Network error. Check your connection and try again.");
    }

    var data = null;
    try {
      data = await response.json();
    } catch (parseError) {
      data = null;
    }

    if (!response.ok) {
      if (response.status === 401) {
        window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
        throw new Error("Your session has expired. Please log in again.");
      }
      var err = new Error((data && data.error) || "Request failed (" + response.status + ").");
      err.status = response.status;
      throw err;
    }
    return data;
  };

  SS.toast = function (message, type) {
    var host = document.getElementById("toast-host");
    if (!host) {
      host = document.createElement("div");
      host.id = "toast-host";
      host.className = "toast-host";
      document.body.appendChild(host);
    }
    var el = document.createElement("div");
    el.className = "toast" + (type === "error" ? " toast-error" : "");
    el.setAttribute("role", type === "error" ? "alert" : "status");
    el.textContent = message;
    host.appendChild(el);
    setTimeout(function () {
      el.classList.add("leave");
      setTimeout(function () { el.remove(); }, 260);
    }, type === "error" ? 6000 : 3500);
  };

  // Replaces every <i data-lucide="..."> on the page with an SVG. Safe to call repeatedly.
  SS.icons = function () {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  };

  /** Disable a button while an async action runs and show a spinner. */
  SS.setBusy = function (button, busy, label) {
    if (!button) return;
    if (busy) {
      if (!button.dataset.label) button.dataset.label = button.innerHTML;
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
      button.innerHTML = '<span class="spinner" aria-hidden="true"></span><span>' + SS.esc(label || "Working…") + "</span>";
    } else {
      button.disabled = false;
      button.removeAttribute("aria-busy");
      if (button.dataset.label) {
        button.innerHTML = button.dataset.label;
        delete button.dataset.label;
      }
      SS.icons();
    }
  };

  SS.empty = function (icon, title, text) {
    return (
      '<div class="empty"><i data-lucide="' + SS.esc(icon) + '"></i><h3>' + SS.esc(title) +
      "</h3>" + (text ? '<p class="muted">' + SS.esc(text) + "</p>" : "") + "</div>"
    );
  };

  SS.errorBox = function (message) {
    return '<div class="empty"><i data-lucide="circle-alert"></i><p class="muted">' + SS.esc(message) + "</p></div>";
  };

  SS.formatDate = function (iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
  };

  SS.formatDateTime = function (iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
  };

  SS.percent = function (value) {
    return value == null ? "—" : Math.round(value) + "%";
  };

  /**
   * Minimal, safe Markdown: escapes HTML first, then supports **bold**, *italic*,
   * `code`, bullet/numbered lists, headings and paragraphs.
   */
  SS.markdown = function (source) {
    var lines = String(source || "").replace(/\r\n/g, "\n").split("\n");
    var html = "";
    var inList = false;

    function inline(text) {
      return SS.esc(text)
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[^*])\*(?!\s)(.+?)\*/g, "$1<em>$2</em>");
    }

    lines.forEach(function (raw) {
      var line = raw.trim();
      var item = /^[-*•]\s+(.*)$/.exec(line) || /^\d+[.)]\s+(.*)$/.exec(line);
      if (item) {
        if (!inList) { html += "<ul>"; inList = true; }
        html += "<li>" + inline(item[1]) + "</li>";
        return;
      }
      if (inList) { html += "</ul>"; inList = false; }
      if (!line) return;
      var heading = /^#{1,3}\s+(.*)$/.exec(line);
      html += heading
        ? '<p class="md-heading">' + inline(heading[1]) + "</p>"
        : "<p>" + inline(line) + "</p>";
    });
    if (inList) html += "</ul>";
    return html;
  };

  SS.setTheme = function (theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("studysphere-theme", theme); } catch (e) { /* storage blocked */ }
    document.querySelectorAll("[data-set-theme]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", String(btn.dataset.setTheme === theme));
    });
  };

  SS.currentTheme = function () {
    return document.documentElement.getAttribute("data-theme") || "light";
  };

  function wireShell() {
    var sidebarToggle = document.querySelector("[data-sidebar-toggle]");
    var scrim = document.querySelector("[data-sidebar-close]");

    function setNav(open) {
      document.body.classList.toggle("nav-open", open);
      if (scrim) scrim.hidden = !open;
      if (sidebarToggle) sidebarToggle.setAttribute("aria-expanded", String(open));
    }

    if (sidebarToggle) {
      sidebarToggle.addEventListener("click", function () {
        setNav(!document.body.classList.contains("nav-open"));
      });
    }
    if (scrim) scrim.addEventListener("click", function () { setNav(false); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") setNav(false);
    });

    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        SS.setTheme(SS.currentTheme() === "dark" ? "light" : "dark");
      });
    });
    document.querySelectorAll("[data-set-theme]").forEach(function (btn) {
      btn.addEventListener("click", function () { SS.setTheme(btn.dataset.setTheme); });
    });
    SS.setTheme(SS.currentTheme());

    // Forms marked .js-submit (login/register) get a loading state on submit.
    document.querySelectorAll("form.js-submit").forEach(function (form) {
      form.addEventListener("submit", function () {
        var submit = form.querySelector('button[type="submit"]');
        SS.setBusy(submit, true, "Please wait…");
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    SS.icons();
    wireShell();
  });
})();
