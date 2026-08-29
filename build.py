#!/usr/bin/env python3
"""Build a fully static, mobile-first notes website from MBA S4 Notes folders."""

from __future__ import annotations

import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "_vendor"
sys.path.insert(0, str(VENDOR))

import markdown  # noqa: E402

WORKSPACE = ROOT.parent
OUT = ROOT

IGNORE_NAME = re.compile(r"(review|augmentation)", re.I)
WEEK_NUM = re.compile(r"Week\s+(\d+)", re.I)
MATH_BLOCK = re.compile(r"\$\$.*?\$\$|\\\[.*?\\\]", re.S)
MATH_INLINE = re.compile(r"\\\(.*?\\\)|(?<!\$)\$(?!\$)(.+?)(?<!\\)\$(?!\$)")

SUBJECTS = [
    {
        "folder": "Adv ML Done",
        "slug": "adv-ml",
        "name": "Advanced ML",
        "blurb": "Learning types, models, and algorithms.",
    },
    {
        "folder": "CSR Done",
        "slug": "csr",
        "name": "CSR",
        "blurb": "Corporate social responsibility and sustainability.",
    },
    {
        "folder": "DL Done",
        "slug": "dl",
        "name": "Deep Learning",
        "blurb": "Neural networks and deep learning.",
    },
    {
        "folder": "EFL Done",
        "slug": "efl",
        "name": "EFL",
        "blurb": "Leadership, governance, and ethical foundations.",
    },
    {
        "folder": "Entrepreneurship Done",
        "slug": "entrepreneurship",
        "name": "Entrepreneurship",
        "blurb": "Entrepreneurship, innovation, and venture practice.",
    },
    {
        "folder": "NLP Done",
        "slug": "nlp",
        "name": "NLP",
        "blurb": "Natural language processing.",
    },
    {
        "folder": "Project Done",
        "slug": "project",
        "name": "Project",
        "blurb": "Business research methods and analysis.",
    },
    {
        "folder": "Visualization Done",
        "slug": "visualization",
        "name": "Visualization",
        "blurb": "Data visualization and visual storytelling.",
    },
]


def slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def strip_md_inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = text.replace("\\.", ".")
    return text.strip()


def extract_week_number(filename: str) -> int | None:
    m = WEEK_NUM.search(filename)
    return int(m.group(1)) if m else None


def prepare_source(text: str, slug: str) -> str:
    if slug == "project":
        idx = text.find("# **Comprehensive Notes")
        if idx == -1:
            idx = text.find("# Comprehensive Notes")
        if idx != -1:
            text = text[idx:]
    return text


def protect_math(text: str) -> tuple[str, list[str]]:
    blocks: list[str] = []

    def save(match: re.Match[str]) -> str:
        blocks.append(match.group(0))
        return f"@@MATH{len(blocks) - 1}@@"

    text = MATH_BLOCK.sub(save, text)
    text = MATH_INLINE.sub(save, text)
    return text, blocks


def restore_math(html_text: str, blocks: list[str]) -> str:
    for i, block in enumerate(blocks):
        html_text = html_text.replace(f"@@MATH{i}@@", block)
    return html_text


def week_title_from_source(text: str, week_num: int) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = strip_md_inline(line[2:])
            title = re.sub(
                r"^Week\s+\d+\s*(Study Notes)?\s*[—:\-–]\s*",
                "",
                title,
                flags=re.I,
            )
            title = re.sub(r"^Comprehensive Notes:\s*", "", title, flags=re.I)
            return title.strip() or f"Week {week_num}"
    return f"Week {week_num}"


def wrap_tables(html_text: str) -> str:
    html_text = html_text.replace("<table>", '<div class="table-wrap"><table>')
    html_text = html_text.replace("</table>", "</table></div>")
    return html_text


def add_heading_ids(html_text: str) -> tuple[str, list[tuple[str, str, int]]]:
    toc: list[tuple[str, str, int]] = []
    used: dict[str, int] = {}

    def repl(match: re.Match[str]) -> str:
        level = int(match.group(1))
        attrs = match.group(2) or ""
        inner = match.group(3)
        if 'id="' in attrs:
            hid = re.search(r'id="([^"]+)"', attrs)
            heading_id = hid.group(1) if hid else slugify(inner)
        else:
            heading_id = slugify(inner)
            n = used.get(heading_id, 0)
            used[heading_id] = n + 1
            if n:
                heading_id = f"{heading_id}-{n + 1}"
            attrs = f'{attrs} id="{heading_id}"'
        if level <= 3:
            toc.append((heading_id, strip_md_inline(re.sub(r"<[^>]+>", "", inner)), level))
        return f"<h{level}{attrs}>{inner}</h{level}>"

    html_text = re.sub(
        r"<h([1-6])([^>]*)>(.*?)</h\1>",
        repl,
        html_text,
        flags=re.S,
    )
    return html_text, toc


