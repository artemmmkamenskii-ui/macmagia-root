#!/usr/bin/env python3
"""
Build /blog/ HTML pages from docs/seo/articles/*.md.

Usage: python3 scripts/build_blog.py [--allow-eso]

Reads markdown articles, renders each one to blog/<slug>.html using the
project template (matching the manually-built chto-takoe-mak-karty.html),
regenerates blog/index.html, updates sitemap.xml.

Markdown extensions we use:
  - YAML frontmatter (slug, title, description, publishedAt, updatedAt,
    authorSlug, tags, emoji, coverGradient, ogImage, readingTime, category)
  - ## <a name="X"></a>Heading  → <h2 id="X">Heading</h2>
  - ## Heading                  → <h2 id="auto-slug">Heading</h2>
  - ## Оглавление block         → stripped (TOC is auto-generated)
  - ## Частые вопросы…          → FAQ cards + FAQPage JSON-LD
                                  (Q lines: **Question?**, A is next para)
  - ::: pullquote ... :::       → <aside class="article__pullquote">
  - ::: cta /url "Btn"          → branded inline CTA block
        body
    :::
  - --- on its own line         → decorative section divider

Эзо-фильтр: hard-fail if any forbidden esoteric term appears (per
docs/seo/agent-task.md §2). Override with --allow-eso for emergencies.

Dependencies: pip3 install markdown pyyaml
"""

import sys
import re
import json
import html
import argparse
import datetime
from pathlib import Path

try:
    import yaml
    import markdown as md_lib
