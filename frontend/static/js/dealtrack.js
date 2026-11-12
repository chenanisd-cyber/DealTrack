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

  // -- Photo d'offre introuvable : on la retire, la vignette du marchand
  //    dessinée dessous apparaît. (Écouteur ici plutôt qu'un attribut onerror :
  //    la Content-Security-Policy du site interdit tout script en ligne.)
  // « error » ne remonte pas dans le document : il faut l'écouter en capture.
  document.addEventListener("error", function (event) {
    var img = event.target;
    if (img.matches && img.matches(".dealmedia__photo")) img.remove();
  }, true);
  // Photos déjà en échec avant le chargement de ce script.
  document.querySelectorAll(".dealmedia__photo").forEach(function (img) {
    if (img.complete && img.naturalWidth === 0) img.remove();
  });

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

  // -- Galerie de la page du deal : une vignette remplace la photo principale
  document.addEventListener("click", function (event) {
    var thumb = event.target.closest("[data-photo]");
    if (!thumb) return;
    var main = document.querySelector(".detail__gallery .dealmedia__photo");
    if (main) main.src = thumb.dataset.photo;
    thumb.parentElement.querySelectorAll("[data-photo]").forEach(function (b) {
      b.setAttribute("aria-pressed", String(b === thumb));
    });
  });

  // -- VIP : comparaison en direct (Amazon.com.be), chargée après la page ------
  var live = document.querySelector("[data-compare-url]");
  if (live) {
    fetch(live.dataset.compareUrl, { credentials: "same-origin", cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : { amazon: [] }; })
      .then(function (data) {
        var status = live.querySelector("[data-compare-status]");
        var list = live.querySelector("[data-compare-list]");
        var offers = data.amazon || [];
        if (!offers.length) { status.textContent = status.dataset.empty || "Amazon.com.be : aucun résultat."; return; }
        status.hidden = true;
        offers.forEach(function (offer) {
          var li = document.createElement("li");
          var a = document.createElement("a");
          a.href = offer.url; a.target = "_blank"; a.rel = "noopener nofollow";
          a.textContent = offer.title;
          var price = document.createElement("strong");
          price.textContent = " " + offer.price.replace(".", ",") + " € ";
          var site = document.createElement("span");
          site.className = "meta"; site.textContent = "Amazon.com.be";
          li.appendChild(site); li.appendChild(price); li.appendChild(a);
          list.appendChild(li);
        });
        list.hidden = false;
      })
      .catch(function () {});
  }

  // Le bouton « Partager » natif n'apparaît que si le navigateur le permet.
  if (navigator.share) {
    document.querySelectorAll('[data-share="native"]').forEach(function (b) { b.hidden = false; });
  }
  // -- Application installable (PWA) ---------------------------------------
  // Le service worker affiche une page d'attente quand il n'y a pas de
  // connexion. Sans lui (vieux navigateur), le site marche comme avant.
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }
  // Chrome et Edge sur Android signalent quand l'installation est possible :
  // on propose alors un bandeau discret, une seule fois par appareil.
  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    var bar = document.querySelector("[data-install]");
    try { if (!bar || localStorage.getItem("dt-install-dismissed")) return; } catch (e) { return; }
    bar.hidden = false;
    bar.querySelector("[data-install-yes]").addEventListener("click", function () {
      bar.hidden = true;
      event.prompt();
    });
    bar.querySelector("[data-install-no]").addEventListener("click", function () {
      bar.hidden = true;
      try { localStorage.setItem("dt-install-dismissed", "1"); } catch (e) {}
    });
  });
})();