def convert_markdown(text: str) -> tuple[str, list[tuple[str, str, int]]]:
    text, math = protect_math(text)
    md = markdown.Markdown(
        extensions=["extra", "sane_lists", "smarty"],
        output_format="html",
    )
    body = md.convert(text)
    body = restore_math(body, math)
    body = wrap_tables(body)
    body = re.sub(r"^<h1[^>]*>.*?</h1>\s*", "", body, count=1, flags=re.S)
    body, toc = add_heading_ids(body)
    return body, toc


def asset_prefix(depth: int) -> str:
    return "../" * depth


def hamburger_svg() -> str:
    return """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <path d="M4 7h16M4 12h16M4 17h16"/>
    </svg>"""


def close_svg() -> str:
    return """<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18"/>
    </svg>"""


def page_shell(
    *,
    title: str,
    kicker: str,
    heading: str,
    depth: int,
    body: str,
    extra_head: str = "",
    sidebar: str = "",
    show_hamburger: bool = False,
    home_href: str = "index.html",
) -> str:
    prefix = asset_prefix(depth)
    hamburger = ""
    if show_hamburger:
        hamburger = f"""
    <button class="icon-btn hamburger" id="hamburger" type="button" aria-controls="sidebar" aria-expanded="false" aria-label="Open week list">
      {hamburger_svg()}
    </button>"""
    return f"""<!DOCTYPE html>
<html lang="en" data-sw="{prefix}sw.js">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#1f4d47">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <meta name="apple-mobile-web-app-title" content="MBA S4">
  <title>{html.escape(title)}</title>
  <link rel="manifest" href="{prefix}manifest.json">
  <link rel="icon" href="{prefix}assets/icons/icon-192.png" sizes="192x192">
  <link rel="apple-touch-icon" href="{prefix}assets/icons/apple-touch-icon.png">
  <link rel="stylesheet" href="{prefix}assets/css/style.css">
  <link rel="stylesheet" href="{prefix}assets/vendor/katex/katex.min.css">
  {extra_head}
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-header">
    {hamburger}
    <a class="brand" href="{home_href}">
      <span class="brand-kicker">{html.escape(kicker)}</span>
      <span class="brand-title">{html.escape(heading)}</span>
    </a>
    <div class="header-actions">
      <button class="text-btn" id="install-btn" type="button" hidden>Install</button>
      <span class="sw-pill" id="sw-pill" hidden>Offline ready</span>
    </div>
    <div class="progress" aria-hidden="true"><span id="read-progress"></span></div>
  </header>
  <div class="backdrop" id="backdrop"></div>
  {body}
  <script src="{prefix}assets/js/nav.js"></script>
  <script defer src="{prefix}assets/vendor/katex/katex.min.js"></script>
  <script defer src="{prefix}assets/vendor/katex/contrib/auto-render.min.js"></script>
  <script>
    document.addEventListener("DOMContentLoaded", function () {{
      if (window.renderMathInElement) {{
        renderMathInElement(document.body, {{
          delimiters: [
            {{left: "$$", right: "$$", display: true}},
            {{left: "\\\\[", right: "\\\\]", display: true}},
            {{left: "\\\\(", right: "\\\\)", display: false}},
            {{left: "$", right: "$", display: false}}
          ],
          throwOnError: false
        }});
      }}
    }});
  </script>
</body>
</html>
"""


def render_home(catalog: list[dict]) -> str:
    cards = []
    for subj in catalog:
        n = len(subj["weeks"])
        cards.append(
            f"""    <a class="subject-card" href="{html.escape(subj['slug'])}/week-{subj['weeks'][0]['num']}.html">
      <h2>{html.escape(subj['name'])}</h2>
      <p>{html.escape(subj['blurb'])}</p>
      <span class="count">{n} week{'s' if n != 1 else ''}</span>
    </a>"""
        )
    body = f"""
  <main id="main" class="home-wrap">
    <section class="home-hero">
      <h1>MBA Semester 4 notes</h1>
      <p>Choose a subject, then move through each week from the sidebar. On a phone, open the menu to switch weeks.</p>
      <p class="home-offline">This site works offline on GitHub Pages. Open it once on a network, wait until the header says <strong>Offline ready</strong>, then install it (or Add to Home Screen). The saved copy stays on this device for well over two days, and usually much longer.</p>
    </section>
    <div class="subject-grid">
{chr(10).join(cards)}
    </div>
  </main>
"""
    return page_shell(
        title="MBA Semester 4 notes",
        kicker="MBA S4",
        heading="Study notes",
        depth=0,
        body=body,
        home_href="index.html",
        show_hamburger=False,
    )


