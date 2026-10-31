#!/usr/bin/env python3
"""Collecte les flux RSS, filtre la société française, prépare docs/data.json.

Usage :  python build.py          (collecte réelle)
         python build.py --demo   (données factices pour tester l'interface)

Résumés : si la variable d'environnement ANTHROPIC_API_KEY est définie, chaque
nouvel article est résumé (reformulé) via l'API Claude ; sinon on utilise
l'extrait fourni par le flux RSS du média.
"""
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DOCS = ROOT / "docs"
DATA = DOCS / "data.json"
UA = "Mozilla/5.0 (compatible; NewsletterSociete/1.0)"
WINDOW_DAYS = 30
MAX_LLM_PER_RUN = 80
TRACKING = re.compile(r"^(utm_|fbclid|gclid|mc_|xtor|at_|cmpid|ref$)", re.I)
STOP = set("""le la les un une des du de d l et ou en au aux a à ce cet cette ces son sa ses leur leurs qui que quoi dont
où par pour sur sous dans avec sans contre entre vers chez est sont été être avoir fait faire plus moins très aussi mais
donc car ni ne pas se si y on nous vous ils elles il elle je tu après avant depuis comme tout tous toute toutes""".split())


# ---------- utilitaires ----------
def clean_url(u):
    p = urlparse(u)
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING.match(k)]
    return urlunparse(p._replace(query=urlencode(q), fragment=""))


def norm(s):
    return unicodedata.normalize("NFD", s.lower()).encode("ascii", "ignore").decode()


def tokens(s):
    return {w for w in re.findall(r"[a-z0-9]{4,}", norm(s)) if w not in STOP}


def html_to_paragraphs(html):
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "iframe", "form"]):
        t.decompose()
    paras = [p.get_text(" ", strip=True) for p in soup.find_all(["p", "li"])]
    paras = [p for p in paras if len(p) > 30]
    if not paras:
        txt = soup.get_text(" ", strip=True)
        paras = [txt] if txt else []
    return "\n\n".join(paras)


def clip(text, n):
    text = text.strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    m = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if m > n * 0.5:
        return cut[: m + 1]
    return cut.rsplit(" ", 1)[0] + "…"


def find_image(entry):
    for key in ("media_content", "media_thumbnail"):
        for m in entry.get(key, []) or []:
            u = m.get("url")
            if u and (m.get("medium") in (None, "image") or re.search(r"\.(jpe?g|png|webp)", u, re.I)):
                return u
    for l in entry.get("links", []) or []:
        if l.get("rel") == "enclosure" and str(l.get("type", "")).startswith("image"):
            return l.get("href")
    html = (entry.get("content") or [{}])[0].get("value") or entry.get("summary", "")
    img = BeautifulSoup(html or "", "html.parser").find("img")
    if img and img.get("src", "").startswith("http"):
        return img["src"]
    return None


