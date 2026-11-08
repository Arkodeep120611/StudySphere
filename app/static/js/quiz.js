(function () {
  "use strict";
  var SS = window.SS;
  var root = document.getElementById("quiz-root");
  if (!root) return;

  var quizId = root.dataset.quizId;
  var quiz = null;
  var answers = [];
  var submitting = false;

  function letter(i) { return String.fromCharCode(65 + i); }

  function header() {
    var attempts = quiz.attempts.length;
    return (
      '<div class="card quiz-head">' +
      "<div><h2>" + SS.esc(quiz.title) + '</h2><div class="muted small">' +
      SS.esc(quiz.questions.length) + " questions · " + SS.esc(quiz.difficulty) +
      " · from " + SS.esc(quiz.document_title) + "</div></div>" +
      '<span class="badge">' + attempts + " attempt" + (attempts === 1 ? "" : "s") + "</span>" +
      "</div>"
    );
  }

  function questionCard(q, index, opts) {
    // opts: { result, disabled }
    var result = opts.result;
    var selected = result ? result.selected : answers[index];
    var options = q.options.map(function (text, i) {
      var classes = ["option"];
      var checked = selected === i;
      if (opts.disabled) classes.push("is-disabled");
      if (result) {
        if (i === result.correct_index) classes.push("is-correct");
        else if (checked) classes.push("is-wrong");
      } else if (checked) {
        classes.push("selected");
      }
      var input = opts.disabled
        ? '<input type="radio" disabled' + (checked ? " checked" : "") + ">"
        : '<input type="radio" name="q' + index + '" value="' + i + '"' + (checked ? " checked" : "") + ">";
      return '<label class="' + classes.join(" ") + '">' + input +
        '<span><strong>' + letter(i) + ".</strong> " + SS.esc(text) + "</span></label>";
    }).join("");

    var verdict = "";
    if (result) {
      verdict = '<span class="badge ' + (result.is_correct ? "badge-success" : "badge-danger") + '">' +
        (result.is_correct ? "Correct" : "Incorrect") + "</span>";
    }
    var explanation = result && result.explanation
      ? '<div class="explanation"><strong>Why:</strong> ' + SS.esc(result.explanation) + "</div>"
      : "";

    return (
      '<article class="question" data-index="' + index + '">' +
      '<div class="question-title"><span class="question-num">' + (index + 1) + ".</span>" +
      '<span style="flex:1">' + SS.esc(q.question) + "</span>" + verdict + "</div>" +
      '<div class="options">' + options + "</div>" + explanation + "</article>"
    );
  }

  function renderTaking() {
    var answered = answers.filter(function (a) { return a !== undefined && a !== null; }).length;
    var total = quiz.questions.length;
    var percent = total ? Math.round((answered / total) * 100) : 0;

    root.innerHTML =
      header() +
      '<div class="progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + percent + '"><div class="progress-bar" style="width:' + percent + '%"></div></div>' +
      '<div class="question-list">' +
      quiz.questions.map(function (q, i) { return questionCard(q, i, { disabled: false }); }).join("") +
      "</div>" +
      '<div class="sticky-bar"><span class="muted small" id="answer-count">' + answered + " of " + total + " answered</span>" +
      '<div class="form-actions"><button class="btn btn-primary" type="button" id="submit-quiz"' + (answered < total ? " disabled" : "") +
      '><i data-lucide="send"></i><span>Submit answers</span></button></div></div>';
    SS.icons();
  }

  function renderResults(result) {
    var tone = result.percent >= 70 ? "badge-success" : result.percent >= 40 ? "badge-warn" : "badge-danger";
    var message = result.percent >= 80 ? "Excellent work." : result.percent >= 50 ? "Good progress. Review the explanations below." : "Keep going. Review the explanations and try again.";
    root.innerHTML =
      header() +
      '<section class="card score-banner">' +
      '<div class="score-ring">' + Math.round(result.percent) + "%</div>" +
      "<div><h2>" + result.score + " of " + result.total + " correct</h2>" +
      '<p class="muted" style="margin:0"><span class="badge ' + tone + '">' + SS.esc(message) + "</span></p></div>" +
      '<div class="form-actions" style="margin-left:auto"><button class="btn btn-primary" type="button" id="retake"><i data-lucide="rotate-ccw"></i><span>Retake quiz</span></button>' +
      '<a class="btn" href="/quizzes">Back to quizzes</a></div></section>' +
      '<div class="question-list">' +
      result.results.map(function (r, i) { return questionCard(quiz.questions[i], i, { result: r, disabled: true }); }).join("") +
      "</div>";
    SS.icons();
  }

  function load() {
    return SS.api("/api/quizzes/" + quizId).then(function (data) {
      quiz = data;
      answers = quiz.questions.map(function () { return null; });
      document.title = quiz.title + " · StudySphere";
      renderTaking();
    }).catch(function (err) {
      root.innerHTML = SS.errorBox(err.message);
      SS.icons();
    });
  }

  root.addEventListener("change", function (e) {
    var input = e.target;
    if (input.type !== "radio") return;
    var index = parseInt(input.name.slice(1), 10);
    answers[index] = parseInt(input.value, 10);
    renderTaking();
    var first = root.querySelector('input[name="q' + (index + 1) + '"]');
    if (first) first.closest(".question").scrollIntoView({ behavior: "smooth", block: "center" });
  });

  root.addEventListener("click", function (e) {
    if (e.target.closest("#submit-quiz")) {
      if (submitting) return;
      var btn = e.target.closest("#submit-quiz");
      submitting = true;
      SS.setBusy(btn, true, "Scoring…");
      SS.api("/api/quizzes/" + quizId + "/attempts", { method: "POST", body: { answers: answers } })
        .then(function (result) {
          SS.toast("Score saved: " + result.score + "/" + result.total);
          return SS.api("/api/quizzes/" + quizId).then(function (fresh) {
            quiz = fresh;
            renderResults(result);
          });
        })
        .catch(function (err) {
          SS.toast(err.message, "error");
          SS.setBusy(btn, false);
        })
        .finally(function () { submitting = false; });
    } else if (e.target.closest("#retake")) {
      answers = quiz.questions.map(function () { return null; });
      renderTaking();
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });

  load();
})();
