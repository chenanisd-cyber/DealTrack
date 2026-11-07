/*
 * Assistant de publication (templates/deals/submit.html).
 *
 * Les six étapes sont des sections d'UN seul formulaire : ce script les
 * affiche une par une, lit le lien collé, gère la galerie d'images et
 * construit l'aperçu final. Le serveur revalide tout à l'envoi.
 * Aucune donnée n'est insérée avec innerHTML : textContent et createElement
 * uniquement (pas de XSS possible avec un titre ou une adresse piégés).
 */
(function () {
  "use strict";

  var MSG = JSON.parse(document.getElementById("wizard-messages").textContent);
  var SCRAPE_URL = document.currentScript.dataset.scrapeUrl;
  var STEPS = ["link", "essentials", "images", "description", "details", "review"];
  var MAX_IMAGES = 8;

  var form = document.getElementById("deal-form");
  var $ = function (id) { return document.getElementById(id); };
  var field = function (name) { return form.elements[name]; };
  var current = "link";

  document.getElementById("wizard").classList.add("is-js");

  // -- Navigation entre les étapes ------------------------------------------
  function show(step) {
    current = step;
    var index = STEPS.indexOf(step);
    form.querySelectorAll(".wizard__step").forEach(function (section) {
      section.hidden = section.dataset.step !== step;
    });
    document.querySelectorAll("[data-goto]").forEach(function (button) {
      var i = STEPS.indexOf(button.dataset.goto);
      button.classList.toggle("is-current", i === index);
      button.classList.toggle("is-done", i < index);
      button.setAttribute("aria-current", i === index ? "step" : "false");
    });
    $("btn-prev").hidden = index === 0;
    $("btn-next").hidden = index === 0 || index === STEPS.length - 1;
    if (step === "review") buildReview();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  document.querySelectorAll("[data-goto]").forEach(function (button) {
    button.addEventListener("click", function () { show(button.dataset.goto); });
  });
  $("btn-prev").addEventListener("click", function () {
    show(STEPS[Math.max(0, STEPS.indexOf(current) - 1)]);
  });
  $("btn-next").addEventListener("click", function () {
    show(STEPS[Math.min(STEPS.length - 1, STEPS.indexOf(current) + 1)]);
  });

  // -- Étape 1 : lecture du lien --------------------------------------------
  var urlInput = field("external_url");

  function setValue(name, value) {
    var el = field(name);
    if (el && value !== undefined && value !== null && value !== "") el.value = value;
  }

  function fetchLink() {
    var url = urlInput.value.trim();
    $("fetch-error").hidden = true;
    if (!/^https?:\/\/\S+$/i.test(url)) {
      $("fetch-error").textContent = MSG.invalid;
      $("fetch-error").hidden = false;
      return;
    }
    $("fetch-status").hidden = false;
    $("btn-fetch").disabled = true;
    fetch(SCRAPE_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": form.elements.csrfmiddlewaretoken.value,
      },
      body: JSON.stringify({ url: url }),
      credentials: "same-origin",
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.success) {
          applyScrape(data);
          show("essentials");
        } else if (data.error === "unsafe_url") {
          $("fetch-error").textContent = MSG.refused;
          $("fetch-error").hidden = false;
        } else if (data.error === "rate_limited") {
          $("fetch-error").textContent = MSG.tooMany;
          $("fetch-error").hidden = false;
        } else {
          summary(data.error === "blocked" ? MSG.blocked : MSG.failed);
          show("essentials");
        }
      })
      .catch(function () { summary(MSG.failed); show("essentials"); })
      .finally(function () {
        $("fetch-status").hidden = true;
        $("btn-fetch").disabled = false;
      });
  }

  function summary(text) {
    $("fetch-summary").textContent = text;
    $("fetch-summary").hidden = false;
  }

  function applyScrape(data) {
    setValue("title", data.title);
    setValue("price", data.price);
    setValue("reference_price", data.reference_price);
    if (!field("description").value && data.description && data.description.length >= 30) {
      field("description").value = data.description;
    }
    // Images trouvées sur la page : elles remplacent la galerie actuelle.
    urlItems = (data.images || []).slice(0, MAX_IMAGES);
    renderGallery();
    // Marchand : reconnu (liste) ou proposé (nouveau, non vérifié).
    if (data.merchant_id) {
      field("merchant").value = data.merchant_id;
      field("merchant_name").value = "";
      $("merchant-new-note").hidden = true;
    } else {
      field("merchant").value = "";
      field("merchant_name").value = data.merchant_name || "";
      $("merchant-new-note").hidden = !data.merchant_name;
    }
    $("merchant-detected").textContent = data.merchant_name || MSG.merchantUnknown;

    var found = [], missing = [];
    var check = function (ok, key) { (ok ? found : missing).push(MSG.fields[key]); };
    check(data.title, "title");
    check(data.price, "price");
    check(data.reference_price, "reference");
    check((data.images || []).length, "photo");
    check(data.merchant_name, "merchant");
    check(data.description, "description");
    summary(
      MSG.found + " " + (found.join(", ") || "—") + ". " +
      (missing.length ? MSG.missing + " " + missing.join(", ") + ". " : "") + MSG.check
    );
    updateDiscount();
    updateCounters();
  }

  $("btn-fetch").addEventListener("click", fetchLink);
  urlInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") { e.preventDefault(); fetchLink(); }
  });
  urlInput.addEventListener("paste", function () {
    setTimeout(function () { if (/^https?:\/\//i.test(urlInput.value.trim())) fetchLink(); }, 50);
  });
  $("btn-nolink").addEventListener("click", function () {
    var inStore = form.querySelector('[name="availability"][value="in_store"]');
    if (inStore) { inStore.checked = true; toggleAvailability(); }
    form.querySelector(".merchantbox details").open = true;
    show("essentials");
  });

  // -- Étape 2 : réduction, disponibilité, compteurs ------------------------
  function updateDiscount() {
    var price = parseFloat(field("price").value);
    var ref = parseFloat(field("reference_price").value);
    var badge = $("discount-badge");
    var pct = price > 0 && ref > price ? Math.round((1 - price / ref) * 100) : 0;
    badge.textContent = (pct ? "-" : "") + pct + " %";
  }
  field("price").addEventListener("input", updateDiscount);
  field("reference_price").addEventListener("input", updateDiscount);

  function toggleAvailability() {
    var checked = form.querySelector('[name="availability"]:checked');
    var online = !checked || checked.value === "online";
    form.querySelectorAll('[data-show-when="online"]').forEach(function (el) { el.hidden = !online; });
  }
  form.querySelectorAll('[name="availability"]').forEach(function (r) {
    r.addEventListener("change", toggleAvailability);
  });

  function updateCounters() {
    document.querySelectorAll("[data-count-for]").forEach(function (counter) {
      var input = $(counter.dataset.countFor);
      if (input) counter.textContent = input.value.length + " / " + counter.dataset.max;
    });
  }
  document.querySelectorAll("[data-count-for]").forEach(function (counter) {
    var input = $(counter.dataset.countFor);
    if (input) input.addEventListener("input", updateCounters);
  });

  // -- Étape 3 : galerie ----------------------------------------------------
  // Ordre envoyé au serveur : adresses (gallery_urls) puis fichiers ;
  // main_index désigne l'image principale dans cet ordre.
  var urlItems = [];
  var fileInput = field("gallery_files");
  var mainIndex = 0;
  try { urlItems = JSON.parse(field("gallery_urls").value || "[]"); } catch (e) { urlItems = []; }
  mainIndex = parseInt(field("main_index").value || "0", 10) || 0;

  function files() { return fileInput ? Array.prototype.slice.call(fileInput.files) : []; }

  function setFiles(list) {
    var transfer = new DataTransfer();
    list.forEach(function (f) { transfer.items.add(f); });
    fileInput.files = transfer.files;
  }

  function allItems() {
    return urlItems.map(function (u) { return { kind: "url", src: u }; })
      .concat(files().map(function (f) { return { kind: "file", src: URL.createObjectURL(f), file: f }; }));
  }

  function renderGallery() {
    var items = allItems();
    if (mainIndex >= items.length) mainIndex = 0;
    var gallery = $("gallery");
    gallery.textContent = "";
    items.forEach(function (item, index) {
      var tile = document.createElement("div");
      tile.className = "gallery__tile" + (index === mainIndex ? " is-main" : "");
      var img = document.createElement("img");
      img.src = item.src;
      img.alt = "";
      img.referrerPolicy = "no-referrer";
      img.addEventListener("error", function () { tile.classList.add("is-broken"); });
      var pick = document.createElement("button");
      pick.type = "button";
      pick.className = "gallery__pick";
      pick.title = MSG.makeMain;
      pick.appendChild(img);
      pick.addEventListener("click", function () { mainIndex = index; renderGallery(); });
      var remove = document.createElement("button");
      remove.type = "button";
      remove.className = "gallery__remove";
      remove.setAttribute("aria-label", MSG.remove);
      remove.textContent = "×";
      remove.addEventListener("click", function () { removeItem(index); });
      tile.appendChild(pick);
      tile.appendChild(remove);
      if (index === mainIndex) {
        var label = document.createElement("span");
        label.className = "gallery__label";
        label.textContent = MSG.main;
        tile.appendChild(label);
      }
      gallery.appendChild(tile);
    });
    $("gallery-empty").hidden = items.length > 0;
    field("gallery_urls").value = JSON.stringify(urlItems);
    field("main_index").value = String(mainIndex);
  }

  function removeItem(index) {
    if (index < urlItems.length) {
      urlItems.splice(index, 1);
    } else {
      var list = files();
      list.splice(index - urlItems.length, 1);
      setFiles(list);
    }
    if (mainIndex === index) mainIndex = 0;
    else if (mainIndex > index) mainIndex -= 1;
    renderGallery();
  }

  $("btn-add-url").addEventListener("click", function () {
    var input = $("image-url-input");
    var url = input.value.trim();
    if (!/^https:\/\/\S+$/i.test(url)) { alert(MSG.httpsOnly); return; }
    if (allItems().length >= MAX_IMAGES) { alert(MSG.maxImages); return; }
    if (urlItems.indexOf(url) === -1) urlItems.push(url);
    input.value = "";
    renderGallery();
  });

  if (fileInput) {
    fileInput.addEventListener("change", function () {
      var room = MAX_IMAGES - urlItems.length;
      var list = files();
      if (list.length > room) { alert(MSG.maxImages); setFiles(list.slice(0, Math.max(room, 0))); }
      renderGallery();
    });
  }

  // -- Étape 6 : aperçu -----------------------------------------------------
  function buildReview() {
    var items = allItems();
    var main = items[mainIndex];
    var img = $("review-img");
    img.hidden = !main;
    if (main) img.src = main.src;
    $("review-title").textContent = field("title").value || "—";
    var price = field("price").value;
    var ref = field("reference_price").value;
    $("review-price").textContent = price ? price.replace(".", ",") + " €" : "";
    $("review-ref").textContent = ref ? ref.replace(".", ",") + " €" : "";

    var flags = $("review-flags");
    flags.textContent = "";
    var addFlag = function (text, cls) {
      var span = document.createElement("span");
      span.className = "badge " + cls;
      span.textContent = text;
      flags.appendChild(span);
    };
    var pct = parseFloat(price) > 0 && parseFloat(ref) > parseFloat(price)
      ? Math.round((1 - price / ref) * 100) : 0;
    if (pct) addFlag("-" + pct + " %", "is-save");
    var availability = form.querySelector('[name="availability"]:checked');
    addFlag(availability && availability.value === "in_store" ? MSG.inStore : MSG.online, "is-border");
    if (field("promo_code").value) addFlag(MSG.promo + " " + field("promo_code").value, "is-new");

    var merchantSelect = field("merchant");
    var merchant = merchantSelect.value
      ? merchantSelect.options[merchantSelect.selectedIndex].text
      : field("merchant_name").value;
    $("review-meta").textContent = merchant ? MSG.availableAt + " " + merchant : MSG.merchantUnknown;
    $("review-desc").textContent = (field("description").value || "").slice(0, 300);
  }

  // -- Démarrage ------------------------------------------------------------
  renderGallery();
  toggleAvailability();
  updateDiscount();
  updateCounters();
  if (field("merchant_name").value) {
    $("merchant-detected").textContent = field("merchant_name").value;
  } else if (field("merchant").value) {
    var sel = field("merchant");
    $("merchant-detected").textContent = sel.options[sel.selectedIndex].text;
  }

  // Après un envoi refusé : ouvrir l'étape de la première erreur.
  var firstError = form.querySelector(".has-error");
  var errorStep = firstError && firstError.closest("[data-step]");
  show(errorStep ? errorStep.dataset.step : (form.dataset.start || "link"));
})();
