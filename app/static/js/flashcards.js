(function () {
  "use strict";
  var SS = window.SS;
  var $ = function (id) { return document.getElementById(id); };

  var form = $("deck-form");
  var docSelect = $("doc-select");
  var list = $("deck-list");
  var status = $("deck-status");
  var button = $("deck-btn");

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

  function loadDecks() {
    return SS.api("/api/decks").then(function (decks) {
      if (!decks.length) {
        list.innerHTML = SS.empty("layers", "No decks yet", "Generate a deck from one of your documents.");
      } else {
        list.innerHTML = decks.map(function (d) {
          var progress = d.card_count ? Math.round((d.known_count / d.card_count) * 100) : 0;
          return (
            '<div class="list-item"><span class="dot-icon"><i data-lucide="layers"></i></span>' +
            '<div class="list-item-main"><a class="list-item-title truncate" href="/flashcards/' + d.id + '">' + SS.esc(d.title) + "</a>" +
            '<div class="list-item-meta">' + SS.esc(d.card_count) + " cards · " + SS.esc(d.known_count) + " known · " +
            SS.esc(d.revise_count) + " to revise</div>" +
            '<div class="progress" style="margin-top:8px"><div class="progress-bar" style="width:' + progress + '%"></div></div></div>' +
            '<button class="btn btn-ghost btn-sm btn-danger" type="button" data-delete="' + d.id + '" data-title="' + SS.esc(d.title) + '" aria-label="Delete deck"><i data-lucide="trash-2"></i></button>' +
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
    SS.setBusy(button, true, "Generating…");
    status.textContent = "Reading your notes and writing cards. This can take 10–20 seconds.";
    SS.api("/api/decks", {
      method: "POST",
      body: { document_id: documentId, count: parseInt(data.get("count"), 10) },
    })
      .then(function (deck) {
        SS.toast("Deck ready with " + deck.cards.length + " cards.");
        window.location.href = "/flashcards/" + deck.id;
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
    if (!window.confirm('Delete the deck "' + btn.dataset.title + '"?')) return;
    btn.disabled = true;
    SS.api("/api/decks/" + btn.dataset.delete, { method: "DELETE" })
      .then(function () { SS.toast("Deck deleted."); return loadDecks(); })
      .catch(function (err) { btn.disabled = false; SS.toast(err.message, "error"); });
  });

  loadDocuments();
  loadDecks();
})();
