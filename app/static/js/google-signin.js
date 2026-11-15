/* "Sign in with Google" on the login and register pages.
 * Google Identity Services returns an ID token to this script. It is sent to /auth/google,
 * where the server verifies it and starts the session. If Google's script fails to load, the
 * button stays hidden and the email/password form is still available.
 */
(function () {
  "use strict";

  var container = document.getElementById("google-signin");
  if (!container) return;

  var divider = document.getElementById("google-signin-divider");
  var errorBox = document.getElementById("google-signin-error");
  var errorText = errorBox ? errorBox.querySelector("span") : null;
  var clientId = container.getAttribute("data-client-id");
  var endpoint = container.getAttribute("data-endpoint");
  var nextPath = container.getAttribute("data-next") || "";

  function showError(message) {
    if (!errorBox || !errorText) return;
    errorText.textContent = message;
    errorBox.hidden = false;
  }

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
  }

  function handleCredential(response) {
    if (errorBox) errorBox.hidden = true;
    var remember = document.querySelector('input[name="remember"]');

    fetch(endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRFToken": csrfToken()
      },
      body: JSON.stringify({
        credential: response.credential,
        remember: !!(remember && remember.checked),
        next: nextPath
      })
    })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          return { ok: res.ok, data: data };
        });
      })
      .then(function (result) {
        if (result.ok && result.data.redirect) {
          window.location.href = result.data.redirect;
        } else {
          showError(result.data.error || "Google sign-in failed. Please try again.");
        }
      })
      .catch(function () {
        showError("Network error. Check your connection and try again.");
      });
  }

  function show() {
    container.hidden = false;
    if (divider) divider.hidden = false;
  }

  function init() {
    var gsi = window.google && window.google.accounts && window.google.accounts.id;
    if (!gsi || !clientId) return;

    // Show first so the button is measured at its real width.
    show();
    gsi.initialize({ client_id: clientId, callback: handleCredential });
    gsi.renderButton(container, {
      type: "standard",
      theme: "outline",
      size: "large",
      text: "continue_with",
      shape: "rectangular",
      logo_alignment: "left",
      width: Math.min(400, container.clientWidth || 360)
    });
  }

  init();
})();
