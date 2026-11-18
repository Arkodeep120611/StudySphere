/* Passkeys (WebAuthn).
 * On the login page, "Log in with a passkey" signs the user in without a password.
 * On the Settings page, the Passkeys card lists, adds and removes passkeys.
 * The server creates and checks every challenge; the browser only passes data between the
 * server and navigator.credentials. Both parts are hidden unless the browser supports passkeys.
 */
(function () {
  "use strict";

  var SS = window.SS;
  var supported = !!(window.PublicKeyCredential && navigator.credentials);
  var csrfMeta = document.querySelector('meta[name="csrf-token"]');

  // ---------- encoding helpers (WebAuthn uses base64url strings on the wire) ----------

  function decode(value) {
    var base64 = value.replace(/-/g, "+").replace(/_/g, "/");
    base64 += "=".repeat((4 - (base64.length % 4)) % 4);
    var raw = atob(base64);
    var bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    return bytes.buffer;
  }

  function encode(buffer) {
    var bytes = new Uint8Array(buffer);
    var text = "";
    for (var i = 0; i < bytes.length; i++) text += String.fromCharCode(bytes[i]);
    return btoa(text).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function encodeCredential(credential) {
    var response = credential.response;
    var out = {
      id: credential.id,
      rawId: encode(credential.rawId),
      type: credential.type,
      clientExtensionResults: credential.getClientExtensionResults ? credential.getClientExtensionResults() : {},
      response: { clientDataJSON: encode(response.clientDataJSON) }
    };
    if (response.attestationObject) {
      out.response.attestationObject = encode(response.attestationObject);
      out.response.transports = response.getTransports ? response.getTransports() : [];
    } else {
      out.response.authenticatorData = encode(response.authenticatorData);
      out.response.signature = encode(response.signature);
      out.response.userHandle = response.userHandle ? encode(response.userHandle) : null;
    }
    return out;
  }

  // ---------- requests ----------

  // Uses fetch directly rather than SS.api, because SS.api redirects to /login on 401 and
  // the login page must show the error instead.
  function post(url, body) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRFToken": csrfMeta ? csrfMeta.content : ""
      },
      body: JSON.stringify(body || {})
    }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) throw new Error(data.error || "Request failed (" + res.status + ").");
        return data;
      });
    }, function () {
      throw new Error("Network error. Check your connection and try again.");
    });
  }

  function cancelled(err) {
    if (err && err.name === "NotAllowedError") {
      return new Error("Passkey request was cancelled or timed out.");
    }
    return err;
  }

  // ---------- login ----------

  var loginButton = document.getElementById("passkey-login-btn");

  function loginWithPasskey() {
    var remember = document.querySelector('input[name="remember"]');
    var next = loginButton.getAttribute("data-next") || "";
    return post("/auth/passkey/options")
      .then(function (options) {
        options.challenge = decode(options.challenge);
        return navigator.credentials.get({ publicKey: options }).catch(function (err) {
          throw cancelled(err);
        });
      })
      .then(function (credential) {
        if (!credential) throw new Error("Passkey request was cancelled.");
        return post("/auth/passkey/verify", {
          credential: encodeCredential(credential),
          remember: !!(remember && remember.checked),
          next: next
        });
      })
      .then(function (result) {
        window.location.href = result.redirect;
      });
  }

  if (loginButton && supported) {
    loginButton.closest("[data-passkey-login]").hidden = false;
    loginButton.addEventListener("click", function () {
      loginButton.disabled = true;
      loginWithPasskey()
        .catch(function (err) { SS.toast(err.message, "error"); })
        .finally(function () { loginButton.disabled = false; });
    });
  }

  // ---------- settings: manage passkeys ----------

  var card = document.getElementById("passkey-card");

  if (card && supported) {
    var list = document.getElementById("passkey-list");
    var form = document.getElementById("passkey-form");
    card.hidden = false;

    var formatDate = function (iso) {
      return iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "never";
    };

    function render(items) {
      if (!items.length) {
        list.innerHTML = '<p class="muted small">No passkeys yet.</p>';
        return;
      }
      list.innerHTML = items.map(function (item) {
        return '<div class="list-item">' +
          '<div class="list-item-main"><div class="list-item-title">' + SS.esc(item.name) + '</div>' +
          '<div class="list-item-meta">Added ' + formatDate(item.created_at) + ' · last used ' + formatDate(item.last_used_at) + '</div></div>' +
          '<button class="btn btn-ghost btn-sm" type="button" data-delete-passkey="' + item.id + '">Remove</button>' +
          '</div>';
      }).join("");
    }

    function load() {
      return SS.api("/api/account/passkeys").then(render).catch(function (err) { SS.toast(err.message, "error"); });
    }

    function addPasskey(name) {
      return SS.api("/api/account/passkeys/options", { method: "POST", body: {} })
        .then(function (options) {
          options.challenge = decode(options.challenge);
          options.user.id = decode(options.user.id);
          options.excludeCredentials = (options.excludeCredentials || []).map(function (c) {
            return { type: c.type, id: decode(c.id), transports: c.transports };
          });
          return navigator.credentials.create({ publicKey: options }).catch(function (err) {
            throw cancelled(err);
          });
        })
        .then(function (credential) {
          if (!credential) throw new Error("Passkey setup was cancelled.");
          return SS.api("/api/account/passkeys/verify", {
            method: "POST",
            body: { credential: encodeCredential(credential), name: name }
          });
        });
    }

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var button = form.querySelector('button[type="submit"]');
      SS.setBusy(button, true, "Waiting for device…");
      addPasskey(form.name.value.trim())
        .then(function () {
          form.reset();
          SS.toast("Passkey added.");
          return load();
        })
        .catch(function (err) { SS.toast(err.message, "error"); })
        .finally(function () { SS.setBusy(button, false); });
    });

    list.addEventListener("click", function (e) {
      var button = e.target.closest("[data-delete-passkey]");
      if (!button) return;
      if (!window.confirm("Remove this passkey? You can add it again later.")) return;
      SS.api("/api/account/passkeys/" + button.getAttribute("data-delete-passkey"), { method: "DELETE" })
        .then(function () { SS.toast("Passkey removed."); return load(); })
        .catch(function (err) { SS.toast(err.message, "error"); });
    });

    load();
  }
})();
