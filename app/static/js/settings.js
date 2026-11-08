(function () {
  "use strict";
  var SS = window.SS;
  var $ = function (id) { return document.getElementById(id); };

  SS.setTheme(SS.currentTheme());

  $("profile-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var form = e.currentTarget;
    var button = form.querySelector('button[type="submit"]');
    SS.setBusy(button, true, "Saving…");
    SS.api("/api/account/profile", { method: "PATCH", body: { name: form.name.value } })
      .then(function (user) {
        document.querySelectorAll(".user-name").forEach(function (el) { el.textContent = user.name; });
        document.querySelectorAll(".avatar").forEach(function (el) { el.textContent = user.name.charAt(0).toUpperCase(); });
        SS.toast("Profile updated.");
      })
      .catch(function (err) { SS.toast(err.message, "error"); })
      .finally(function () { SS.setBusy(button, false); });
  });

  $("password-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var form = e.currentTarget;
    var current = form.current_password.value;
    var next = form.new_password.value;
    if (next !== form.confirm_password.value) {
      SS.toast("New passwords do not match.", "error");
      return;
    }
    var button = form.querySelector('button[type="submit"]');
    SS.setBusy(button, true, "Updating…");
    SS.api("/api/account/password", { method: "POST", body: { current_password: current, new_password: next } })
      .then(function () {
        form.reset();
        SS.toast("Password updated.");
      })
      .catch(function (err) { SS.toast(err.message, "error"); })
      .finally(function () { SS.setBusy(button, false); });
  });
})();
