/* Marketing Brain — marketing site
   Minimal vanilla JS: nav toggle, theme toggle, reveal-on-scroll, loop step cycling, feature filters.
   Everything degrades gracefully without JS. */
(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.remove("no-js");
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- Mobile navigation ---- */
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("site-nav");
  if (toggle && nav) {
    var setOpen = function (open) {
      nav.classList.toggle("is-open", open);
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    };
    toggle.addEventListener("click", function () {
      setOpen(!nav.classList.contains("is-open"));
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("is-open")) { setOpen(false); toggle.focus(); }
    });
    document.addEventListener("click", function (e) {
      if (!nav.classList.contains("is-open")) return;
      if (nav.contains(e.target) || toggle.contains(e.target)) return;
      setOpen(false);
    });
    window.matchMedia("(min-width: 961px)").addEventListener("change", function (m) { if (m.matches) setOpen(false); });
  }

  /* ---- Theme toggle (system by default; explicit choice persisted) ---- */
  var themeBtn = document.querySelector(".theme-toggle");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      var current = root.getAttribute("data-theme") || (systemDark ? "dark" : "light");
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      try { localStorage.setItem("mb-site-theme", next); } catch (err) { /* storage unavailable */ }
    });
  }

  /* ---- Reveal on scroll ---- */
  var revealEls = document.querySelectorAll(".reveal, .insight");
  if ("IntersectionObserver" in window && !reduceMotion) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("is-visible"); io.unobserve(en.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("is-visible"); });
  }

  /* ---- Loop diagram: cycle the active step while in view ---- */
  var loop = document.querySelector("[data-loop]");
  if (loop) {
    var nodes = loop.querySelectorAll(".loop-node");
    var items = loop.querySelectorAll(".loop-steps li");
    var idx = 0, timer = null;
    var setActive = function (i) {
      nodes.forEach(function (n, k) { n.classList.toggle("is-active", k === i); });
      items.forEach(function (n, k) { n.classList.toggle("is-active", k === i); });
    };
    setActive(0);
    if (!reduceMotion && nodes.length) {
      var start = function () { if (timer) return; timer = setInterval(function () { idx = (idx + 1) % nodes.length; setActive(idx); }, 2200); };
      var stop = function () { if (timer) { clearInterval(timer); timer = null; } };
      if ("IntersectionObserver" in window) {
        new IntersectionObserver(function (entries) {
          entries.forEach(function (en) { en.isIntersecting ? start() : stop(); });
        }, { threshold: 0.25 }).observe(loop);
      } else { start(); }
      /* Hovering or focusing a step pins it. */
      items.forEach(function (li, k) {
        li.addEventListener("mouseenter", function () { stop(); idx = k; setActive(k); });
        li.addEventListener("mouseleave", start);
      });
    }
  }

  /* ---- Feature catalogue filters ---- */
  var filters = document.querySelectorAll("[data-filter]");
  if (filters.length) {
    var features = document.querySelectorAll(".feature[data-status]");
    var phases = document.querySelectorAll(".phase");
    var count = document.getElementById("filter-count");
    var apply = function (value) {
      var shown = 0;
      features.forEach(function (f) {
        var show = value === "all" || f.getAttribute("data-status") === value;
        f.hidden = !show; if (show) shown++;
      });
      phases.forEach(function (p) {
        var visible = p.querySelectorAll(".feature:not([hidden])").length;
        p.setAttribute("data-empty", visible === 0 ? "true" : "false");
      });
      filters.forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-filter") === value ? "true" : "false"); });
      if (count) count.textContent = shown + " of " + features.length + " modules shown";
    };
    filters.forEach(function (b) { b.addEventListener("click", function () { apply(b.getAttribute("data-filter")); }); });
    apply("all");
  }

  /* ---- Footer year ---- */
  var y = document.getElementById("year");
  if (y) y.textContent = String(new Date().getFullYear());
})();