def toc_html(toc: list[tuple[str, str, int]]) -> str:
    useful = [(hid, title, level) for hid, title, level in toc if level == 2]
    if len(useful) < 3:
        return ""
    items = []
    for hid, title, level in useful:
        items.append(
            f'      <li><a href="#{html.escape(hid)}">{html.escape(title)}</a></li>'
        )
    return f"""    <details class="toc">
      <summary>On this page</summary>
      <ol>
{chr(10).join(items)}
      </ol>
    </details>
"""


def sidebar_html(catalog: list[dict], current_slug: str, current_num: int, depth: int) -> str:
    prefix = asset_prefix(depth)
    options = []
    current = None
    for subj in catalog:
        first = subj["weeks"][0]["num"]
        href = f"{prefix}{subj['slug']}/week-{first}.html"
        selected = " selected" if subj["slug"] == current_slug else ""
        options.append(
            f'        <option value="{html.escape(href)}"{selected}>{html.escape(subj["name"])}</option>'
        )
        if subj["slug"] == current_slug:
            current = subj
    assert current is not None
    links = []
    for week in current["weeks"]:
        href = f"week-{week['num']}.html"
        short = week["title"]
        if len(short) > 72:
            short = short[:69].rsplit(" ", 1)[0] + "…"
        cls = ' class="is-active"' if week["num"] == current_num else ""
        links.append(
            f"""      <a{cls} href="{href}">
        <span class="week-num">Week {week['num']}</span>
        {html.escape(short)}
      </a>"""
        )
    return f"""
  <aside class="sidebar" id="sidebar">
    <div class="sidebar-head">
      <div class="sidebar-head-row">
        <span class="sidebar-label">Navigate</span>
        <button class="icon-btn" id="close-nav" type="button" aria-label="Close menu">
          {close_svg()}
        </button>
      </div>
      <label class="sidebar-label" for="subject-select">Subject</label>
      <select class="subject-select" id="subject-select">
{chr(10).join(options)}
      </select>
    </div>
    <nav class="week-nav" aria-label="Weeks">
{chr(10).join(links)}
    </nav>
  </aside>
"""


def pager_html(weeks: list[dict], index: int) -> str:
    prev_w = weeks[index - 1] if index > 0 else None
    next_w = weeks[index + 1] if index + 1 < len(weeks) else None
    parts = ['    <nav class="week-pager">']
    if prev_w:
        title = prev_w["title"]
        if len(title) > 48:
            title = title[:45].rsplit(" ", 1)[0] + "…"
        parts.append(
            f"""      <a href="week-{prev_w['num']}.html" rel="prev">
        <span class="pager-label">Previous</span>
        <span class="pager-title">Week {prev_w['num']}: {html.escape(title)}</span>
      </a>"""
        )
    if next_w:
        title = next_w["title"]
        if len(title) > 48:
            title = title[:45].rsplit(" ", 1)[0] + "…"
        parts.append(
            f"""      <a href="week-{next_w['num']}.html" rel="next">
        <span class="pager-label">Next</span>
        <span class="pager-title">Week {next_w['num']}: {html.escape(title)}</span>
      </a>"""
        )
    parts.append("    </nav>")
    return "\n".join(parts) if prev_w or next_w else ""


def render_week(catalog: list[dict], subj: dict, index: int, body_html: str, toc: list) -> str:
    week = subj["weeks"][index]
    sidebar = sidebar_html(catalog, subj["slug"], week["num"], 1)
    toc_block = toc_html(toc)
    pager = pager_html(subj["weeks"], index)
    inner = f"""
  <div class="shell">
    {sidebar}
    <main id="main" class="content">
      <article class="article">
        <p class="crumb">{html.escape(subj['name'])} · Week {week['num']}</p>
        <h1 class="page-title">{html.escape(week['title'])}</h1>
        <p class="page-meta">Week {week['num']} of {len(subj['weeks'])}</p>
{toc_block}
        <div class="prose">
{body_html}
        </div>
{pager}
      </article>
    </main>
  </div>
"""
    html_page = page_shell(
        title=f"{subj['name']} · Week {week['num']} — MBA S4 notes",
        kicker=subj["name"],
        heading=f"Week {week['num']}",
        depth=1,
        body=inner,
        home_href="../index.html",
        show_hamburger=True,
    )
    return html_page


