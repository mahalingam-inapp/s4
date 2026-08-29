(function () {
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.getElementById("backdrop");
  var hamburger = document.getElementById("hamburger");
  var closeBtn = document.getElementById("close-nav");
  var select = document.getElementById("subject-select");
  var bar = document.getElementById("read-progress");
  var installBtn = document.getElementById("install-btn");
  var pill = document.getElementById("sw-pill");
  var deferredPrompt = null;

  function setOpen(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("is-open", open);
    if (backdrop) backdrop.classList.toggle("is-visible", open);
    if (hamburger) hamburger.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.style.overflow = open && window.matchMedia("(max-width: 959px)").matches ? "hidden" : "";
  }

  if (hamburger) hamburger.addEventListener("click", function () { setOpen(true); });
  if (closeBtn) closeBtn.addEventListener("click", function () { setOpen(false); });
  if (backdrop) backdrop.addEventListener("click", function () { setOpen(false); });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") setOpen(false);
  });

  if (select) {
    select.addEventListener("change", function () {
      var href = select.value;
      if (href) window.location.href = href;
    });
  }

  window.addEventListener("resize", function () {
    if (window.matchMedia("(min-width: 960px)").matches) setOpen(false);
  });

  if (bar) {
    var article = document.querySelector(".article");
    function updateProgress() {
      if (!article) return;
      var rect = article.getBoundingClientRect();
      var total = article.offsetHeight - window.innerHeight;
      var scrolled = -rect.top;
      var pct = total <= 0 ? 100 : Math.min(100, Math.max(0, (scrolled / total) * 100));
      bar.style.width = pct + "%";
    }
    window.addEventListener("scroll", updateProgress, { passive: true });
    updateProgress();
  }

  function showPill(text) {
    if (!pill) return;
    pill.hidden = false;
    pill.textContent = text;
  }

  if (navigator.storage && navigator.storage.persist) {
    navigator.storage.persist().catch(function () {});
  }

  if (!navigator.onLine) showPill("Offline");
  window.addEventListener("offline", function () { showPill("Offline"); });
  window.addEventListener("online", function () {
    if (pill && pill.textContent === "Offline") showPill("Offline ready");
  });

  if (installBtn) {
    window.addEventListener("beforeinstallprompt", function (e) {
      e.preventDefault();
      deferredPrompt = e;
      installBtn.hidden = false;
    });
    installBtn.addEventListener("click", function () {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt.userChoice.finally(function () {
        installBtn.hidden = true;
        deferredPrompt = null;
      });
    });
    window.addEventListener("appinstalled", function () {
      installBtn.hidden = true;
      deferredPrompt = null;
    });
  }

  if ("serviceWorker" in navigator) {
    var swPath = document.documentElement.getAttribute("data-sw") || "sw.js";
    var swHref = new URL(swPath, window.location.href);
    var scopeHref = new URL("./", swHref).href;
    navigator.serviceWorker.register(swHref.href, { scope: scopeHref }).then(function (reg) {
      if (reg.active && !reg.installing) showPill("Offline ready");
      if (reg.installing) showPill("Saving notes…");
      reg.addEventListener("updatefound", function () {
        var installing = reg.installing;
        if (!installing) return;
        showPill("Saving notes…");
        installing.addEventListener("statechange", function () {
          if (installing.state === "installed") showPill("Offline ready");
        });
      });
    }).catch(function () {
      /* file:// and some browsers cannot register a worker; local assets still load. */
    });
    navigator.serviceWorker.addEventListener("message", function (event) {
      if (event.data && event.data.type === "cached") showPill("Offline ready");
    });
  }
})();