except ImportError as e:
    print(f"Missing Python dependency: {e.name}.", file=sys.stderr)
    print("Run: pip3 install -r scripts/requirements.txt", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DIR = ROOT / "docs" / "seo" / "articles"
BLOG_DIR = ROOT / "blog"
SITEMAP = ROOT / "sitemap.xml"

SITE_URL = "https://macmagia.ru"
LOGO_URL = f"{SITE_URL}/icon-512.png"

# Яндекс.Метрика 109562142. Константа НЕ проходит через .format(), скобки литеральные.
YM_SNIPPET = """<!-- Yandex.Metrika counter -->
<script type="text/javascript">
   (function(m,e,t,r,i,k,a){m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};m[i].l=1*new Date();for(var j=0;j<document.scripts.length;j++){if(document.scripts[j].src===r){return;}}k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)})(window,document,"script","https://mc.yandex.ru/metrika/tag.js","ym");
   ym(109562142, "init", {clickmap:true, trackLinks:true, accurateTrackBounce:true, webvisor:true});
</script>
<noscript><div><img src="https://mc.yandex.ru/watch/109562142" style="position:absolute; left:-9999px;" alt="" /></div></noscript>
<!-- /Yandex.Metrika counter -->
"""

def inject_metrika(html):
    return html.replace("</head>", YM_SNIPPET + "</head>", 1)
DEFAULT_OG_IMAGE = f"{SITE_URL}/about.jpg"


def resolve_og_image(fm):
    """Обложка статьи для Google Discover / og:image / schema.
    Приоритет: явный ogImage → своё фото cover: → сгенерированная
    blog/covers/<slug>.jpg → общий дефолт. Возвращает абсолютный URL."""
    if fm.get("ogImage"):
        return fm["ogImage"]
    cover = fm.get("cover")
    if cover:
        return cover if cover.startswith("http") else f"{SITE_URL}{cover}"
    slug = fm.get("slug")
    if slug and (BLOG_DIR / "covers" / f"{slug}.jpg").exists():
        return f"{SITE_URL}/blog/covers/{slug}.jpg"
    return DEFAULT_OG_IMAGE

AUTHORS = {
    "ekaterina-kamenskaya": {
        "name": "Екатерина Каменская",
        "role": "Психолог, выпускница МГУ",
        "longRole": "Психолог, выпускница психологического факультета МГУ, основатель МакМагии",
        "bio": "Работаю с метафорическими картами и арт-терапией в индивидуальной практике с клиентами и обучаю психологов. Объединяю классическую психологию, проективные методики и современные технологии — в том числе AI-инструменты для документации сессий.",
        "avatar": "/about.jpg",
        "schemaType": "Person",
        "schemaId": "https://macmagia.ru/#ekaterina",
        "jobTitle": "Психолог",
        "alumniOf": "Московский государственный университет имени М. В. Ломоносова",
    },
    "macmagia-editorial": {
        "name": "Редакция МакМагии",
        "role": "Материал проверен Е. Каменской, психологом",
        "longRole": "Редакция МакМагии (материалы проверяет Екатерина Каменская, психолог)",
        "bio": "Редакция МакМагии готовит обзорные и справочные материалы. Каждая статья проходит редактуру Екатериной Каменской — психологом и основателем МакМагии.",
        "avatar": "/icon-512.png",
        "schemaType": "Organization",
        "schemaId": "https://macmagia.ru/#organization",
    },
}
DEFAULT_AUTHOR = "ekaterina-kamenskaya"

# Related-products registry. An article's frontmatter can list `relatedProducts:
# [slug, slug, ...]` and the corresponding card grid is rendered between the
# article body and the author card. Keep titles short and texts under 120 chars.
PRODUCTS = {
    "online": {
        "url": "/online",
        "title": "Платформа МАК онлайн",
        "text": "Виртуальные колоды и инструменты для расклада в браузере — для сессий с клиентом и для домашней практики.",
        "emoji": "💻",
    },
    "cards": {
        "url": "/cards",
        "title": "Колоды МакМагии",
        "text": "Электронные и печатные колоды для работы в кабинете и дома.",
        "emoji": "🎴",
    },
    "mac": {
        "url": "/mac",
        "title": "Курс по МАК для специалистов",
        "text": "Техники и реальные кейсы работы с клиентом — для психологов, арт-терапевтов, коучей.",
        "emoji": "🧠",
    },
    "artterapy": {
        "url": "/artterapy",
        "title": "Курс по арт-терапии",
        "text": "Практические техники арт-терапии: рисунок, лепка, коллаж, песочная работа.",
        "emoji": "🎨",
    },
    "ai": {
        "url": "/ai",
        "title": "Курс «Своя колода с AI»",
        "text": "Пошаговое создание авторской колоды МАК через нейросети: концепция, генерация, печать.",
        "emoji": "🪄",
    },
    "coach": {
        "url": "/coach",
        "title": "Курс по коучингу",
        "text": "Инструменты коучинга для работы с целями, состояниями и ресурсами клиента.",
        "emoji": "🎯",
    },
}

# Эзо-фильтр. Точное совпадение по словарным границам (\b), чтобы бренд
# "МакМагия" не триггерил "магия" (там нет границы внутри слова).
FORBIDDEN_PATTERNS = [
    r"магически", r"магически[йяе]", r"магическо[ейм]",
    r"волшебно", r"волшебство", r"волшебны[мйх]",
    r"гадание", r"гадан[ий]я", r"гадать", r"гаданье", r"нагадать",
    r"таро", r"руны", r"руна", r"гороскоп", r"астрологи[яи]",
    r"нумерологи[яи]", r"хиромантия",
    r"эзотерик[аиу]", r"эзотерическ",
    r"предсказани[ея]", r"предсказать", r"прорицани[ея]", r"прорицать",
    r"карма", r"кармически[йяе]",
    r"чакр[аыыу]", r"биополе",
    r"ангелы", r"архангел",
    r"вселенная говорит", r"послание вселенной",
    r"знак свыше", r"знаки судьбы",
    r"привлечение денег", r"привлечение любви",
    r"исполнение желани[йя]", r"магический ритуал",
    r"карты подскажут", r"карты знают", r"карты говорят",
    r"карта дня", r"расклад на месяц", r"расклад на будущее",
    r"расшифровка прошлой жизни", r"раскроют истину",
    r"волшебным образом",
]
FORBIDDEN_RE = re.compile(r"\b(?:" + "|".join(FORBIDDEN_PATTERNS) + r")\b",
                          re.IGNORECASE | re.UNICODE)


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n+(.*)", text, re.DOTALL)
    if not m:
        raise ValueError("Article must start with --- YAML frontmatter ---")
    return yaml.safe_load(m.group(1)), m.group(2)


def reading_time_min(md_text):
    words = len(re.findall(r"\w+", md_text))
    return max(1, round(words / 200))


def html_escape(s):
    return html.escape(str(s), quote=True)


def render_inline_md(text):
    """Render inline-only markdown (used for FAQ answers and small fragments)."""
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def transliterate_for_slug(text):
    table = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    s = text.lower()
    out = []
    for ch in s:
        out.append(table.get(ch, ch))
    s = "".join(out)
    s = re.sub(r"[^\w-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def strip_h1(md_text):
    return re.sub(r"^#\s+.+?\n+", "", md_text, count=1)


def strip_toc_section(md_text):
    """Strip the ## Оглавление list block."""
    return re.sub(
        r"^##\s+(?:<a\s+name=\"[^\"]+\"></a>)?Оглавление[^\n]*\n+(?:^- .+\n?)+\n*",
        "",
        md_text,
        count=1,
        flags=re.MULTILINE,
    )


def strip_legacy_related(md_text):
    """Strip a trailing **Читайте также:** block (auto-generated now)."""
    return re.sub(
        r"\n+(?:---\s*\n+)?\*\*Читайте также:\*\*[\s\S]*\Z",
        "",
        md_text,
    )


def extract_faq(md_text):
    """Find FAQ section, extract Q/A pairs.

    Returns (items, md_with_placeholder). The H2 is kept; the Q/A pairs are
    replaced with the placeholder <!--MMFAQ-->. Any tail content (e.g. ---
    decorative divider or extra prose) AFTER the last Q/A but BEFORE the next
    H2 is preserved verbatim — it follows the placeholder.
    """
    h2_pat = re.compile(
        r"(^##\s+(?:<a\s+name=\"([^\"]+)\"></a>)?(?:Частые вопросы|FAQ)[^\n]*$)",
        re.MULTILINE,
    )
    h2_match = h2_pat.search(md_text)
    if not h2_match:
        return [], md_text
    section_start = h2_match.end()
    rest = md_text[section_start:]
    next_h2 = re.search(r"^##\s+", rest, re.MULTILINE)
    section_end_offset = next_h2.start() if next_h2 else len(rest)
    section_body = rest[:section_end_offset]

    # Split off any trailing non-Q/A content (e.g. a --- decorative divider
    # placed between the last answer and the next H2) so it doesn't get
    # swallowed by the final Q/A regex match.
    tail_split = re.split(r"\n\s*\n---\s*\n", section_body, maxsplit=1)
    qa_zone = tail_split[0]
    tail_md = ("---\n" + tail_split[1]).strip() if len(tail_split) > 1 else ""

    items = []
    qa_pat = re.compile(
        r"\*\*\s*([^*]+?\?)\s*\*\*\s*\n+(.+?)(?=\n+\*\*\s*[^*]+?\?\s*\*\*|\Z)",
        re.DOTALL,
    )
    for m in qa_pat.finditer(qa_zone):
        items.append({"q": m.group(1).strip(), "a_md": m.group(2).strip()})

    tail = tail_md
    head_line = h2_match.group(1)
    replacement = head_line + "\n\n<!--MMFAQ-->\n\n"
    if tail:
        replacement += tail + "\n\n"
    new = (md_text[:h2_match.start()] + replacement
           + md_text[section_start + section_end_offset:])
    return items, new


def convert_custom_blocks(md_text):
    # Hard-fail if an article emits empty ::: cta ... ::: blocks — the regex
    # below won't match them and the raw markers would leak into HTML.
    empty_cta = re.search(r':::\s*cta\s+\S+\s+"[^"]+"\s*\n\s*:::\s*', md_text)
    if empty_cta:
        raise ValueError(
            f"Empty ::: cta block found (no body between markers). "
            f"Context: …{empty_cta.group(0)[:80]}… "
            f"Add 1-2 sentences inside the block."
        )
    # ::: pullquote ... :::
    md_text = re.sub(
        r":::\s*pullquote\s*\n(.+?)\n:::\s*",
        lambda m: (f'\n\n<aside class="article__pullquote">'
                   f'{render_inline_md(m.group(1).strip())}'
                   f'</aside>\n\n'),
        md_text,
        flags=re.DOTALL,
    )
    # ::: cta /url "Button text"
    #   body
    # :::
    md_text = re.sub(
        r':::\s*cta\s+(\S+)\s+"([^"]+)"\s*\n(.+?)\n:::\s*',
        lambda m: (
            '\n\n<div class="article__cta">'
            f'<div class="article__cta-text">{render_inline_md(m.group(3).strip())}</div>'
            f'<a href="{m.group(1)}" class="btn btn--primary btn--sm">{html_escape(m.group(2))}</a>'
            '</div>\n\n'
        ),
        md_text,
        flags=re.DOTALL,
    )
    # ::: callout warning
    #   body
    # :::
    md_text = re.sub(
        r":::\s*callout\s+(\w+)\s*\n(.+?)\n:::\s*",
        lambda m: (f'\n\n<aside class="article__callout article__callout--{m.group(1)}">'
                   f'{render_inline_md(m.group(2).strip())}'
                   f'</aside>\n\n'),
        md_text,
        flags=re.DOTALL,
    )
    # --- on its own line → decorative divider
    md_text = re.sub(
        r"^---\s*$",
        '<div class="article__divider" role="separator">'
        '<span class="article__divider-dot" aria-hidden="true"></span>'
        '</div>',
        md_text,
        flags=re.MULTILINE,
    )
    # ## <a name="X"></a>Title → ## Title {#X}  (so attr_list picks the ID up)
    md_text = re.sub(
        r'^##\s+<a\s+name="([^"]+)"></a>(.+?)$',
        r"## \2 {#\1}",
        md_text,
        flags=re.MULTILINE,
    )
    return md_text


def auto_anchor_h2(md_text):
    """For ## headings without an explicit {#id}, add one based on transliterated slug."""
    def add_id(m):
        heading = m.group(1).strip()
        if "{#" in heading:
            return m.group(0)
        slug = transliterate_for_slug(re.sub(r"<[^>]+>", "", heading))
        if not slug:
            return m.group(0)
        return f"## {heading} {{#{slug}}}"
    return re.sub(r"^##\s+(.+?)\s*$", add_id, md_text, flags=re.MULTILINE)


def extract_toc_from_html(body_html):
    out = []
    for m in re.finditer(r'<h2\s+id="([^"]+)"[^>]*>(.+?)</h2>', body_html):
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        out.append((m.group(1), title))
    return out


def render_faq_cards(items):
    if not items:
        return ""
    parts = ['<div class="article__faq article__faq--cards">']
    for it in items:
        parts.append(
            '<div class="article__faq-item">'
            f'<p class="article__faq-q">{html_escape(it["q"])}</p>'
            f'<p class="article__faq-a">{render_inline_md(it["a_md"])}</p>'
            '</div>'
        )
    parts.append('</div>')
    return "\n".join(parts)


def faq_for_schema(items):
    out = []
    for it in items:
        a = it["a_md"]
        a = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", a)
        a = re.sub(r"\*\*([^*]+)\*\*", r"\1", a)
        a = re.sub(r"\*([^*]+)\*", r"\1", a)
        out.append({
            "@type": "Question",
            "name": it["q"],
            "acceptedAnswer": {"@type": "Answer", "text": a.strip()},
        })
    return out


def build_jsonld(fm, faq_items, author, canonical):
    author_obj = {
        "@type": author["schemaType"],
        "@id": author["schemaId"],
        "name": author["name"],
    }
    if author.get("jobTitle"):
        author_obj["jobTitle"] = author["jobTitle"]
    if author.get("alumniOf"):
        author_obj["alumniOf"] = {
            "@type": "CollegeOrUniversity",
            "name": author["alumniOf"],
        }
    blogposting = {
        "@type": "BlogPosting",
        "@id": canonical + "#article",
        "mainEntityOfPage": canonical,
        "headline": fm["title"],
        "description": fm["description"],
        "image": resolve_og_image(fm),
        "datePublished": str(fm["publishedAt"]),
        "dateModified": str(fm.get("updatedAt", fm["publishedAt"])),
        "inLanguage": "ru-RU",
        "author": author_obj,
        "publisher": {
            "@type": "Organization",
            "@id": "https://macmagia.ru/#organization",
            "name": "МакМагия",
            "logo": {"@type": "ImageObject", "url": LOGO_URL},
        },
        "keywords": fm.get("tags", []),
    }
    if fm.get("category"):
        blogposting["articleSection"] = fm["category"]

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Главная", "item": SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "Блог", "item": SITE_URL + "/blog/"},
            {"@type": "ListItem", "position": 3, "name": fm["title"]},
        ],
    }

    graph = [blogposting, breadcrumb]
    if faq_items:
        graph.append({"@type": "FAQPage", "mainEntity": faq_for_schema(faq_items)})
    return {"@context": "https://schema.org", "@graph": graph}


