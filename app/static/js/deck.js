(function () {
  "use strict";
  var SS = window.SS;
  var root = document.getElementById("deck-root");
  if (!root) return;

  var deckId = root.dataset.deckId;
  var deck = null;
  var filter = "all";
  var index = 0;
  var flipped = false;
  var busy = false;

  function visibleCards() {
    if (filter === "all") return deck.cards;
    return deck.cards.filter(function (c) { return c.status === filter; });
  }

  function statusBadge(status) {
    if (status === "known") return '<span class="badge badge-success status-pill">Known</span>';
    if (status === "revise") return '<span class="badge badge-warn status-pill">Revise</span>';
    return '<span class="badge status-pill">New</span>';
  }

  function render() {
    var cards = visibleCards();
    var known = deck.cards.filter(function (c) { return c.status === "known"; }).length;
    var total = deck.cards.length;
    var percent = total ? Math.round((known / total) * 100) : 0;

    var stage;
    if (!cards.length) {
      stage = SS.empty(
        "party-popper",
        filter === "revise" ? "Nothing to revise" : "No cards in this view",
        filter === "revise" ? "Mark cards as Revise to review them here." : "Try a different filter."
      );
    } else {
      if (index >= cards.length) index = 0;
      var card = cards[index];
      stage =
        '<div class="flip-scene"><button class="flip-card' + (flipped ? " is-flipped" : "") + '" type="button" id="flip" aria-label="Flip card">' +
        '<div class="flip-face"><span class="face-label">Question</span>' + SS.esc(card.question) + '<span class="flip-hint">Click or press Space to flip</span></div>' +
        '<div class="flip-face flip-face-back"><span class="face-label">Answer</span>' + SS.esc(card.answer) + "</div>" +
        "</button></div>" +
        '<div class="muted small">Card ' + (index + 1) + " of " + cards.length + " · " + statusBadge(card.status) + "</div>" +
        '<div class="card-controls">' +
        '<button class="btn" type="button" id="prev" aria-label="Previous card"><i data-lucide="chevron-left"></i><span>Previous</span></button>' +
        '<button class="btn btn-danger" type="button" id="revise"><i data-lucide="rotate-ccw"></i><span>Revise</span></button>' +
        '<button class="btn btn-primary" type="button" id="known"><i data-lucide="check"></i><span>Known</span></button>' +
        '<button class="btn" type="button" id="next" aria-label="Next card"><i data-lucide="chevron-right"></i><span>Next</span></button>' +
        "</div>";
    }

    root.innerHTML =
      '<div class="card deck-toolbar">' +
      '<div><div class="muted small">' + known + " of " + total + " known</div>" +
      '<div class="progress" style="width:min(320px,70vw);margin-top:6px"><div class="progress-bar" style="width:' + percent + '%"></div></div></div>' +
      '<div class="form-actions">' +
      '<select class="input select" id="filter" aria-label="Filter cards" style="width:auto">' +
      '<option value="all"' + (filter === "all" ? " selected" : "") + ">All cards</option>" +
      '<option value="revise"' + (filter === "revise" ? " selected" : "") + ">To revise</option>" +
      '<option value="unseen"' + (filter === "unseen" ? " selected" : "") + ">Not yet seen</option>" +
      '<option value="known"' + (filter === "known" ? " selected" : "") + ">Known</option>" +
      "</select>" +
      '<button class="btn btn-sm" type="button" id="reset"><i data-lucide="rotate-ccw"></i><span>Reset progress</span></button>' +
      "</div></div>" +
      '<div class="deck-stage">' + stage + "</div>" +
      '<p class="muted small" style="text-align:center">Shortcuts: ← → to move · Space to flip · K known · R revise</p>';
    SS.icons();
  }

  function setStatus(card, status) {
    if (busy) return;
    busy = true;
    SS.api("/api/cards/" + card.id, { method: "PATCH", body: { status: status } })
      .then(function (updated) {
        card.status = updated.status;
        if (filter !== "all" && card.status !== filter) {
          // Card left the current filter; keep the index on the next card in view.
          flipped = false;
        } else {
          index = Math.min(index + 1, Math.max(0, visibleCards().length - 1));
          flipped = false;
        }
        render();
      })
      .catch(function (err) { SS.toast(err.message, "error"); })
      .finally(function () { busy = false; });
  }

  function move(delta) {
    var cards = visibleCards();
    if (!cards.length) return;
    index = (index + delta + cards.length) % cards.length;
    flipped = false;
    render();
  }

  function currentCard() {
    var cards = visibleCards();
    return cards.length ? cards[index % cards.length] : null;
  }

  function load() {
    return SS.api("/api/decks/" + deckId).then(function (data) {
      deck = data;
      document.title = deck.title + " · StudySphere";
      render();
    }).catch(function (err) {
      root.innerHTML = SS.errorBox(err.message);
      SS.icons();
    });
  }

  root.addEventListener("click", function (e) {
    var target = e.target.closest("button, select");
    if (!target) return;
    if (target.id === "flip") { flipped = !flipped; render(); }
    else if (target.id === "prev") move(-1);
    else if (target.id === "next") move(1);
    else if (target.id === "known" && currentCard()) setStatus(currentCard(), "known");
    else if (target.id === "revise" && currentCard()) setStatus(currentCard(), "revise");
    else if (target.id === "reset") {
      SS.api("/api/decks/" + deckId + "/reset", { method: "POST" })
        .then(function (data) {
          deck = data;
          index = 0;
          flipped = false;
          SS.toast("Progress reset.");
          render();
        })
        .catch(function (err) { SS.toast(err.message, "error"); });
    }
  });

  root.addEventListener("change", function (e) {
    if (e.target.id === "filter") {
      filter = e.target.value;
      index = 0;
      flipped = false;
      render();
    }
  });

  document.addEventListener("keydown", function (e) {
    if (!deck || e.target.closest("input, textarea, select") || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "ArrowRight") { e.preventDefault(); move(1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); move(-1); }
    else if (e.key === " ") { e.preventDefault(); flipped = !flipped; render(); }
    else if (e.key === "k" || e.key === "K") { if (currentCard()) setStatus(currentCard(), "known"); }
    else if (e.key === "r" || e.key === "R") { if (currentCard()) setStatus(currentCard(), "revise"); }
  });

  load();
})();