def og_image(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for attrs in ({"property": "og:image"}, {"name": "twitter:image"}):
            m = soup.find("meta", attrs=attrs)
            if m and m.get("content"):
                return urljoin(url, m["content"])
    except Exception as e:
        print(f"   (og:image indisponible pour {url}: {e})")
    return None


def llm_summary(title, source, text):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key or len(text) < 200:
        return None
    prompt = (
        "Rédige en français un résumé factuel et neutre de 5 à 8 phrases (environ 600 à 900 caractères) "
        "de l'article ci-dessous, avec tes propres mots (pas de citation longue). Réponds uniquement par le résumé.\n\n"
        f"Média : {source}\nTitre : {title}\n\nTexte disponible :\n{text[:6000]}"
    )
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": os.getenv("SUMMARY_MODEL", "claude-haiku-5-5"), "max_tokens": 500,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"   (résumé IA indisponible: {e})")
        return None


# ---------- collecte ----------
def collect(cfg, prev, cutoff):
    kw = [norm(k) for k in cfg["keywords"]]
    items = dict(prev)
    new_ids = []
    for src in cfg["sources"]:
        if not src.get("enabled", True):
            continue
        try:
            resp = requests.get(src["url"], headers={"User-Agent": UA}, timeout=25)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as e:
            print(f"✗ {src['name']}: {e}")
            continue
        n = 0
        for e in feed.entries:
            link = e.get("link")
            if not link:
                continue
            link = clean_url(link)
            t = e.get("published_parsed") or e.get("updated_parsed")
            date = datetime(*t[:6], tzinfo=timezone.utc) if t else datetime.now(timezone.utc)
            if date < cutoff:
                continue
            title = BeautifulSoup(e.get("title", ""), "html.parser").get_text(" ", strip=True)
            raw = (e.get("content") or [{}])[0].get("value") or e.get("summary", "")
            tags = " ".join(x.get("term", "") for x in e.get("tags", []) or [])
            if not src.get("society_only") and not any(k in norm(f"{title} {raw} {tags}") for k in kw):
                continue
            iid = hashlib.sha1(link.encode()).hexdigest()[:12]
            if iid in items:
                continue
            body = html_to_paragraphs(raw)
            items[iid] = {
                "id": iid, "title": title, "source": src["name"], "url": link,
                "date": date.isoformat(), "image": find_image(e), "_raw": body,
            }
            new_ids.append(iid)
            n += 1
        print(f"✓ {src['name']}: {n} nouveaux articles")
    # images manquantes, résumés
    llm_budget = MAX_LLM_PER_RUN
    for iid in new_ids:
        it = items[iid]
        if not it["image"]:
            it["image"] = og_image(it["url"])
        body = it.pop("_raw")
        summary = None
        if llm_budget > 0:
            summary = llm_summary(it["title"], it["source"], body)
            if summary:
                llm_budget -= 1
        it["summary"] = summary or clip(body, 900) or "Résumé indisponible : consultez l'article chez la source."
        it["detail"] = (summary + "\n\n" if summary else "") + (clip(body, 2500) if body else "")
    return items


def add_related(items):
    toks = {i: tokens(it["title"]) for i, it in items.items()}
    for i, it in items.items():
        scored = []
        for j, other in items.items():
            if j == i or other["source"] == it["source"]:
                continue
            a, b = toks[i], toks[j]
            if not a or not b:
                continue
            s = len(a & b) / len(a | b)
            if s >= 0.25:
                scored.append((s, other))
        scored.sort(key=lambda x: -x[0])
        it["related"] = [{"source": o["source"], "title": o["title"], "url": o["url"]} for _, o in scored[:4]]
        words = sorted(toks[i], key=len, reverse=True)[:5]
        q = quote(" ".join(words) or it["title"])
        it["more"] = [{"label": "Chercher d'autres sources (Google Actualités)",
                       "url": f"https://news.google.com/search?q={q}&hl=fr&gl=FR&ceid=FR:fr"}]


def demo_items(now):
    srcs = ["Mediapart", "Libération", "L'Humanité", "Basta!", "Reporterre", "Politis"]
    topics = ["Hausse des loyers et mal-logement : les associations alertent",
              "Hôpital public : les soignants en grève dans plusieurs régions",
              "Réforme de l'assurance chômage : les syndicats dénoncent un recul des droits",
              "Violences policières : une enquête révèle des failles dans le contrôle",
              "Écoles rurales : fermetures de classes et mobilisation des parents",
              "Féminicides : les associations réclament un budget dédié",
              "Précarité étudiante : files d'attente devant les banques alimentaires",
              "Agriculteurs et transition écologique : un dialogue sous tension"]
    body = ("Ceci est un texte de démonstration. " * 12).strip()
    out = {}
    for k in range(24):
        title = topics[k % len(topics)] + (" (suite)" if k >= len(topics) else "")
        date = now - timedelta(hours=[2, 5, 9, 20, 30, 60, 100, 150, 200, 300, 420, 600][k % 12] + k * 3)
        iid = hashlib.sha1(f"demo{k}".encode()).hexdigest()[:12]
        out[iid] = {"id": iid, "title": title, "source": srcs[k % len(srcs)], "url": "https://example.org/demo",
                    "date": date.isoformat(), "image": None, "summary": body, "detail": body + "\n\n" + body}
    return out


def main():
    cfg = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    if "--demo" in sys.argv:
        items = demo_items(now)
    else:
        prev = {}
        if DATA.exists():
            for it in json.loads(DATA.read_text(encoding="utf-8")).get("items", []):
                if datetime.fromisoformat(it["date"]) >= cutoff:
                    prev[it["id"]] = it
        items = collect(cfg, prev, cutoff)
    add_related(items)
    lst = sorted(items.values(), key=lambda x: x["date"], reverse=True)
    DOCS.mkdir(exist_ok=True)
    DATA.write_text(json.dumps({"generated_at": now.isoformat(), "items": lst}, ensure_ascii=False), encoding="utf-8")
    print(f"→ {len(lst)} articles écrits dans {DATA}")


if __name__ == "__main__":
    main()