def render_toc(items):
    if not items:
        return ""
    lis = "\n                    ".join(
        f'<li><a href="#{html_escape(a)}">{html_escape(t)}</a></li>'
        for a, t in items
    )
    return (
        '<aside class="article-toc" aria-label="Содержание статьи">\n'
        '                <div class="article-toc__title">Содержание</div>\n'
        '                <ol class="article-toc__list">\n'
        f'                    {lis}\n'
        '                </ol>\n'
        '            </aside>'
    )


def render_products(slugs):
    """Render the related-products card grid from a list of product slugs.

    Unknown slugs are skipped with a stderr warning so a typo in frontmatter
    doesn't kill the build.
    """
    if not slugs:
        return ""
    items_html = []
    for slug in slugs:
        product = PRODUCTS.get(slug)
        if not product:
            print(f"WARN: unknown relatedProducts slug: {slug!r}", file=sys.stderr)
            continue
        items_html.append(
            '<a class="article-products__item" href="{url}">'
            '<div class="article-products__icon" aria-hidden="true">{emoji}</div>'
            '<div class="article-products__body">'
            '<div class="article-products__name">{title}</div>'
            '<div class="article-products__text">{text}</div>'
            '</div>'
            '<div class="article-products__arrow" aria-hidden="true">→</div>'
            '</a>'.format(
                url=html_escape(product["url"]),
                emoji=product["emoji"],
                title=html_escape(product["title"]),
                text=html_escape(product["text"]),
            )
        )
    if not items_html:
        return ""
    return (
        '<aside class="article-products" aria-label="Связанные продукты МакМагии">\n'
        '                <div class="article-products__title">Связанные продукты МакМагии</div>\n'
        f'                <div class="article-products__grid">{"".join(items_html)}</div>\n'
        '            </aside>'
    )