def collect_weeks(folder: Path, slug: str) -> list[dict]:
    notes = folder / "Notes"
    if not notes.is_dir():
        raise SystemExit(f"Missing Notes folder: {notes}")
    weeks = []
    for path in sorted(notes.iterdir()):
        if path.suffix.lower() != ".md" or not path.is_file():
            continue
        if IGNORE_NAME.search(path.name):
            continue
        num = extract_week_number(path.name)
        if num is None:
            continue
        raw = path.read_text(encoding="utf-8")
        source = prepare_source(raw, slug)
        title = week_title_from_source(source, num)
        weeks.append(
            {
                "num": num,
                "path": path,
                "source": source,
                "title": title,
            }
        )
    weeks.sort(key=lambda w: w["num"])
    return weeks


def site_asset_urls() -> list[str]:
    urls = [
        "index.html",
        "offline.html",
        "404.html",
        "manifest.json",
        "assets/css/style.css",
        "assets/js/nav.js",
        "assets/icons/icon-192.png",
        "assets/icons/icon-512.png",
        "assets/icons/icon-maskable-512.png",
        "assets/icons/apple-touch-icon.png",
        "assets/icons/icon.svg",
        "assets/vendor/katex/katex.min.css",
        "assets/vendor/katex/katex.min.js",
        "assets/vendor/katex/contrib/auto-render.min.js",
    ]
    fonts = OUT / "assets" / "vendor" / "katex" / "fonts"
    if fonts.is_dir():
        for font in sorted(fonts.glob("*.woff2")):
            urls.append(f"assets/vendor/katex/fonts/{font.name}")
    return urls


