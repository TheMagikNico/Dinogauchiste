(() => {
  "use strict";
  const RANGES = { "24h": 24 * 3600e3, "7j": 7 * 86400e3, "30j": 30 * 86400e3 };
  const REFRESH_MS = 5 * 60e3;
  const range = document.body.dataset.range || "24h";
  const grid = document.getElementById("grid");
  const empty = document.getElementById("empty");
  const statusEl = document.getElementById("status");
  const dlg = document.getElementById("dlg");
  let items = [];
  let generatedAt = null;

  const fmtDate = new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeStyle: "short" });

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function safeUrl(u) {
    try {
      const x = new URL(u);
      return x.protocol === "https:" || x.protocol === "http:" ? x.href : null;
    } catch (e) { return null; }
  }
  function ago(d) {
    const m = Math.round((Date.now() - d.getTime()) / 60000);
    if (m < 1) return "à l'instant";
    if (m < 60) return "il y a " + m + " min";
    const h = Math.round(m / 60);
    if (h < 24) return "il y a " + h + " h";
    return fmtDate.format(d);
  }
  function picture(it, cls) {
    const u = it.image && safeUrl(it.image);
    const ph = () => el("div", "ph", (it.source || "?").charAt(0));
    if (!u) return ph();
    const img = el("img", cls);
    img.src = u;
    img.alt = "";
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer";
    img.addEventListener("error", () => img.replaceWith(ph()));
    return img;
  }

  function card(it) {
    const c = el("article", "card");
    c.tabIndex = 0;
    c.setAttribute("role", "button");
    c.appendChild(picture(it, "thumb"));
    const b = el("div", "body");
    const meta = el("div", "meta", it.source + " ");
    meta.appendChild(el("span", "when", "· " + ago(new Date(it.date))));
    b.appendChild(meta);
    b.appendChild(el("h2", null, it.title));
    b.appendChild(el("p", "summary", it.summary));
    b.appendChild(el("span", "more", "Lire le détail →"));
    c.appendChild(b);
    const open = () => openItem(it.id);
    c.addEventListener("click", open);
    c.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
    return c;
  }

  function linkList(title, rows) {
    const wrap = document.createDocumentFragment();
    if (!rows.length) return wrap;
    wrap.appendChild(el("h3", null, title));
    const ul = el("ul");
    rows.forEach((r) => {
      const u = safeUrl(r.url);
      if (!u) return;
      const li = el("li");
      const a = el("a", null, r.title || r.label);
      a.href = u; a.target = "_blank"; a.rel = "noopener noreferrer";
      li.appendChild(a);
      if (r.source) li.appendChild(document.createTextNode(" — " + r.source));
      ul.appendChild(li);
    });
    wrap.appendChild(ul);
    return wrap;
  }

  function openItem(id) {
    const it = items.find((x) => x.id === id);
    if (!it) return;
    dlg.replaceChildren();
    const inner = el("div", "d-inner");
    const close = el("button", "d-close", "✕");
    close.type = "button";
    close.setAttribute("aria-label", "Fermer");
    close.addEventListener("click", () => dlg.close());
    inner.appendChild(close);
    inner.appendChild(picture(it, "thumb"));
    const t = el("div", "d-text");
    const meta = el("div", "meta", it.source + " ");
    meta.appendChild(el("span", "when", "· " + fmtDate.format(new Date(it.date))));
    t.appendChild(meta);
    t.appendChild(el("h2", null, it.title));
    (it.detail || it.summary || "").split(/\n\n+/).filter(Boolean).forEach((p) => t.appendChild(el("p", null, p)));
    const src = safeUrl(it.url);
    if (src) {
      const a = el("a", "btn", "Lire l'article chez " + it.source + " ↗");
      a.href = src; a.target = "_blank"; a.rel = "noopener noreferrer";
      t.appendChild(a);
      t.appendChild(el("p", "note", "Source officielle. Certains médias réservent l'article complet à leurs abonnés."));
    }
    t.appendChild(linkList("Pour en savoir plus — d'autres médias", it.related || []));
    t.appendChild(linkList("Recherche complémentaire", it.more || []));
    inner.appendChild(t);
    dlg.appendChild(inner);
    if (!dlg.open) dlg.showModal();
    try { history.replaceState(null, "", "#" + id); } catch (e) { /* ignoré */ }
  }
  dlg.addEventListener("close", () => { try { history.replaceState(null, "", location.pathname); } catch (e) { /* ignoré */ } });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });

  function render() {
    const limit = Date.now() - RANGES[range];
    const list = items.filter((x) => new Date(x.date).getTime() >= limit);
    grid.replaceChildren(...list.map(card));
    empty.hidden = list.length > 0;
    statusEl.textContent = generatedAt
      ? list.length + " article" + (list.length > 1 ? "s" : "") + " · mis à jour " + ago(new Date(generatedAt)) + " · actualisation automatique"
      : "Aucune donnée : lancez la première mise à jour (voir le README).";
  }

  async function load() {
    try {
      const r = await fetch("data.json?t=" + Date.now(), { cache: "no-store" });
      if (!r.ok) throw new Error(r.status);
      const d = await r.json();
      items = d.items || [];
      generatedAt = d.generated_at;
    } catch (e) {
      statusEl.textContent = "Impossible de charger les articles pour le moment. Nouvel essai automatique…";
      return;
    }
    render();
    if (location.hash.length > 1 && !dlg.open) openItem(location.hash.slice(1));
  }

  load();
  setInterval(() => { if (!dlg.open) load(); }, REFRESH_MS);
  document.addEventListener("visibilitychange", () => { if (!document.hidden && !dlg.open) load(); });
})();