def render_related(current_fm, all_meta):
    current_slug = current_fm["slug"]
    current_tags = set(current_fm.get("tags", []))
    scored = []
    for meta in all_meta:
        if meta["slug"] == current_slug:
            continue
        overlap = len(set(meta.get("tags", [])) & current_tags)
        scored.append((overlap, str(meta["publishedAt"]), meta))
    scored.sort(key=lambda x: (-x[0], x[1]), reverse=False)
    scored.sort(key=lambda x: -x[0])
    related = [m for _, _, m in scored[:4]]
    if not related:
        return ""
    items = "\n                    ".join(
        f'<li><a href="/blog/{m["slug"]}.html">{html_escape(m["title"])}</a></li>'
        for m in related
    )
    return (
        '<section class="article-related-v2">\n'
        '                <h2 class="article-related-v2__title">Читайте также</h2>\n'
        '                <ul class="article-related-v2__list">\n'
        f'                    {items}\n'
        '                </ul>\n'
        '            </section>'
    )


HEADER_HTML = """<header class="header">
    <div class="container header__inner">
        <a href="/" class="logo">
            <span class="logo__mark">
                <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                    <circle cx="20" cy="20" r="6" fill="currentColor"/>
                    <g stroke="currentColor" stroke-width="2" stroke-linecap="round">
                        <path d="M20 6 L20 14"/><path d="M20 26 L20 34"/>
                        <path d="M6 20 L14 20"/><path d="M26 20 L34 20"/>
                        <path d="M10 10 L15.5 15.5"/><path d="M24.5 24.5 L30 30"/>
                        <path d="M30 10 L24.5 15.5"/><path d="M15.5 24.5 L10 30"/>
                    </g>
                </svg>
            </span>
            <span class="logo__text">МакМагия</span>
        </a>
        <nav class="nav">
            <a href="/#products">Продукты</a>
            <a href="/#courses">Обучение</a>
            <a href="/blog/">Блог</a>
            <a href="/#creator">Обо мне</a>
            <a href="/#footer">Контакты</a>
        </nav>
        <div class="header__cta">
            <a href="https://lk.macmagia.ru/login" class="btn btn--ghost btn--sm">Войти</a>
            <a href="/#products" class="btn btn--primary btn--sm">Начать бесплатно</a>
        </div>
        <button class="burger" aria-label="Меню">
            <span></span><span></span><span></span>
        </button>
    </div>
</header>"""

FOOTER_HTML = """<footer class="footer" id="footer">
    <div class="container footer__inner">
        <div class="footer__col">
            <a href="/" class="logo logo--light">
                <span class="logo__mark">
                    <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                        <circle cx="20" cy="20" r="6" fill="currentColor"/>
                        <g stroke="currentColor" stroke-width="2" stroke-linecap="round">
                            <path d="M20 6 L20 14"/><path d="M20 26 L20 34"/>
                            <path d="M6 20 L14 20"/><path d="M26 20 L34 20"/>
                            <path d="M10 10 L15.5 15.5"/><path d="M24.5 24.5 L30 30"/>
                            <path d="M30 10 L24.5 15.5"/><path d="M15.5 24.5 L10 30"/>
                        </g>
                    </svg>
                </span>
                <span class="logo__text">МакМагия</span>
            </a>
            <p class="footer__about">Психология, метафорические карты и AI в одном пространстве.</p>
        </div>
        <div class="footer__col">
            <div class="footer__title">Продукты</div>
            <a href="https://provizorai.ru/" target="_blank" rel="noopener">AI платформа</a>
            <a href="/cards">Электронные колоды</a>
            <a href="https://www.wildberries.ru/seller/63444" target="_blank" rel="noopener">Колоды на Wildberries</a>
        </div>
        <div class="footer__col">
            <div class="footer__title">Обучение</div>
            <a href="/ai">Создание колоды с AI</a>
            <a href="/artterapy">Арт-терапия</a>
            <a href="/mac">МАК-карты</a>
            <a href="/blog/">Блог</a>
        </div>
        <div class="footer__col">
            <div class="footer__title">Контакты</div>
            <a href="mailto:macmagia@yandex.ru">macmagia@yandex.ru</a>
            <div class="footer__title" style="margin-top: 22px;">Документы</div>
            <a href="/public-offer.html">Публичная оферта</a>
            <a href="/privacy-policy.html">Политика обработки ПДн</a>
            <a href="/refund-policy.html">Политика возвратов</a>
        </div>
    </div>
</footer>"""