def write_manifest() -> None:
    manifest = {
        "name": "MBA Semester 4 notes",
        "short_name": "MBA S4",
        "description": "Offline study notes for MBA Semester 4.",
        "id": "./",
        "start_url": "./index.html",
        "scope": "./",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#f4f0e8",
        "theme_color": "#1f4d47",
        "lang": "en",
        "icons": [
            {
                "src": "./assets/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "./assets/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "./assets/icons/icon-maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
    }
    write(OUT / "manifest.json", json.dumps(manifest, indent=2) + "\n")


def write_offline_page() -> None:
    body = """
  <main id="main" class="home-wrap">
    <section class="home-hero">
      <h1>This page is not cached yet</h1>
      <p>Open the home page once while online so every week can be stored on this device. After the header says Offline ready, the notes will open without a network.</p>
      <p><a href="index.html">Back to subjects</a></p>
    </section>
  </main>
"""
    write(
        OUT / "offline.html",
        page_shell(
            title="Offline — MBA S4 notes",
            kicker="MBA S4",
            heading="Offline",
            depth=0,
            body=body,
            home_href="index.html",
            show_hamburger=False,
        ),
    )


def write_service_worker(catalog: list[dict]) -> None:
    urls = site_asset_urls()
    for subj in catalog:
        urls.append(f"{subj['slug']}/index.html")
        for week in subj["weeks"]:
            urls.append(f"{subj['slug']}/week-{week['num']}.html")

    digest = hashlib.sha256("\n".join(urls).encode()).hexdigest()[:12]
    cache_name = f"mba-s4-notes-{digest}"
    precache_js = json.dumps(urls, indent=2)
    script = f"""/* Generated by build.py — do not edit by hand. */
const CACHE_NAME = {json.dumps(cache_name)};
const PRECACHE = {precache_js};

function inScope(url) {{
  return url.startsWith(self.registration.scope);
}}

function assetURL(path) {{
  return new URL(path, self.registration.scope).href;
}}

async function cacheAll(cache) {{
  const batch = 20;
  for (let i = 0; i < PRECACHE.length; i += batch) {{
    const slice = PRECACHE.slice(i, i + batch);
    await Promise.all(slice.map(async (path) => {{
      const href = assetURL(path);
      try {{
        const request = new Request(href, {{ cache: "reload", mode: "same-origin" }});
        const response = await fetch(request);
        if (!response || !response.ok) throw new Error(String(response && response.status));
        await cache.put(href, response);
      }} catch (err) {{
        try {{
          await cache.add(href);
        }} catch (err2) {{
          console.warn("PWA cache skip", path, err2);
        }}
      }}
    }}));
  }}
}}

self.addEventListener("install", (event) => {{
  event.waitUntil((async () => {{
    const cache = await caches.open(CACHE_NAME);
    await cacheAll(cache);
    await self.skipWaiting();
  }})());
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil((async () => {{
    const cache = await caches.open(CACHE_NAME);
    const stored = await cache.keys();
    if (stored.length > 40) {{
      const keys = await caches.keys();
      await Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)));
    }}
    await self.clients.claim();
    const clients = await self.clients.matchAll({{ includeUncontrolled: true }});
    for (const client of clients) {{
      client.postMessage({{ type: "cached" }});
    }}
  }})());
}});

async function cachedResponse(request) {{
  const cache = await caches.open(CACHE_NAME);
  const url = new URL(request.url);
  url.hash = "";
  const candidates = [request, url.href];
  if (url.pathname.endsWith("/")) {{
    candidates.push(new URL("index.html", url.href).href);
  }} else if (!/\\.[a-z0-9]+$/i.test(url.pathname)) {{
    candidates.push(url.href.replace(/\\/?$/, "/") + "index.html");
  }}
  for (const candidate of candidates) {{
    const hit = await cache.match(candidate, {{ ignoreSearch: true }});
    if (hit) return hit;
  }}
  return undefined;
}}

self.addEventListener("fetch", (event) => {{
  const request = event.request;
  if (request.method !== "GET" || !inScope(request.url)) return;
  event.respondWith((async () => {{
    const cached = await cachedResponse(request);
    if (cached) return cached;
    try {{
      const fresh = await fetch(request);
      if (fresh && fresh.ok && inScope(request.url)) {{
        const cache = await caches.open(CACHE_NAME);
        cache.put(request, fresh.clone());
      }}
      return fresh;
    }} catch (err) {{
      if (request.mode === "navigate") {{
        const offline = await cachedResponse(new Request(assetURL("offline.html")));
        if (offline) return offline;
        const home = await cachedResponse(new Request(assetURL("index.html")));
        if (home) return home;
      }}
      throw err;
    }}
  }})());
}});
"""
    write(OUT / "sw.js", script)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    catalog = []
    for spec in SUBJECTS:
        folder = WORKSPACE / spec["folder"]
        weeks = collect_weeks(folder, spec["slug"])
        if not weeks:
            raise SystemExit(f"No week notes found in {folder / 'Notes'}")
        catalog.append({**spec, "weeks": weeks})

    # Clean previously generated subject folders / index, keep assets and vendor
    for spec in SUBJECTS:
        dest = OUT / spec["slug"]
        if dest.exists():
            for f in dest.glob("*.html"):
                f.unlink()

    write(OUT / "index.html", render_home(catalog))

    for subj in catalog:
        dest = OUT / subj["slug"]
        dest.mkdir(parents=True, exist_ok=True)
        for i, week in enumerate(subj["weeks"]):
            body, toc = convert_markdown(week["source"])
            page = render_week(catalog, subj, i, body, toc)
            write(dest / f"week-{week['num']}.html", page)
            print(f"  {subj['name']}: week {week['num']} ({week['path'].name})")
        first_page = dest / f"week-{subj['weeks'][0]['num']}.html"
        write(dest / "index.html", first_page.read_text(encoding="utf-8"))

    write_manifest()
    write_offline_page()
    write(
        OUT / "404.html",
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Page not found — MBA S4 notes</title>
  <style>
    body { margin: 0; background: #f4f0e8; color: #1c1915; font-family: ui-sans-serif, system-ui, sans-serif; line-height: 1.5; }
    main { max-width: 36rem; margin: 12vh auto; padding: 1.25rem; }
    h1 { font-family: Georgia, "Times New Roman", serif; font-size: 1.8rem; }
    a { color: #1f4d47; }
  </style>
</head>
<body>
  <main>
    <h1>Page not found</h1>
    <p>That address is not part of these notes.</p>
    <p><a id="home" href="index.html">Back to subjects</a></p>
  </main>
  <script>
    (function () {
      var slugs = ["adv-ml","csr","dl","efl","entrepreneurship","nlp","project","visualization"];
      var path = location.pathname;
      var root = path;
      for (var i = 0; i < slugs.length; i++) {
        var needle = "/" + slugs[i] + "/";
        var at = path.indexOf(needle);
        if (at !== -1) { root = path.slice(0, at + 1); break; }
      }
      if (root === path) root = path.replace(/\\/[^/]*$/, "/");
      document.getElementById("home").href = root.replace(/\\/?$/, "/") + "index.html";
    })();
  </script>
</body>
</html>
""",
    )
    write(OUT / ".nojekyll", "\n")
    write_service_worker(catalog)

    n_pages = sum(len(s["weeks"]) for s in catalog)
    print(f"\nBuilt {n_pages} week pages across {len(catalog)} subjects → {OUT}")


if __name__ == "__main__":
    main()
