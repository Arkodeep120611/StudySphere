(function () {
  "use strict";
  var SS = window.SS;
  var $ = function (id) { return document.getElementById(id); };

  var form = $("upload-form");
  var fileInput = $("file-input");
  var dropzone = $("dropzone");
  var list = $("doc-list");
  var search = $("doc-search");
  var searchTimer = null;
  var requestId = 0;

  function renderList(docs, term) {
    if (!docs.length) {
      list.innerHTML = term
        ? SS.empty("search-x", "No matches", "Try a different word or clear the search.")
        : SS.empty("file-up", "No documents yet", "Upload your first set of notes above.");
      SS.icons();
      return;
    }
    list.innerHTML = docs.map(function (d) {
      var snippet = d.snippet
        ? '<p class="doc-snippet">' + highlight(d.snippet, term) + "</p>"
        : "";
      return (
        '<article class="doc-card">' +
        '<div class="doc-card-top"><span class="dot-icon"><i data-lucide="file-text"></i></span>' +
        '<div style="min-width:0;flex:1"><a class="doc-title" href="/documents/' + d.id + '">' + SS.esc(d.title) + "</a>" +
        '<div class="list-item-meta">' + SS.esc(d.subject) + "</div></div></div>" +
        snippet +
        '<div class="doc-card-foot">' +
        '<span class="badge">' + SS.esc(d.file_type.toUpperCase()) + " · " + SS.esc(Number(d.char_count).toLocaleString()) + " chars</span>" +
        '<div class="form-actions">' +
        '<a class="btn btn-ghost btn-sm" href="/documents/' + d.id + '">Open</a>' +
        '<button class="btn btn-ghost btn-sm btn-danger" type="button" data-delete="' + d.id + '" data-title="' + SS.esc(d.title) + '" aria-label="Delete ' + SS.esc(d.title) + '"><i data-lucide="trash-2"></i></button>' +
        "</div></div></article>"
      );
    }).join("");
    SS.icons();
  }

  // Wrap case-insensitive matches of the search term in <mark>. Input is escaped first.
  function highlight(text, term) {
    var escaped = SS.esc(text);
    if (!term) return escaped;
    var safe = SS.esc(term).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return escaped.replace(new RegExp("(" + safe + ")", "ig"), "<mark>$1</mark>");
  }

  function load(term) {
    var id = ++requestId;
    var url = "/api/documents" + (term ? "?q=" + encodeURIComponent(term) : "");
    return SS.api(url).then(function (docs) {
      if (id === requestId) renderList(docs, term);
    }).catch(function (err) {
      if (id === requestId) list.innerHTML = SS.errorBox(err.message);
      SS.icons();
    });
  }

  function setFile(file) {
    if (!file) {
      $("file-name").textContent = "No file selected";
      return;
    }
    $("file-name").textContent = file.name + " (" + Math.max(1, Math.round(file.size / 1024)) + " KB)";
  }

  fileInput.addEventListener("change", function () { setFile(fileInput.files[0]); });

  ["dragenter", "dragover"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) { e.preventDefault(); dropzone.classList.add("is-over"); });
  });
  ["dragleave", "drop"].forEach(function (evt) {
    dropzone.addEventListener(evt, function (e) { e.preventDefault(); dropzone.classList.remove("is-over"); });
  });
  dropzone.addEventListener("drop", function (e) {
    var file = e.dataTransfer && e.dataTransfer.files[0];
    if (file) {
      fileInput.files = e.dataTransfer.files;
      setFile(file);
    }
  });

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var file = fileInput.files[0];
    if (!file) {
      SS.toast("Choose a file to upload.", "error");
      return;
    }
    var button = $("upload-btn");
    var data = new FormData(form);
    SS.setBusy(button, true, "Extracting text…");
    SS.api("/api/documents", { method: "POST", formData: data })
      .then(function (doc) {
        SS.toast('"' + doc.title + '" uploaded. ' + Number(doc.char_count).toLocaleString() + " characters extracted.");
        form.reset();
        setFile(null);
        return load(search.value.trim());
      })
      .catch(function (err) { SS.toast(err.message, "error"); })
      .finally(function () { SS.setBusy(button, false); });
  });

  list.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-delete]");
    if (!btn) return;
    var title = btn.dataset.title;
    if (!window.confirm('Delete "' + title + '"? Its quizzes, flashcards and chat history will also be removed.')) return;
    btn.disabled = true;
    SS.api("/api/documents/" + btn.dataset.delete, { method: "DELETE" })
      .then(function () {
        SS.toast("Document deleted.");
        return load(search.value.trim());
      })
      .catch(function (err) {
        btn.disabled = false;
        SS.toast(err.message, "error");
      });
  });

  search.addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () { load(search.value.trim()); }, 280);
  });

  load("");
})();