def format_ru_date(d):
    months = ["января", "февраля", "марта", "апреля", "мая", "июня",
              "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    return f"{d.day} {months[d.month - 1]} {d.year}"


def ensure_date(value):
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        return datetime.date.fromisoformat(value)
    raise ValueError(f"Unparseable date: {value!r}")


def render_article(md_path, all_meta):
    raw = md_path.read_text(encoding="utf-8")
    fm, body_md = parse_frontmatter(raw)

    for k in ("slug", "title", "description", "publishedAt"):
        if k not in fm:
            raise ValueError(f"{md_path.name}: missing frontmatter field: {k}")

    author = AUTHORS.get(fm.get("authorSlug", DEFAULT_AUTHOR), AUTHORS[DEFAULT_AUTHOR])

    body_md = strip_h1(body_md)
    body_md = strip_toc_section(body_md)
    body_md = strip_legacy_related(body_md)
    faq_items, body_md = extract_faq(body_md)
    body_md = convert_custom_blocks(body_md)
    body_md = auto_anchor_h2(body_md)

    md = md_lib.Markdown(
        extensions=["tables", "fenced_code", "attr_list"],
        output_format="html5",
    )
    body_html = md.convert(body_md)
    body_html = body_html.replace("<!--MMFAQ-->", render_faq_cards(faq_items))

    # Ни один ::: не должен пережить конвертацию. Раньше однострочный
    # «::: cta /coach "…" :::» и неподдержанный «::: callout» уезжали на сайт
    # сырым текстом и висели там незамеченными.
    leak = re.search(r":::.*", body_html)
    if leak:
        raise ValueError(
            f"{md_path.name}: незакрытый или неподдержанный ::: -блок — "
            f"«{leak.group(0)[:90]}». Блок должен быть в три строки: "
            f"открывающая ::: с типом, тело, закрывающая :::"
        )

    toc_items = extract_toc_from_html(body_html)
    toc_html = render_toc(toc_items)

    rt = fm.get("readingTime") or reading_time_min(body_md)

    canonical = f"{SITE_URL}/blog/{fm['slug']}.html"
    ld_json = json.dumps(
        build_jsonld(fm, faq_items, author, canonical),
        ensure_ascii=False, indent=4,
    )

    pub = ensure_date(fm["publishedAt"])
    pub_iso = pub.isoformat()
    pub_human = format_ru_date(pub)

    tag_label = fm.get("category") or (fm.get("tags") or ["Блог"])[0]
    og_image = resolve_og_image(fm)

    article_tags_meta = "\n".join(
        f'    <meta property="article:tag" content="{html_escape(t)}">'
        for t in fm.get("tags", [])
    )

    related_html = render_related(fm, all_meta)
    products_html = render_products(fm.get("relatedProducts") or [])

    author_card = (
        '<aside class="article__author-card">\n'
        f'                <div class="article__author-card-photo" style="background: url(\'{author["avatar"]}\') center/cover, var(--violet-100);" aria-hidden="true"></div>\n'
        '                <div class="article__author-card-body">\n'
        f'                    <div class="article__author-card-name">{html_escape(author["name"])}</div>\n'
        f'                    <div class="article__author-card-role">{html_escape(author["longRole"])}</div>\n'
        f'                    <p class="article__author-card-text">{html_escape(author["bio"])}</p>\n'
        '                </div>\n'
        '            </aside>'
    )

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html_escape(fm["title"])} — МакМагия</title>
    <meta name="description" content="{html_escape(fm["description"])}">
    <link rel="canonical" href="{canonical}">
    <meta name="robots" content="index, follow, max-image-preview:large">
    <meta name="theme-color" content="#7c3aed">

    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="512x512" href="/icon-512.png">

    <meta property="og:type" content="article">
    <meta property="og:site_name" content="МакМагия">
    <meta property="og:locale" content="ru_RU">
    <meta property="og:url" content="{canonical}">
    <meta property="og:title" content="{html_escape(fm["title"])}">
    <meta property="og:description" content="{html_escape(fm["description"])}">
    <meta property="og:image" content="{og_image}">
    <meta property="article:published_time" content="{pub_iso}">
    <meta property="article:author" content="{html_escape(author["name"])}">
{article_tags_meta}

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{html_escape(fm["title"])}">
    <meta name="twitter:description" content="{html_escape(fm["description"])}">
    <meta name="twitter:image" content="{og_image}">

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/styles.css">

    <script type="application/ld+json">
{ld_json}
    </script>
</head>
<body>

{HEADER_HTML}

<main>
    <div class="reading-progress" aria-hidden="true"><div class="reading-progress__fill"></div></div>

    <section class="article-hero">
        <div class="article-hero__inner">
            <nav class="breadcrumb" aria-label="Хлебные крошки">
                <a href="/">Главная</a>
                <span class="breadcrumb__sep">›</span>
                <a href="/blog/">Блог</a>
                <span class="breadcrumb__sep">›</span>
                <span class="breadcrumb__current">{html_escape(fm["title"])}</span>
            </nav>

            <div class="article__tag">{html_escape(tag_label)}</div>
            <h1 class="article-hero__title">{html_escape(fm["title"])}</h1>
            <p class="article-hero__lead">{html_escape(fm["description"])}</p>

            <div class="article-hero__meta">
                <div class="article-hero__author">
                    <div class="article-hero__avatar" style="background: url('{author["avatar"]}') center/cover, var(--violet-100);" aria-hidden="true"></div>
                    <div class="article-hero__author-info">
                        <span class="article-hero__author-name">{html_escape(author["name"])}</span>
                        <span class="article-hero__author-role">{html_escape(author["role"])}</span>
                    </div>
                </div>
                <div class="article-hero__dates">
                    <time datetime="{pub_iso}">{pub_human}</time>
                    <span class="article-hero__dates-sep" aria-hidden="true"></span>
                    <span>{rt} минут чтения</span>
                </div>
            </div>
        </div>
    </section>

    <section class="article-body-wrap">
        <div class="article-body-wrap__inner">

            {toc_html}

            <article class="article__body article__body--rich">
{body_html}
            </article>

            {products_html}

            {author_card}

            {related_html}

        </div>
    </section>
</main>

{FOOTER_HTML}

