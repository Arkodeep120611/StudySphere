(function () {
  "use strict";
  var SS = window.SS;
  var form = document.getElementById("doc-edit-form");
  var deleteBtn = document.getElementById("doc-delete");
  if (!form) return;

  var docId = form.dataset.docId;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var data = new FormData(form);
    var button = form.querySelector('button[type="submit"]');
    SS.setBusy(button, true, "Saving…");
    SS.api("/api/documents/" + docId, {
      method: "PATCH",
      body: { title: data.get("title"), subject: data.get("subject") },
    })
      .then(function (doc) {
        document.querySelectorAll(".topbar-title, title").forEach(function (el) {
          el.textContent = el.tagName === "TITLE" ? doc.title + " · StudySphere" : doc.title;
        });
        SS.toast("Changes saved.");
      })
      .catch(function (err) { SS.toast(err.message, "error"); })
      .finally(function () { SS.setBusy(button, false); });
  });

  deleteBtn.addEventListener("click", function () {
    if (!window.confirm("Delete this document? Its quizzes, flashcards and chat history will also be removed.")) return;
    deleteBtn.disabled = true;
    SS.api("/api/documents/" + docId, { method: "DELETE" })
      .then(function () {
        window.location.href = "/documents";
      })
      .catch(function (err) {
        deleteBtn.disabled = false;
        SS.toast(err.message, "error");
      });
  });
})();
