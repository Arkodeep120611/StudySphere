(function () {
  "use strict";
  var SS = window.SS;
  var $ = function (id) { return document.getElementById(id); };

  var form = $("quiz-form");
  var docSelect = $("doc-select");
  var list = $("quiz-list");
  var status = $("quiz-status");
  var button = $("quiz-btn");

  var DIFFICULTY = { easy: "Easy", medium: "Medium", hard: "Hard" };
  var TYPES = { mcq: "Multiple choice", true_false: "True / False", mixed: "Mixed" };

  function loadDocuments() {
    return SS.api("/api/documents").then(function (docs) {
      if (!docs.length) {
        docSelect.innerHTML = '<option value="">No documents yet — upload one first</option>';
        docSelect.disabled = true;
        button.disabled = true;
        return;
      }
      docSelect.disabled = false;
      button.disabled = false;
      docSelect.innerHTML = '<option value="">Select a document…</option>' + docs.map(function (d) {
        return '<option value="' + d.id + '">' + SS.esc(d.title) + " (" + SS.esc(d.subject) + ")</option>";
      }).join("");
      var preselect = parseInt(docSelect.dataset.preselect, 10);
      if (preselect && docs.some(function (d) { return d.id === preselect; })) {
        docSelect.value = String(preselect);
      }
    }).catch(function (err) {
      docSelect.innerHTML = '<option value="">Could not load documents</option>';
      SS.toast(err.message, "error");
    });
  }

  function loadQuizzes() {
    return SS.api("/api/quizzes").then(function (quizzes) {
      if (!quizzes.length) {
        list.innerHTML = SS.empty("list-checks", "No quizzes yet", "Generate one from a document to start practising.");
      } else {
        list.innerHTML = quizzes.map(function (q) {
          var best = q.best_percent == null ? '<span class="badge">Not attempted</span>' : '<span class="badge badge-accent">Best ' + SS.esc(Math.round(q.best_percent)) + "%</span>";
          return (
            '<div class="list-item"><span class="dot-icon"><i data-lucide="list-checks"></i></span>' +
            '<div class="list-item-main"><a class="list-item-title truncate" href="/quizzes/' + q.id + '">' + SS.esc(q.title) + "</a>" +
            '<div class="list-item-meta">' + SS.esc(q.question_count) + " questions · " + SS.esc(DIFFICULTY[q.difficulty] || q.difficulty) +
            " · " + SS.esc(TYPES[q.question_type] || q.question_type) + " · " + SS.esc(SS.formatDate(q.created_at)) + "</div></div>" +
            best +
            '<button class="btn btn-ghost btn-sm btn-danger" type="button" data-delete="' + q.id + '" data-title="' + SS.esc(q.title) + '" aria-label="Delete quiz"><i data-lucide="trash-2"></i></button>' +
            "</div>"
          );
        }).join("");
      }
      SS.icons();
    }).catch(function (err) {
      list.innerHTML = SS.errorBox(err.message);
      SS.icons();
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var data = new FormData(form);
    var documentId = parseInt(data.get("document_id"), 10);
    if (!documentId) {
      SS.toast("Choose a source document first.", "error");
      return;
    }
    var payload = {
      document_id: documentId,
      difficulty: data.get("difficulty"),
      question_type: data.get("question_type"),
      count: parseInt(data.get("count"), 10),
    };
    SS.setBusy(button, true, "Generating…");
    status.textContent = "Reading your notes and writing questions. This can take 10–20 seconds.";
    SS.api("/api/quizzes", { method: "POST", body: payload })
      .then(function (quiz) {
        SS.toast("Quiz ready with " + quiz.questions.length + " questions.");
        window.location.href = "/quizzes/" + quiz.id;
      })
      .catch(function (err) {
        SS.toast(err.message, "error");
        status.textContent = "";
      })
      .finally(function () { SS.setBusy(button, false); });
  });

  list.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-delete]");
    if (!btn) return;
    if (!window.confirm('Delete the quiz "' + btn.dataset.title + '" and its attempt history?')) return;
    btn.disabled = true;
    SS.api("/api/quizzes/" + btn.dataset.delete, { method: "DELETE" })
      .then(function () { SS.toast("Quiz deleted."); return loadQuizzes(); })
      .catch(function (err) { btn.disabled = false; SS.toast(err.message, "error"); });
  });

  loadDocuments();
  loadQuizzes();
})();