<script src="/script.js"></script>
</body>
</html>
"""


def render_hub(metas):
    sorted_meta = sorted(metas, key=lambda m: str(m["publishedAt"]), reverse=True)
    cards_html_parts = []

    if not sorted_meta:
        cards_html_parts.append(
            '<p style="text-align:center; color: var(--ink-60); padding: 40px 0;">Статьи скоро появятся.</p>'
        )
    else:
        first = sorted_meta[0]
        cards_html_parts.append('<h2 class="blog-hub-v2__section-title">Свежее</h2>')
        cards_html_parts.append(render_featured_card(first))
        rest = sorted_meta[1:]
        if rest:
            cards_html_parts.append('<h2 class="blog-hub-v2__section-title" style="margin-top: 56px;">Ещё статьи</h2>')
            cards_html_parts.append('<div class="blog-soon-grid">')
            for m in rest:
                cards_html_parts.append(render_regular_card(m))
            cards_html_parts.append('</div>')

    cards_html = "\n        ".join(cards_html_parts)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Блог МакМагии — психология, метафорические карты, арт-терапия</title>
    <meta name="description" content="Статьи Екатерины Каменской и редакции МакМагии о метафорических картах, арт-терапии, психологии и AI-инструментах для специалистов и для самопознания.">
    <link rel="canonical" href="https://macmagia.ru/blog/">
    <meta name="robots" content="index, follow, max-image-preview:large">
    <meta name="theme-color" content="#7c3aed">

    <link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="512x512" href="/icon-512.png">

    <meta property="og:type" content="website">
    <meta property="og:site_name" content="МакМагия">
    <meta property="og:locale" content="ru_RU">
    <meta property="og:url" content="https://macmagia.ru/blog/">
    <meta property="og:title" content="Блог МакМагии — психология, метафорические карты, арт-терапия">
    <meta property="og:description" content="Статьи о метафорических картах, арт-терапии, психологии и AI-инструментах.">
    <meta property="og:image" content="https://macmagia.ru/about.jpg">

    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Блог МакМагии">
    <meta name="twitter:description" content="Статьи о метафорических картах, арт-терапии, психологии и AI-инструментах.">
    <meta name="twitter:image" content="https://macmagia.ru/about.jpg">

    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/styles.css">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@graph": [
        {{"@type": "Blog", "@id": "https://macmagia.ru/blog/#blog",
          "name": "Блог МакМагии",
          "description": "Статьи о метафорических картах, арт-терапии, психологии и AI-инструментах.",
          "url": "https://macmagia.ru/blog/",
          "inLanguage": "ru-RU",
          "publisher": {{ "@id": "https://macmagia.ru/#organization" }}}},
        {{"@type": "BreadcrumbList", "itemListElement": [
          {{ "@type": "ListItem", "position": 1, "name": "Главная", "item": "https://macmagia.ru/" }},
          {{ "@type": "ListItem", "position": 2, "name": "Блог" }}
        ]}}
      ]
    }}
    </script>
</head>
<body>

{HEADER_HTML}

<main class="blog-hub-v2">
    <section class="blog-hub-v2__hero">
        <div class="blog-hub-v2__hero-inner">
            <nav class="breadcrumb" aria-label="Хлебные крошки">
                <a href="/">Главная</a>
                <span class="breadcrumb__sep">›</span>
                <span class="breadcrumb__current">Блог</span>
            </nav>
            <div class="blog-hub-v2__hero-tag">Блог МакМагии</div>
            <h1 class="blog-hub-v2__title">Статьи о картах, психологии и работе с собой</h1>
            <p class="blog-hub-v2__lead">Метафорические карты, арт-терапия, психология и AI-инструменты — для практикующих специалистов и для тех, кто хочет глубже понять себя. Пишет Екатерина Каменская и редакция МакМагии.</p>
        </div>
    </section>

    <div class="blog-hub-v2__container">
        {cards_html}
    </div>
</main>

{FOOTER_HTML}

<script src="/script.js"></script>
</body>
</html>
"""


def render_featured_card(meta):
    emoji = meta.get("emoji", "📖")
    gradient = meta.get("coverGradient", 1)
    tag = meta.get("category") or (meta.get("tags") or ["Статья"])[0]
    return (
        f'<a href="/blog/{meta["slug"]}.html" class="blog-card blog-card--featured">\n'
        f'            <div class="blog-card__cover blog-card__cover--{gradient}" aria-hidden="true">\n'
        f'                <span class="blog-card__emoji">{emoji}</span>\n'
        f'            </div>\n'
        f'            <div class="blog-card__body">\n'
        f'                <div class="blog-card__meta">\n'
        f'                    <span class="blog-card__tag">{html_escape(tag)}</span>\n'
        f'                    <time class="blog-card__date" datetime="{meta["pub_iso"]}">{meta["pub_human"]}</time>\n'
        f'                </div>\n'
        f'                <h3 class="blog-card__title">{html_escape(meta["title"])}</h3>\n'
        f'                <p class="blog-card__excerpt">{html_escape(meta["description"])}</p>\n'
        f'                <span class="blog-card__readmore">Читать статью →</span>\n'
        f'            </div>\n'
        f'        </a>'
    )


def render_regular_card(meta):
    emoji = meta.get("emoji", "📖")
    gradient = meta.get("coverGradient", 1)
    tag = meta.get("category") or (meta.get("tags") or ["Статья"])[0]
    return (
        f'<a href="/blog/{meta["slug"]}.html" class="blog-card">\n'
        f'                <div class="blog-card__cover blog-card__cover--{gradient}" aria-hidden="true">\n'
        f'                    <span class="blog-card__emoji">{emoji}</span>\n'
        f'                </div>\n'
        f'                <div class="blog-card__body">\n'
        f'                    <div class="blog-card__meta">\n'
        f'                        <span class="blog-card__tag">{html_escape(tag)}</span>\n'
        f'                        <time class="blog-card__date" datetime="{meta["pub_iso"]}">{meta["pub_human"]}</time>\n'
        f'                    </div>\n'
        f'                    <h3 class="blog-card__title">{html_escape(meta["title"])}</h3>\n'
        f'                    <p class="blog-card__excerpt">{html_escape(meta["description"])}</p>\n'
        f'                    <span class="blog-card__readmore">Читать →</span>\n'
        f'                </div>\n'
        f'            </a>'
    )


