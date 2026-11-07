/*
 * DealTrack.be — interactions sans rechargement de page.
 *
 * Amélioration progressive : chaque fonctionnalité marche déjà sans
 * JavaScript (formulaires classiques, liens). Ce script ne fait que la rendre
 * plus vivante. Aucune donnée n'est construite avec innerHTML : les textes
 * venant du serveur passent par textContent (pas de XSS possible).
 */
(function () {
  "use strict";

  function csrfToken(form) {
    var field = form.querySelector("[name=csrfmiddlewaretoken]");
    return field ? field.value : "";
  }

  // -- Votes : la température change instantanément ------------------------
  function setTemperature(form, temperature, userVote) {
    var temp = form.querySelector(".vote__temp");
    if (temp) {
      temp.textContent = temperature + "°";
      temp.classList.toggle("is-cold", temperature < 0);
      temp.classList.remove("is-bump");
      void temp.offsetWidth; // relance l'animation
      temp.classList.add("is-bump");
    }
    form.querySelectorAll(".vote__btn").forEach(function (button) {
      button.setAttribute("aria-pressed", String(Number(button.value) === userVote));
    });
    // Toutes les copies de ce deal sur la page (carte, colonne « Les plus hot »)
    var slug = form.dataset.slug;
    if (slug) {
      document.querySelectorAll('[data-temp-for="' + slug + '"]').forEach(function (el) {
        el.textContent = temperature + "°";
      });
    }
  }

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!form.matches(".vote")) return;
    var button = event.submitter;
    if (!button || !button.value) return; // laisse le navigateur faire

    if (document.body.dataset.authenticated !== "1") {
      // Visiteur non connecté : direction la page de connexion, puis retour ici.
      event.preventDefault();
      window.location.href =
        document.body.dataset.loginUrl + "?next=" + encodeURIComponent(window.location.pathname);
      return;
    }

    event.preventDefault();
    var data = new FormData(form);
    data.set("value", button.value);
    form.classList.add("is-busy");

    fetch(form.action, {
      method: "POST",
      body: data,
      headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrfToken(form) },
      credentials: "same-origin",
    })
      .then(function (response) {
        if (!response.ok) throw new Error(response.status);
        return response.json();
      })
      .then(function (json) {
        setTemperature(form, json.temperature, json.user_vote);
      })
      .catch(function () {
        form.submit(); // repli : envoi classique du formulaire
      })
      .finally(function () {
        form.classList.remove("is-busy");
      });
  });

  // -- Partage : WhatsApp, menu de partage du téléphone, copie du lien ------
  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-share]");
    if (!button) return;
    var url = button.dataset.url || window.location.href;
    var title = button.dataset.title || document.title;

    if (button.dataset.share === "native" && navigator.share) {
      event.preventDefault();
      navigator.share({ title: title, url: url }).catch(function () {});
    } else if (button.dataset.share === "copy") {
      event.preventDefault();
      navigator.clipboard.writeText(url).then(function () {
        var label = button.querySelector("span") || button;
        var original = label.textContent;
        label.textContent = button.dataset.copied || "OK";
        setTimeout(function () { label.textContent = original; }, 2000);
      });
    }
    // data-share="whatsapp" : simple lien https://wa.me/?text=…, rien à faire.
  });

  // Le bouton « Partager » natif n'apparaît que si le navigateur le permet.
  if (navigator.share) {
    document.querySelectorAll('[data-share="native"]').forEach(function (b) { b.hidden = false; });
  }
})();
