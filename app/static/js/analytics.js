(function () {
  "use strict";
  var SS = window.SS;
  var $ = function (id) { return document.getElementById(id); };

  if (!window.Chart) {
    SS.toast("Charts could not load. Check your internet connection.", "error");
    return;
  }

  var charts = [];

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function palette() {
    return {
      accent: cssVar("--accent"),
      accentSoft: cssVar("--accent-soft"),
      success: cssVar("--success"),
      warn: cssVar("--warn"),
      danger: cssVar("--danger-strong"),
      muted: cssVar("--muted"),
      border: cssVar("--border"),
      text: cssVar("--text"),
    };
  }

  function baseOptions(p) {
    Chart.defaults.color = p.muted;
    Chart.defaults.borderColor = p.border;
    Chart.defaults.font.family = "system-ui, -apple-system, Segoe UI, Roboto, sans-serif";
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { usePointStyle: true, boxWidth: 8 } } },
    };
  }

  function draw(id, config) {
    var canvas = $(id);
    var chart = new Chart(canvas, config);
    charts.push(chart);
    return chart;
  }

  function render(data) {
    var p = palette();
    var opts = baseOptions(p);

    // Score trend
    var scores = data.score_history;
    $("scores-empty").hidden = scores.length > 0;
    $("chart-scores").closest(".chart-box").hidden = scores.length === 0;
    if (scores.length) {
      draw("chart-scores", {
        type: "line",
        data: {
          labels: scores.map(function (s) { return s.date; }),
          datasets: [{
            label: "Score %",
            data: scores.map(function (s) { return s.percent; }),
            borderColor: p.accent,
            backgroundColor: p.accentSoft,
            fill: true,
            tension: 0.35,
            pointRadius: 3,
          }],
        },
        options: Object.assign({}, opts, {
          plugins: Object.assign({}, opts.plugins, { legend: { display: false } }),
          scales: { y: { min: 0, max: 100, ticks: { callback: function (v) { return v + "%"; } } } },
        }),
      });
    }

    // Daily activity
    draw("chart-activity", {
      type: "bar",
      data: {
        labels: data.activity_daily.map(function (d) {
          var dt = new Date(d.date + "T00:00:00");
          return dt.toLocaleDateString(undefined, { day: "numeric", month: "short" });
        }),
        datasets: [{
          label: "Actions",
          data: data.activity_daily.map(function (d) { return d.count; }),
          backgroundColor: p.accent,
          borderRadius: 6,
          maxBarThickness: 28,
        }],
      },
      options: Object.assign({}, opts, {
        plugins: Object.assign({}, opts.plugins, { legend: { display: false } }),
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      }),
    });

    // Subject averages
    var subjectsWithScores = data.subjects.filter(function (s) { return s.average_score != null; });
    $("subjects-empty").hidden = subjectsWithScores.length > 0;
    $("chart-subjects").closest(".chart-box").hidden = subjectsWithScores.length === 0;
    if (subjectsWithScores.length) {
      draw("chart-subjects", {
        type: "bar",
        data: {
          labels: subjectsWithScores.map(function (s) { return s.subject; }),
          datasets: [{
            label: "Average score %",
            data: subjectsWithScores.map(function (s) { return s.average_score; }),
            backgroundColor: p.accent,
            borderRadius: 6,
            maxBarThickness: 40,
          }],
        },
        options: Object.assign({}, opts, {
          plugins: Object.assign({}, opts.plugins, { legend: { display: false } }),
          scales: { y: { min: 0, max: 100, ticks: { callback: function (v) { return v + "%"; } } } },
        }),
      });
    }

    // Flashcard mastery
    var fs = data.flashcard_status;
    var cardTotal = fs.unseen + fs.known + fs.revise;
    $("cards-empty").hidden = cardTotal > 0;
    $("chart-cards").closest(".chart-box").hidden = cardTotal === 0;
    if (cardTotal) {
      draw("chart-cards", {
        type: "doughnut",
        data: {
          labels: ["Known", "To revise", "Not yet seen"],
          datasets: [{
            data: [fs.known, fs.revise, fs.unseen],
            backgroundColor: [p.success, p.warn, p.border],
            borderWidth: 0,
          }],
        },
        options: Object.assign({}, opts, { cutout: "68%" }),
      });
    }

    // Subject table
    var tbody = $("subject-table").querySelector("tbody");
    tbody.innerHTML = data.subjects.length
      ? data.subjects.map(function (s) {
          return "<tr><td><strong>" + SS.esc(s.subject) + "</strong></td><td>" + SS.esc(s.documents) +
            "</td><td>" + SS.esc(s.quizzes_taken) + "</td><td>" + SS.esc(SS.percent(s.average_score)) +
            "</td><td>" + SS.esc(s.flashcards_known) + " / " + SS.esc(s.flashcards_total) + "</td></tr>";
        }).join("")
      : '<tr><td colspan="5" class="muted">No subjects yet. Upload a document to begin.</td></tr>';
  }

  SS.api("/api/analytics")
    .then(render)
    .catch(function (err) {
      SS.toast(err.message, "error");
      $("subject-table").querySelector("tbody").innerHTML = '<tr><td colspan="5" class="muted">' + SS.esc(err.message) + "</td></tr>";
    });

  // Re-theme charts when the user toggles dark mode.
  new MutationObserver(function () {
    if (!charts.length) return;
    charts.forEach(function (c) { c.destroy(); });
    charts = [];
    SS.api("/api/analytics").then(render).catch(function () { /* already reported on load */ });
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
})();