def update_landing_latest(metas, limit=6):
    """Блок «Свежее в блоге» на главной.

    Нужен не для красоты: до него с главной не было ни одной прямой ссылки на
    статью — все они лежали на глубине двух кликов за /blog/, и краулер молодого
    домена до них почти не доходил (GSC: «Обнаружена, не проиндексирована»).
    Перестраивается при каждой сборке между маркерами LATEST_POSTS.
    """
    index = ROOT / "index.html"
    if not index.exists():
        return 0
    text = index.read_text(encoding="utf-8")
    if "<!-- LATEST_POSTS:START -->" not in text:
        return 0

    # свежие сначала, но не больше двух из одной рубрики — иначе блок
    # вырождается в шесть подряд «Медитаций» из одного батча
    ordered = sorted(metas, key=lambda m: str(m["publishedAt"]), reverse=True)
    latest, per_cat = [], {}
    for m in ordered:
        cat = str(m.get("category") or "Блог")
        if per_cat.get(cat, 0) >= 2:
            continue
        per_cat[cat] = per_cat.get(cat, 0) + 1
        latest.append(m)
        if len(latest) == limit:
            break
    cards = []
    for m in latest:
        cover = resolve_og_image(m).replace(SITE_URL, "")
        date = m.get("pub_human") or format_ru_date(ensure_date(m["publishedAt"]))
        cards.append(
            f'                <a class="latest-card" href="/blog/{m["slug"]}.html">\n'
            f'                    <img class="latest-card__img" src="{cover}" alt="" width="480" height="270" loading="lazy">\n'
            f'                    <div class="latest-card__body">\n'
            f'                        <div class="latest-card__meta">'
            f'<span class="blog-card__tag">{html_escape(str(m.get("category") or "Блог"))}</span>'
            f'<span class="blog-card__date">{date}</span></div>\n'
            f'                        <h3 class="latest-card__title">{html_escape(str(m["title"]))}</h3>\n'
            f'                    </div>\n'
            f'                </a>'
        )
    block = (
        "<!-- LATEST_POSTS:START -->\n"
        '            <div class="latest-grid">\n'
        + "\n".join(cards)
        + "\n            </div>\n            <!-- LATEST_POSTS:END -->"
    )
    text = re.sub(
        r"<!-- LATEST_POSTS:START -->.*?<!-- LATEST_POSTS:END -->",
        lambda _: block,
        text,
        flags=re.DOTALL,
    )
    index.write_text(text, encoding="utf-8")
    return len(latest)


# ---------- RSS для Дзена ----------
# Дзен импортирует материалы по RSS: канал настраивается один раз, дальше
# статьи уезжают туда сами в том же ритме, что и на сайт.
# RSS_TEASER_PARAS = 0 — отдавать полный текст (Дзен так работает лучше всего);
# число N — отдать первые N абзацев и ссылку «продолжение на сайте».
RSS_TEASER_PARAS = 0
RSS_LIMIT = 50

RFC822_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
RFC822_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def rfc822(d):
    """Дата в формате RSS. Собираем вручную: strftime зависит от локали."""
    return (f"{RFC822_DAYS[d.weekday()]}, {d.day:02d} {RFC822_MONTHS[d.month - 1]} "
            f"{d.year} 09:00:00 +0300")


def rss_body_html(md_path):
    """Тело статьи для ленты: без оглавления, CTA-кнопок и карточек продуктов —
    в Дзене они не нужны и всё равно вырезаются. Ссылки — абсолютные."""
    raw = md_path.read_text(encoding="utf-8")
    fm, body_md = parse_frontmatter(raw)

    body_md = strip_h1(body_md)
    body_md = strip_toc_section(body_md)
    body_md = strip_legacy_related(body_md)
    faq_items, body_md = extract_faq(body_md)

    # промо-блоки вырезаем целиком, цитаты превращаем в blockquote
    body_md = re.sub(r':::\s*cta\s+\S+\s+"[^"]+"\s*\n.+?\n:::\s*', "\n\n",
                     body_md, flags=re.DOTALL)
    body_md = re.sub(r":::\s*(?:pullquote|callout\s+\w+)\s*\n(.+?)\n:::\s*",
                     lambda m: f"\n\n> {m.group(1).strip()}\n\n",
                     body_md, flags=re.DOTALL)
    body_md = re.sub(r"^---\s*$", "", body_md, flags=re.MULTILINE)
    if ":::" in body_md:
        raise ValueError(f"{md_path.name}: ::: -блок не разобран для RSS")

    md = md_lib.Markdown(extensions=["tables", "fenced_code"], output_format="html5")
    html_body = md.convert(body_md)
    html_body = html_body.replace("<!--MMFAQ-->", "")

    if faq_items:
        parts = ["<h2>Частые вопросы</h2>"]
        for q, a in faq_items:
            parts.append(f"<h3>{html_escape(q)}</h3>\n<p>{render_inline_md(a)}</p>")
        html_body += "\n" + "\n".join(parts)

    if RSS_TEASER_PARAS:
        paras = re.findall(r"<p>.*?</p>", html_body, flags=re.DOTALL)
        html_body = "\n".join(paras[:RSS_TEASER_PARAS])
        html_body += (f'\n<p><a href="{SITE_URL}/blog/{fm["slug"]}.html">'
                      f'Продолжение читайте на сайте</a></p>')
    else:
        html_body += (f'\n<p><a href="{SITE_URL}/blog/{fm["slug"]}.html">'
                      f'Источник: МакМагия</a></p>')

    # относительные ссылки → абсолютные, иначе в Дзене они ведут в никуда
    html_body = re.sub(r'(href|src)="/(?!/)', rf'\1="{SITE_URL}/', html_body)
    return html_body


def update_rss(metas):
    ordered = sorted(metas, key=lambda m: str(m["publishedAt"]), reverse=True)[:RSS_LIMIT]
    items = []
    for m in ordered:
        link = f"{SITE_URL}/blog/{m['slug']}.html"
        author = AUTHORS.get(m.get("authorSlug", DEFAULT_AUTHOR), AUTHORS[DEFAULT_AUTHOR])
        items.append(f"""    <item>
      <title>{html_escape(str(m["title"]))}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{link}</guid>
      <pubDate>{rfc822(ensure_date(m["publishedAt"]))}</pubDate>
      <author>{html_escape(author["name"])}</author>
      <category>{html_escape(str(m.get("category") or "Психология"))}</category>
      <description>{html_escape(str(m["description"]))}</description>
      <enclosure url="{resolve_og_image(m)}" type="image/jpeg" length="0"/>
      <content:encoded><![CDATA[{rss_body_html(m["__path"])}]]></content:encoded>
    </item>""")

    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>МакМагия — блог о психологии и арт-терапии</title>
    <link>{SITE_URL}/blog/</link>
    <description>Разборы, техники и упражнения по психологии, арт-терапии и метафорическим картам.</description>
    <language>ru</language>
{chr(10).join(items)}
  </channel>
