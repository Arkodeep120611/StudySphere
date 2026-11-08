(function () {
  "use strict";
  var SS = window.SS;
  var $ = function (id) { return document.getElementById(id); };

  var select = $("doc-select");
  var log = $("chat-log");
  var empty = $("chat-empty");
  var form = $("chat-form");
  var input = $("chat-text");
  var send = $("chat-send");
  var quick = $("quick-actions");
  var clearBtn = $("clear-chat");
  var sending = false;

  function setEnabled(enabled) {
    input.disabled = !enabled;
    send.disabled = !enabled;
    quick.hidden = !enabled;
    clearBtn.hidden = !enabled;
    quick.querySelectorAll("button").forEach(function (b) { b.disabled = !enabled; });
  }

  function bubble(role, content) {
    var el = document.createElement("div");
    el.className = "bubble " + (role === "user" ? "bubble-user" : "bubble-assistant");
    if (role === "user") el.textContent = content;
    else el.innerHTML = SS.markdown(content);
    return el;
  }

  function scrollDown() { log.scrollTop = log.scrollHeight; }

  function showMessages(messages) {
    log.innerHTML = "";
    if (!messages.length) {
      log.appendChild(emptyState());
      return;
    }
    messages.forEach(function (m) { log.appendChild(bubble(m.role, m.content)); });
    scrollDown();
  }

  function emptyState() {
    var wrap = document.createElement("div");
    wrap.className = "empty";
    wrap.innerHTML = '<i data-lucide="message-square"></i><h3>Ask about this document</h3>' +
      '<p class="muted">Answers come only from the selected document. If something is not covered, the assistant will tell you.</p>';
    SS.icons();
    return wrap;
  }

  function currentDocId() {
    return parseInt(select.value, 10) || null;
  }

  function loadDocuments() {
    return SS.api("/api/documents").then(function (docs) {
      if (!docs.length) {
        select.innerHTML = '<option value="">No documents yet — upload one first</option>';
        select.disabled = true;
        showMessages([]);
        return;
      }
      select.innerHTML = '<option value="">Select a document…</option>' + docs.map(function (d) {
        return '<option value="' + d.id + '">' + SS.esc(d.title) + "</option>";
      }).join("");
      var preselect = parseInt(select.dataset.preselect, 10);
      if (preselect && docs.some(function (d) { return d.id === preselect; })) {
        select.value = String(preselect);
      }
      return onDocumentChange();
    }).catch(function (err) {
      select.innerHTML = '<option value="">Could not load documents</option>';
      SS.toast(err.message, "error");
    });
  }

  function onDocumentChange() {
    var docId = currentDocId();
    setEnabled(!!docId);
    if (!docId) {
      showMessages([]);
      return Promise.resolve();
    }
    log.innerHTML = '<div class="skeleton skeleton-line" style="width:60%"></div><div class="skeleton skeleton-line" style="width:40%"></div>';
    return SS.api("/api/documents/" + docId + "/chat").then(showMessages).catch(function (err) {
      log.innerHTML = SS.errorBox(err.message);
      SS.icons();
    });
  }

  function ask(message) {
    var docId = currentDocId();
    if (!docId || sending || !message.trim()) return;
    sending = true;
    setEnabled(true);
    send.disabled = true;
    input.disabled = true;
    empty.hidden = true;
    var emptyNode = log.querySelector(".empty");
    if (emptyNode) emptyNode.remove();

    log.appendChild(bubble("user", message));
    var typing = document.createElement("div");
    typing.className = "bubble bubble-assistant bubble-typing";
    typing.setAttribute("aria-label", "Assistant is thinking");
    typing.innerHTML = "<span></span><span></span><span></span>";
    log.appendChild(typing);
    scrollDown();

    SS.api("/api/documents/" + docId + "/chat", { method: "POST", body: { message: message } })
      .then(function (data) {
        typing.replaceWith(bubble("assistant", data.assistant.content));
        input.value = "";
        scrollDown();
      })
      .catch(function (err) {
        typing.remove();
        log.appendChild(bubble("assistant", "I couldn't answer that just now. " + err.message));
        SS.toast(err.message, "error");
        scrollDown();
      })
      .finally(function () {
        sending = false;
        input.disabled = false;
        send.disabled = false;
        input.focus();
      });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    ask(input.value.trim());
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  quick.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-prompt]");
    if (btn) ask(btn.dataset.prompt);
  });

  clearBtn.addEventListener("click", function () {
    var docId = currentDocId();
    if (!docId || !window.confirm("Clear the chat history for this document?")) return;
    SS.api("/api/documents/" + docId + "/chat", { method: "DELETE" })
      .then(function () { showMessages([]); SS.toast("Chat cleared."); })
      .catch(function (err) { SS.toast(err.message, "error"); });
  });

  select.addEventListener("change", onDocumentChange);

  loadDocuments();
})();
