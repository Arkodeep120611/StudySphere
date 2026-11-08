(function () {
  "use strict";
  var SS = window.SS;
  var $ = function (id) { return document.getElementById(id); };

  var KIND = {
    upload: { icon: "upload", label: "Upload" },
    quiz: { icon: "list-checks", label: "Quiz" },
    flashcards: { icon: "layers", label: "Flashcards" },
    chat: { icon: "bot", label: "Assistant" },
  };

  function statCard(label, value, sub) {
    return (
      '<div class="card stat"><div class="stat-label">' + SS.esc(label) + '</div>' +
      '<div class="stat-value">' + SS.esc(value) + '</div>' +
      '<div class="stat-sub">' + SS.esc(sub) + "</div></div>"
    );
  }

  function render(data) {
    var s = data.stats;
    $("stat-grid").innerHTML = [
      statCard("Documents", s.documents, s.documents === 1 ? "file uploaded" : "files uploaded"),
      statCard("Quizzes completed", s.quizzes_completed, s.active_days_7d + " active day(s) this week"),
      statCard("Average score", SS.percent(s.average_score), "across all quiz attempts"),
      statCard("Flashcards known", s.flashcards_known + " / " + s.flashcards_total, "cards marked as known"),
    ].join("");

    $("activity-summary").textContent = s.activity_7d + " actions in 7 days";
    $("activity").innerHTML = data.recent_activity.length
      ? data.recent_activity.map(function (a) {
          var kind = KIND[a.kind] || { icon: "circle", label: "Activity" };
          var score = a.score == null ? "" : '<span class="badge badge-accent">' + SS.esc(Math.round(a.score)) + "%</span>";
          return (
            '<div class="list-item"><span class="dot-icon"><i data-lucide="' + kind.icon + '"></i></span>' +
            '<div class="list-item-main"><div class="list-item-title truncate">' + SS.esc(a.title) + "</div>" +
            '<div class="list-item-meta">' + SS.esc(kind.label) + " · " + SS.esc(SS.formatDateTime(a.created_at)) + "</div></div>" +
            score + "</div>"
          );
        }).join("")
      : SS.empty("activity", "No activity yet", "Upload a document to start studying.");

    $("recent-docs").innerHTML = data.recent_documents.length
      ? data.recent_documents.map(function (d) {
          return (
            '<a class="list-item" href="/documents/' + d.id + '"><span class="dot-icon"><i data-lucide="file-text"></i></span>' +
            '<div class="list-item-main"><div class="list-item-title truncate">' + SS.esc(d.title) + "</div>" +
            '<div class="list-item-meta">' + SS.esc(d.subject) + " · " + SS.esc(SS.formatDate(d.created_at)) + "</div></div></a>"
          );
        }).join("")
      : SS.empty("file-up", "No documents yet", "Upload PDF, TXT or DOCX notes to begin.");

    SS.icons();
  }

  SS.api("/api/dashboard")
    .then(render)
    .catch(function (err) {
      var msg = err.message || "Could not load your dashboard.";
      $("activity").innerHTML = SS.errorBox(msg);
      $("recent-docs").innerHTML = SS.errorBox(msg);
      $("stat-grid").innerHTML = "";
      SS.toast(msg, "error");
      SS.icons();
    });
})();