</rss>
"""
    (ROOT / "rss.xml").write_text(feed, encoding="utf-8")
    return len(items)


def update_sitemap(metas, today):
    text = SITEMAP.read_text(encoding="utf-8")
    text = re.sub(
        r"\s*<url>\s*<loc>https://macmagia\.ru/blog/[^<]*</loc>.*?</url>",
        "",
        text,
        flags=re.DOTALL,
    )
    parts = [
        '  <url>',
        '    <loc>https://macmagia.ru/blog/</loc>',
        f'    <lastmod>{today}</lastmod>',
        '    <changefreq>weekly</changefreq>',
        '    <priority>0.8</priority>',
        '  </url>',
    ]
    for m in metas:
        lastmod = str(m.get("updatedAt") or m["publishedAt"])
        parts.extend([
            '  <url>',
            f'    <loc>https://macmagia.ru/blog/{m["slug"]}.html</loc>',
            f'    <lastmod>{lastmod}</lastmod>',
            '    <changefreq>monthly</changefreq>',
            '    <priority>0.7</priority>',
            '  </url>',
        ])
    block = "\n".join(parts) + "\n"
    # Drop blank lines just before </urlset> so the sitemap stays tidy
    text = re.sub(r"\n+</urlset>\s*$", "\n</urlset>\n", text)
    text = text.replace("</urlset>", block + "</urlset>")
    SITEMAP.write_text(text, encoding="utf-8")


def check_eso(md_text, whitelist=None):
    """Find forbidden esoteric terms in md text.

    whitelist: optional list of terms (case-insensitive) that are explicitly
    allowed for this article (e.g. an отстраивающий-context article about
    differences between МАК and Таро). See agent-task.md §2.3.
    """
    wl = {t.lower() for t in (whitelist or [])}
    hits = []
    for m in FORBIDDEN_RE.finditer(md_text):
        token = m.group(0).lower()
        if any(allowed in token or token in allowed for allowed in wl):
            continue
        hits.append(m.group(0))
    return hits


def collect_meta(md_path):
    raw = md_path.read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(raw)
    pub = ensure_date(fm["publishedAt"])
    fm["pub_iso"] = pub.isoformat()
    fm["pub_human"] = format_ru_date(pub)
    fm["__path"] = md_path
    return fm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-eso", action="store_true",
                        help="bypass the esoteric-terms gate (don't normally use this)")
    args = parser.parse_args()

    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    md_files = sorted(ARTICLES_DIR.glob("*.md"))
    if not md_files:
        print(f"No articles in {ARTICLES_DIR}")
        return 0

    # Эзо-фильтр (с уважением к article-level esoWhitelist)
    eso_failures = []
    for p in md_files:
        raw = p.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(raw)
        whitelist = fm.get("esoWhitelist") or []
        hits = check_eso(raw, whitelist=whitelist)
        if hits:
            eso_failures.append((p, hits))

    if eso_failures and not args.allow_eso:
        print("ERROR: эзо-фильтр сработал в следующих файлах:", file=sys.stderr)
        for p, hits in eso_failures:
            unique = sorted(set(h.lower() for h in hits))
            print(f"  {p.name}: {', '.join(unique)}", file=sys.stderr)
        print("Перепишите фразы согласно docs/seo/agent-task.md §2.", file=sys.stderr)
        print("(Запустить с --allow-eso для обхода — но это плохая идея.)", file=sys.stderr)
        return 1
    elif eso_failures:
        print("WARN: эзо-фильтр найдены слова, но --allow-eso активен:")
        for p, hits in eso_failures:
            print(f"  {p.name}: {sorted(set(h.lower() for h in hits))}")

    metas = [collect_meta(p) for p in md_files]

    # Отложенная публикация: статьи с publishedAt в будущем не попадают в сборку,
    # пока не наступит их дата. Ежедневный деплой по расписанию (cron в GitHub Actions)
    # пересобирает блог и выкатывает статьи, у которых дата уже наступила — по 10 в день.
    today = datetime.date.today()
    scheduled = [m for m in metas if ensure_date(m["publishedAt"]) > today]
    for m in sorted(scheduled, key=lambda m: str(m["publishedAt"])):
        print(f"  scheduled (skip until {m['publishedAt']}): {m['slug']}")
    metas = [m for m in metas if ensure_date(m["publishedAt"]) <= today]

    # Не просто «не собирать», а снести уже лежащий HTML: файл мог остаться от
    # прошлой сборки (когда дата была в прошлом) — тогда rsync выложит его на
    # сервер и статья окажется доступна по прямой ссылке раньше срока.
    for m in scheduled:
        stale = BLOG_DIR / f"{m['slug']}.html"
        if stale.exists():
            stale.unlink()
            print(f"  removed premature blog/{m['slug']}.html")
    if not metas:
        print("No articles due for publication yet.")
        return 0

    for meta in metas:
        path = meta["__path"]
        out = BLOG_DIR / f"{meta['slug']}.html"
        out.write_text(inject_metrika(render_article(path, metas)), encoding="utf-8")
        print(f"  built blog/{meta['slug']}.html")

    (BLOG_DIR / "index.html").write_text(inject_metrika(render_hub(metas)), encoding="utf-8")
    print("  built blog/index.html")

    n_rss = update_rss(metas)
    print(f"  updated rss.xml ({n_rss} материалов для Дзена)")

    n_latest = update_landing_latest(metas)
    if n_latest:
        print(f"  updated index.html (свежее в блоге: {n_latest})")

    update_sitemap(metas, datetime.date.today().isoformat())
    print("  updated sitemap.xml")

    print(f"\nDone. {len(metas)} article(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
