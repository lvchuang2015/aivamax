#!/usr/bin/env python3
"""AIvaMax Matrix CLI with a private JarveePro source adapter.

This script crawls private source pages, converts them into local Markdown,
builds a JSONL search index, and renders AIvaMax public SOP assets from
retrieved source material.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html as html_lib
import json
import os
import re
import shutil
import sys
import textwrap
import time
import warnings
from collections import Counter, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, quote, unquote, urlencode, urljoin, urlparse, urlunparse

from aivamax_artifacts import (
    build_dual_project_files,
    read_course_sop,
    scan_artifact_violations,
)
from aivamax_course import (
    render_course_grade_module_files,
    render_course_grade_public_sop,
    render_media_plan_markdown,
)
from aivamax_quality import public_export_dir_for_course, scan_course_quality
from aivamax_release import (
    render_case_plan_markdown,
    render_course_export_files,
    render_course_dashboard,
    render_course_release_files,
    render_preview_pack_files,
    render_release_demo_files,
    render_sales_pack_files,
    scan_case_plan,
)

try:
    warnings.filterwarnings(
        "ignore",
        message=r"urllib3 .* doesn't match a supported version!",
    )
    import requests
    from bs4 import BeautifulSoup
except ImportError as exc:  # pragma: no cover - exercised by users without deps
    missing = getattr(exc, "name", "a required package")
    print(f"Missing dependency: {missing}", file=sys.stderr)
    print("Install with: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)


ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "seeds.json"
DEFAULT_BRAND_CONFIG = ROOT / "config" / "brand_config.json"
DEFAULT_DATA_DIR = ROOT / "data"
USER_AGENT = (
    "AIvaMaxKnowledgeAdapter/0.1 "
    "(personal research archive; contact: local-user)"
)
DEFAULT_SOURCE = "jarveepro"
MATRIX_AGENT_FLOW = [
    {
        "agent": "Intake Agent",
        "tool": "brief",
        "responsibility": "Convert the user request into a structured TaskBrief.",
    },
    {
        "agent": "Knowledge Agent",
        "tool": "evidence",
        "responsibility": "Retrieve private source context and produce a public EvidencePack.",
    },
    {
        "agent": "Platform Agent",
        "tool": "platform-playbook",
        "responsibility": "Create platform-specific playbooks for tactics, users, content paths, and course framing.",
    },
    {
        "agent": "Boundary Agent",
        "tool": "boundary-brief",
        "responsibility": "Translate policy references and operating experience into green/yellow/red execution boundaries.",
    },
    {
        "agent": "SOP Agent",
        "tool": "sop",
        "responsibility": "Compile source-backed AIvaMax public and internal SOP layers.",
    },
    {
        "agent": "Risk Agent",
        "tool": "risk-audit",
        "responsibility": "Audit account, action, and execution risk before use.",
    },
    {
        "agent": "Memory Agent",
        "tool": "project",
        "responsibility": "Save the project package into AIvaMax Obsidian Matrix.",
    },
    {
        "agent": "Course Agent",
        "tool": "course",
        "responsibility": "Turn the public project package into a course module.",
    },
    {
        "agent": "Brand Auditor",
        "tool": "brand-audit",
        "responsibility": "Check public outputs for private source leakage.",
    },
    {
        "agent": "Artifact Auditor",
        "tool": "artifact-audit",
        "responsibility": "Verify artifact manifests and keep internal-only files out of courses and public exports.",
    },
    {
        "agent": "Quality Auditor",
        "tool": "quality-audit",
        "responsibility": "Verify course depth, teaching assets, assignments, and public/private wording.",
    },
]
requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
SKIP_TAGS = [
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "canvas",
    "form",
    "button",
]
SKIP_SELECTORS = [
    "header",
    "footer",
    "nav",
    ".header-nav",
    ".preloader",
    ".mobile-nav",
    ".mobile-nav-toggle",
    ".breadcrumbs",
    ".copyright",
    ".credits",
    ".back-to-top",
    "#header",
]


@dataclass
class PageRecord:
    id: str
    url: str
    title: str
    category: str
    summary: str
    text: str
    headings: list[str]
    links: list[str]
    fetched_at: str
    status_code: int
    content_hash: str
    raw_path: str
    note_path: str


def now_iso() -> str:
    return dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        config = json.load(f)
    if not config.get("seeds"):
        raise ValueError(f"No seeds found in {path}")
    if not config.get("allowed_domains"):
        raise ValueError(f"No allowed_domains found in {path}")
    return config


def default_brand_config() -> dict:
    return {
        "public_brand": "AIvaMax",
        "default_source": DEFAULT_SOURCE,
        "forbidden_public_terms": [
            "JarveePro",
            "jarveepro",
            "jarveepro.com",
            "blog.jarveepro.com",
            "source_url:",
            "source_note:",
            "raw_path:",
            "note_path:",
        ],
        "source_adapters": {
            DEFAULT_SOURCE: {
                "source_brand": "JarveePro",
                "visibility": "internal_only",
                "role": "oem_knowledge_source",
            }
        },
        "capability_map": {
            "JarveePro Account Manager": "AIvaMax Account Asset Manager",
            "JarveePro Campaign Manager": "AIvaMax Automation Orchestrator",
            "JarveePro AI Monitor": "AIvaMax Real-Time Signal Monitor",
            "JarveePro Content Explorer": "AIvaMax Content Intelligence Engine",
            "JarveePro Scheduler": "AIvaMax Publishing Scheduler",
            "JarveePro Developer API": "AIvaMax Integration API",
            "JarveePro Warm-Up": "AIvaMax Account Trust Warm-Up",
            "JarveePro Instagram Warm-Up": "AIvaMax Instagram Trust Warm-Up",
        },
    }


def load_brand_config(path: Path | None = None) -> dict:
    config = default_brand_config()
    path = path or DEFAULT_BRAND_CONFIG
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            loaded = json.load(f)
        for key, value in loaded.items():
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                merged = dict(config[key])
                merged.update(value)
                config[key] = merged
            else:
                config[key] = value
    return config


def public_brand(brand_config: dict) -> str:
    return brand_config.get("public_brand", "AIvaMax")


def ensure_dirs(data_dir: Path) -> None:
    for child in ["raw", "pages", "reports", "obsidian"]:
        (data_dir / child).mkdir(parents=True, exist_ok=True)


def clean_ws(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "")
    return value.strip()


def slugify(value: str, fallback: str = "page", max_len: int = 80) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value, flags=re.I)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        value = fallback
    return value[:max_len].strip("-") or fallback


def sha1_text(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8", errors="ignore")).hexdigest()


def normalize_url(href: str, base: str | None = None) -> str | None:
    if not href:
        return None
    href = html_lib.unescape(href.strip())
    if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
        return None

    joined = urljoin(base or "", href)
    parsed = urlparse(joined)
    if parsed.scheme not in {"http", "https"}:
        return None

    host = parsed.netloc.lower()
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    path = quote(unquote(path), safe="/-._~(),;:@!$&*=+")
    if host == "jarveepro.com":
        host = "www.jarveepro.com"
    if host == "www.jarveepro.com" and path.lower().startswith("/home/"):
        host = "blog.jarveepro.com"
    scheme = "https" if host.endswith("jarveepro.com") else parsed.scheme

    query_pairs = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        low_key = key.lower()
        if low_key.startswith("utm_") or low_key in {"fbclid", "gclid"}:
            continue
        if value == "":
            continue
        query_pairs.append((key, value))
    query = urlencode(sorted(query_pairs))
    normalized = urlunparse((scheme, host, path, "", query, ""))

    if normalized.endswith("/") and path != "/":
        normalized = normalized[:-1]
    return normalized


def is_allowed_url(url: str, allowed_domains: set[str], exclude_patterns: list[str]) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host == "jarveepro.com":
        host = "www.jarveepro.com"
    if host not in allowed_domains:
        return False
    low = url.lower()
    if any(pattern.lower() in low for pattern in exclude_patterns):
        return False
    suffix = Path(parsed.path).suffix.lower()
    if suffix and suffix not in {".html", ".htm", ".aspx"}:
        return False
    return True


def classify_url(url: str, title: str = "") -> str:
    low = url.lower()
    text = title.lower()
    host = urlparse(url).netloc.lower()
    if "knowledgebaselist" in low:
        return "knowledge-index"
    if "knowledgesingle" in low or "/knowledge/" in low or "knowledge base" in text:
        return "knowledge"
    if "/home/blog" in low:
        return "blog-index"
    if "/social-media-marketing-tips/" in low or "/blog/" in low or "blog" in text:
        return "blog"
    if "features.html" in low or "features" in text:
        return "feature"
    if "pricing" in low:
        return "pricing"
    if host == "blog.jarveepro.com":
        return "blog"
    if low.rstrip("/") in {"https://www.jarveepro.com", "https://www.jarveepro.com/"}:
        return "home"
    return "site"


def best_title(soup: BeautifulSoup, url: str) -> str:
    candidates: list[str] = []
    for selector in [
        'meta[property="og:title"]',
        'meta[name="twitter:title"]',
        "title",
        "h1",
        "h2",
    ]:
        node = soup.select_one(selector)
        if not node:
            continue
        if node.name == "meta":
            text = node.get("content", "")
        else:
            text = node.get_text(" ", strip=True)
        text = clean_ws(text)
        if text:
            candidates.append(text)
    if candidates:
        title = candidates[0]
        title = re.sub(r"\s+-\s+JARVEEPRO\s*$", "", title, flags=re.I)
        return clean_ws(title)
    parsed = urlparse(url)
    return Path(parsed.path).stem or parsed.netloc


def extract_links(soup: BeautifulSoup, url: str, html: str = "") -> list[str]:
    links: set[str] = set()
    for node in soup.find_all("a", href=True):
        normalized = normalize_url(str(node.get("href", "")), base=url)
        if normalized:
            links.add(normalized)

    # The knowledge-base index embeds hundreds of article URLs inside a
    # JavaScript data array rather than as anchors, so parse quoted URL fields.
    for match in re.finditer(
        r"""(?ix)
        \b(?:url|href|link)\s*:\s*
        ["'](?P<url>https?://[^"']+)["']
        """,
        html,
    ):
        normalized = normalize_url(match.group("url"), base=url)
        if normalized:
            links.add(normalized)
    return sorted(links)


def is_generic_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", title).strip().lower()
    return normalized in {
        "jarveepro",
        "blog",
        "knowledge base",
        "knowledge base detail",
        "home",
        "sites",
        "resources",
        "blog - jarveepro",
        "knowledge base - jarveepro",
    }


def remove_noise(soup: BeautifulSoup) -> None:
    for tag in SKIP_TAGS:
        for node in soup.find_all(tag):
            node.decompose()
    for selector in SKIP_SELECTORS:
        for node in soup.select(selector):
            node.decompose()


def choose_content_root(soup: BeautifulSoup) -> BeautifulSoup:
    for selector in [
        "main",
        "#main",
        "article",
        ".blog-details",
        ".blog-details-content",
        ".knowledge-detail",
        ".services-details-content",
        ".single-blog-content",
        ".page-banner-content",
        ".feature-area",
        ".pricing-area",
    ]:
        node = soup.select_one(selector)
        if node:
            return node
    return soup.body or soup


def dedupe_lines(lines: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    seen_window: deque[str] = deque(maxlen=12)
    for raw in lines:
        line = clean_ws(raw)
        if len(line) < 2:
            continue
        low = line.lower()
        if low in {"home", "pricing", "sites", "blog", "knowledge base", "contact us"}:
            continue
        if line in seen_window:
            continue
        cleaned.append(line)
        seen_window.append(line)
    return cleaned


def extract_text_and_headings(html: str, url: str) -> tuple[str, str, list[str], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    title = best_title(soup, url)
    links = extract_links(soup, url, html)

    remove_noise(soup)
    root = choose_content_root(soup)

    headings = []
    for node in root.find_all(["h1", "h2", "h3", "h4"]):
        text = clean_ws(node.get_text(" ", strip=True))
        if text and text not in headings:
            headings.append(text)

    low_url = url.lower()
    parsed = urlparse(url)
    if "knowledgebaselist" in low_url:
        title = "Knowledge Base Index"
    elif parsed.netloc.lower() == "www.jarveepro.com" and parsed.path in {"", "/"}:
        title = "JarveePro Home"
    elif "/home/blog" in low_url:
        title = "Blog Index" if not parsed.query else f"Blog Listing ({parsed.query})"
    elif is_generic_title(title) and headings:
        title = headings[0]

    raw_text = root.get_text("\n", strip=True)
    lines = dedupe_lines(raw_text.splitlines())
    text = "\n\n".join(lines)
    if not text:
        text = clean_ws(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))

    summary = ""
    for line in lines:
        if len(line) >= 45:
            summary = line[:420]
            break
    if not summary and lines:
        summary = lines[0][:420]
    return title, summary, headings, links


def yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_list(values: Iterable[str]) -> str:
    return "[" + ", ".join(yaml_string(v) for v in values) + "]"


def render_markdown(record: PageRecord) -> str:
    tags = ["jarveepro", f"jarveepro/{record.category}"]
    heading_text = "\n".join(f"- {h}" for h in record.headings[:30]) or "- None extracted"
    link_text = "\n".join(f"- {link}" for link in record.links[:80]) or "- None extracted"
    body = record.text.strip() or record.summary.strip()
    return f"""---
title: {yaml_string(record.title)}
source_url: {yaml_string(record.url)}
category: {yaml_string(record.category)}
fetched_at: {yaml_string(record.fetched_at)}
status_code: {record.status_code}
content_hash: {yaml_string(record.content_hash)}
tags: {yaml_list(tags)}
---

# {record.title}

Source: [{record.url}]({record.url})

Category: `{record.category}`

## Summary

{record.summary or "No summary extracted."}

## Headings

{heading_text}

## Content

{body}

## Extracted Links

{link_text}
"""


def fetch_url(session: requests.Session, url: str, timeout: int) -> tuple[int, str, str]:
    response = session.get(url, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if response.encoding is None:
        response.encoding = response.apparent_encoding
    return response.status_code, content_type, response.text


def load_existing_index(data_dir: Path) -> dict[str, dict]:
    path = data_dir / "index.jsonl"
    if not path.exists():
        return {}
    records: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                records[rec["url"]] = rec
            except (json.JSONDecodeError, KeyError):
                continue
    return records


def write_index(data_dir: Path, records: list[PageRecord], errors: list[dict]) -> None:
    records = sorted(records, key=lambda r: (r.category, r.title.lower(), r.url))
    index_path = data_dir / "index.jsonl"
    with index_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    counts = Counter(record.category for record in records)
    manifest = {
        "generated_at": now_iso(),
        "page_count": len(records),
        "category_counts": dict(sorted(counts.items())),
        "errors": errors,
    }
    with (data_dir / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def save_record(data_dir: Path, url: str, status_code: int, html: str) -> PageRecord:
    title, summary, headings, links = extract_text_and_headings(html, url)
    content_hash = sha1_text(html)
    page_id = sha1_text(url)[:12]
    slug = slugify(title, fallback="jarveepro")
    raw_rel = f"raw/{page_id}.html"
    note_rel = f"pages/{slug}-{page_id}.md"
    category = classify_url(url, title)

    record = PageRecord(
        id=page_id,
        url=url,
        title=title,
        category=category,
        summary=summary,
        text="",
        headings=headings,
        links=links,
        fetched_at=now_iso(),
        status_code=status_code,
        content_hash=content_hash,
        raw_path=raw_rel,
        note_path=note_rel,
    )
    soup = BeautifulSoup(html, "html.parser")
    remove_noise(soup)
    root = choose_content_root(soup)
    record.text = "\n\n".join(dedupe_lines(root.get_text("\n", strip=True).splitlines()))
    if not record.text:
        record.text = summary

    raw_path = data_dir / raw_rel
    raw_path.write_text(html, encoding="utf-8", errors="ignore")
    note_path = data_dir / note_rel
    note_path.write_text(render_markdown(record), encoding="utf-8")
    return record


def run_sync(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    data_dir = Path(args.data_dir)
    ensure_dirs(data_dir)

    allowed_domains = {d.lower() for d in config["allowed_domains"]}
    if "jarveepro.com" in allowed_domains:
        allowed_domains.add("www.jarveepro.com")
    exclude_patterns = list(config.get("exclude_url_patterns", []))

    existing = load_existing_index(data_dir)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    queue: deque[tuple[str, int]] = deque()
    for seed in config["seeds"]:
        normalized = normalize_url(seed)
        if normalized:
            queue.append((normalized, 0))

    visited: set[str] = set()
    records_by_url: dict[str, PageRecord] = {}
    errors: list[dict] = []

    print(f"Sync start: {len(queue)} seeds, max_pages={args.max_pages}, max_depth={args.max_depth}")
    while queue and len(visited) < args.max_pages:
        url, depth = queue.popleft()
        if url in visited:
            continue
        if depth > args.max_depth:
            continue
        if not is_allowed_url(url, allowed_domains, exclude_patterns):
            continue

        visited.add(url)
        cached = False
        try:
            old = existing.get(url)
            raw_path = data_dir / old.get("raw_path", "") if old else None
            if args.reuse_raw and raw_path and raw_path.exists():
                status_code = int(old.get("status_code", 200))
                html = raw_path.read_text(encoding="utf-8", errors="ignore")
                cached = True
            else:
                status_code, content_type, html = fetch_url(session, url, args.timeout)
                if "html" not in content_type.lower() and "<html" not in html[:500].lower():
                    print(f"skip non-html: {url}")
                    continue
            record = save_record(data_dir, url, status_code, html)
            if cached:
                changed = "cached"
            else:
                changed = "new"
                if old and old.get("content_hash") == record.content_hash:
                    changed = "same"
                elif old:
                    changed = "updated"
            records_by_url[url] = record
            print(f"[{len(visited):03d}] {changed:7s} {record.category:15s} {record.title[:78]}")

            for link in record.links:
                if link not in visited and is_allowed_url(link, allowed_domains, exclude_patterns):
                    queue.append((link, depth + 1))
        except Exception as exc:  # noqa: BLE001 - record crawl failures for review
            errors.append({"url": url, "error": str(exc), "depth": depth})
            print(f"[ERR] {url} :: {exc}", file=sys.stderr)
        if args.delay > 0 and not cached:
            time.sleep(args.delay)

    write_index(data_dir, list(records_by_url.values()), errors)
    if args.export_obsidian:
        export_args = argparse.Namespace(data_dir=str(data_dir), out=None)
        run_export_obsidian(export_args)
    print(f"Sync complete: {len(records_by_url)} pages, {len(errors)} errors")
    print(f"Index: {data_dir / 'index.jsonl'}")
    return 0 if records_by_url else 1


def load_records(data_dir: Path) -> list[dict]:
    path = data_dir / "index.jsonl"
    if not path.exists():
        raise SystemExit(f"No index found at {path}. Run: python jarveepro_cli.py sync")
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def vendor_source_root(data_dir: Path) -> Path:
    return data_dir / "obsidian" / "JarveePro" / "Vendor_Source_Docs"


def vendor_source_index_dir(data_dir: Path) -> Path:
    return data_dir / "vendor_sources"


def strip_markdown_frontmatter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                return "\n".join(lines[idx + 1:]).lstrip()
    return text


def markdown_title(text: str, fallback: str) -> str:
    for line in strip_markdown_frontmatter(text).splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return clean_ws(match.group(1))
    return fallback


def vendor_chunk_type(section: str, text: str) -> str:
    section_text = section.lower()
    haystack = f"{section}\n{text}".lower()
    if "评论模板" in section or "私信模板" in section:
        return "message_template"
    if "内容日历" in section or "calendar" in section_text:
        return "calendar"
    if "提示词" in section or "prompt" in section_text or "输出格式" in section or "总公式" in section:
        return "prompt"
    if any(term in section for term in ["账号矩阵", "平台定位", "任务类型", "推广周期", "每日执行", "项目结构", "生成规则", "执行原则"]):
        return "execution_rule"
    if "|" in text or "json" in haystack or "表" in section:
        return "table"
    if any(term in haystack for term in ["执行", "任务", "周期", "campaign", "规则", "账号矩阵"]):
        return "execution_rule"
    return "framework"


def iter_vendor_markdown_chunks(path: Path, data_dir: Path) -> list[dict]:
    raw_text = path.read_text(encoding="utf-8-sig")
    body = strip_markdown_frontmatter(raw_text)
    title = markdown_title(raw_text, path.stem)
    chunks: list[dict] = []
    current_section = title
    current_lines: list[str] = []

    def flush() -> None:
        text = "\n".join(current_lines).strip()
        if not text:
            return
        rel_path = path.relative_to(data_dir).as_posix()
        section = clean_ws(current_section)
        chunk_hash = sha1_text(f"{rel_path}\n{section}\n{text}")
        chunks.append({
            "id": f"vendor:{chunk_hash[:12]}",
            "source_type": "vendor_source_doc",
            "source_adapter": DEFAULT_SOURCE,
            "visibility": "internal_only",
            "title": title,
            "section": section,
            "category": "vendor-template",
            "chunk_type": vendor_chunk_type(section, text),
            "summary": clean_ws(text)[:280],
            "text": text,
            "headings": [section],
            "source_doc": path.name,
            "source_path": rel_path,
            "content_hash": sha1_text(text),
            "derived_brand_target": "AIvaMax",
            "fetched_at": now_iso(),
            "status_code": 200,
        })

    for line in body.splitlines():
        match = re.match(r"^(#{1,3})\s+(.+?)\s*$", line)
        if match:
            flush()
            current_section = match.group(2)
            current_lines = [line]
        else:
            current_lines.append(line)
    flush()
    return chunks


def load_vendor_records(data_dir: Path) -> list[dict]:
    path = vendor_source_index_dir(data_dir) / "index.jsonl"
    if not path.exists():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_source_records(data_dir: Path, corpus: str = "web") -> list[dict]:
    normalized = (corpus or "web").strip().lower()
    if normalized not in {"web", "vendor", "all", "auto"}:
        raise SystemExit(f"Unsupported corpus: {corpus}. Use web, vendor, all, or auto.")
    web_records: list[dict] = []
    vendor_records: list[dict] = []
    if normalized in {"web", "all", "auto"}:
        if (data_dir / "index.jsonl").exists():
            web_records = load_records(data_dir)
        elif normalized == "web":
            web_records = load_records(data_dir)
        for record in web_records:
            record.setdefault("source_corpus", "web")
    if normalized in {"vendor", "all", "auto"}:
        vendor_records = load_vendor_records(data_dir)
        for record in vendor_records:
            record.setdefault("source_corpus", "vendor")
    if normalized == "vendor":
        return vendor_records
    if normalized == "all":
        return web_records + vendor_records
    if normalized == "auto":
        return web_records + vendor_records if vendor_records else web_records
    return web_records


def run_index_vendor_source(args: argparse.Namespace) -> int:
    if args.source != DEFAULT_SOURCE:
        print(f"Unsupported source adapter: {args.source}", file=sys.stderr)
        return 2
    data_dir = Path(args.data_dir)
    source_root = Path(args.path) if args.path else vendor_source_root(data_dir)
    if not source_root.exists():
        print(f"Vendor source folder not found: {source_root}", file=sys.stderr)
        return 1
    index_dir = vendor_source_index_dir(data_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    source_docs: list[str] = []
    for path in sorted(source_root.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        chunks = iter_vendor_markdown_chunks(path, data_dir)
        if chunks:
            source_docs.append(path.name)
            records.extend(chunks)

    index_path = index_dir / "index.jsonl"
    with index_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    chunk_counts = Counter(record.get("chunk_type", "unknown") for record in records)
    manifest = {
        "generated_at": now_iso(),
        "source_adapter": DEFAULT_SOURCE,
        "source_root": str(source_root),
        "source_doc_count": len(source_docs),
        "chunk_count": len(records),
        "category_counts": {"vendor-template": len(records)},
        "chunk_type_counts": dict(sorted(chunk_counts.items())),
        "source_docs": source_docs,
    }
    (index_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    derivations = index_dir / "derivations.jsonl"
    if not derivations.exists():
        derivations.write_text("", encoding="utf-8")

    if args.json:
        print(json.dumps({
            "index_path": str(index_path),
            "manifest_path": str(index_dir / "manifest.json"),
            "derivations_path": str(derivations),
            **manifest,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Vendor source index: {index_path}")
        print(f"Indexed {len(records)} chunks from {len(source_docs)} docs.")
    return 0


def resolve_vendor_source_doc(data_dir: Path, source_doc: str) -> Path:
    candidate = Path(source_doc)
    if candidate.exists():
        return candidate
    root = vendor_source_root(data_dir)
    candidate = root / source_doc
    if candidate.exists():
        return candidate
    if not candidate.suffix:
        candidate = candidate.with_suffix(".md")
        if candidate.exists():
            return candidate
    raise SystemExit(f"Vendor source doc not found: {source_doc}")


def render_derived_aivamax_template(source_text: str, brand_config: dict, template_id: str) -> str:
    body = strip_markdown_frontmatter(source_text)
    body = redact_public_text(body, brand_config)
    body = re.sub(r"(?i)jarveepro", public_brand(brand_config), body)
    body = re.sub(r"(?i)jarveepro\.com", "internal source", body)
    body = re.sub(r"(?im)^source_path:.*$", "", body)
    body = re.sub(r"(?im)^raw_path:.*$", "", body)
    body = re.sub(r"(?im)^note_path:.*$", "", body)
    return f"""---
type: aivamax_master_template
template_id: {template_id}
public_brand: {public_brand(brand_config)}
source_corpus: internal_vendor_source
derivative_status: draft
visibility: internal
risk_level: medium
---

# {public_brand(brand_config)} Social Media Automation Master Template CN

> This is a brand-migrated draft derived from an internal vendor source document. Keep it internal until compliance review, risk rewriting, and course-structure review are complete.

{body}
"""


def run_template_derive(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    brand_config = load_brand_config(Path(args.brand_config))
    source_path = resolve_vendor_source_doc(data_dir, args.source_doc)
    template_id = args.template_id or slugify(source_path.stem.replace("JarveePro", "AIvaMax"), fallback="aivamax-template")
    out_path = Path(args.out) if args.out else data_dir / "obsidian" / "AIvaMax_Matrix" / "90_Templates" / "AIvaMax_Social_Media_Automation_Master_Template_CN.md"
    if out_path.exists() and not args.force:
        print(f"Template already exists: {out_path}. Use --force to overwrite.", file=sys.stderr)
        return 1
    content = render_derived_aivamax_template(source_path.read_text(encoding="utf-8-sig"), brand_config, template_id)
    violations = [
        term for term in ["JarveePro", "jarveepro.com", "source_path", "raw_path", "note_path"]
        if term.lower() in content.lower()
    ]
    if violations:
        print(f"Derived template still contains forbidden terms: {', '.join(sorted(set(violations)))}", file=sys.stderr)
        return 1
    if not args.dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        derivations = vendor_source_index_dir(data_dir) / "derivations.jsonl"
        derivations.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "generated_at": now_iso(),
            "source_doc": source_path.name,
            "source_hash": sha1_text(source_path.read_text(encoding="utf-8-sig")),
            "output_path": out_path.relative_to(data_dir).as_posix() if out_path.is_relative_to(data_dir) else str(out_path),
            "output_hash": sha1_text(content),
            "template_id": template_id,
            "public_brand": public_brand(brand_config),
        }
        with derivations.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    if args.json:
        print(json.dumps({
            "template_id": template_id,
            "source_doc": str(source_path),
            "output_path": str(out_path),
            "dry_run": args.dry_run,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Derived template: {out_path}")
    return 0


COURSE_FACTORY_REQUIRED_FILES = [
    "00_Module-Overview.md",
    "01_Lesson-Plan.md",
    "02_Workbook.md",
    "03_Instructor-Guide.md",
    "04_Assessment.md",
]


def safe_rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def course_factory_root(data_dir: Path) -> Path:
    return data_dir / "obsidian" / "AIvaMax_Matrix" / "70_Courses"


def resolve_course_factory_dir(data_dir: Path, course_dir: str | None = None, course: str | None = None) -> Path:
    if course_dir:
        return resolve_existing_cli_path(course_dir)
    root = course_factory_root(data_dir)
    if course:
        candidate = root / course
        if candidate.exists():
            return candidate
        raise SystemExit(f"Course folder not found: {candidate}")
    matches = sorted(root.glob("*/_V2-Module-Teaching-Pack.md"))
    if matches:
        return matches[0].parent
    candidates = []
    if root.exists():
        for candidate in sorted(root.iterdir()):
            if candidate.is_dir() and len(course_module_dirs(candidate)) >= 12:
                candidates.append(candidate)
    if candidates:
        return candidates[0]
    raise SystemExit(f"No course factory folder found under: {root}")


def course_module_dirs(course_dir: Path) -> list[Path]:
    if not course_dir.exists():
        return []
    return sorted(
        [path for path in course_dir.iterdir() if path.is_dir() and re.match(r"^\d{2}-", path.name)],
        key=lambda path: path.name,
    )


def extract_heading_block(text: str, heading: str) -> str:
    pattern = re.compile(rf"^###\s+{re.escape(heading)}\s*$", re.M)
    match = pattern.search(text)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^###\s+.+?\s*$|^##\s+Module\s+\d{2}\s+-\s+.+?\s*$", text[start:], re.M)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end].strip()


def parse_course_teaching_pack(text: str) -> list[dict]:
    body = strip_markdown_frontmatter(text)
    matches = list(re.finditer(r"^##\s+Module\s+(\d{2})\s+-\s+(.+?)\s*$", body, re.M))
    modules: list[dict] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        section = body[start:end].strip()
        number = match.group(1)
        title = clean_ws(match.group(2))
        modules.append({
            "number": number,
            "title": title,
            "section": section,
            "teaching_goal": extract_heading_block(section, "Teaching Goal"),
            "lesson_flow": extract_heading_block(section, "Lesson Flow"),
            "workbook_task": extract_heading_block(section, "Workbook Task"),
            "assessment": extract_heading_block(section, "Assessment"),
            "production_output": extract_heading_block(section, "Production Output"),
        })
    return modules


def frontmatter_for_course_file(file_type: str, brand: str, module_id: str, module_number: str, risk_level: str) -> str:
    return f"""---
type: {file_type}
public_brand: {brand}
module_id: {module_id}
module_number: {module_number}
status: draft_v2
visibility: internal
risk_level: {risk_level}
---
"""


def render_course_factory_module_files(module_dir: Path, module: dict, brand_config: dict) -> dict[str, str]:
    brand = public_brand(brand_config)
    module_id = module_dir.name
    number = module["number"]
    title = module["title"]
    risk_level = "high" if number in {"08", "11"} else "medium"
    teaching_goal = module.get("teaching_goal") or "Define the module goal, decision model, review gates, and final student output."
    lesson_flow = module.get("lesson_flow") or "| Segment | Teaching point | Instructor action |\n| --- | --- | --- |\n| 0-10 min | Introduce the module | Explain the core workflow |"
    workbook_task = module.get("workbook_task") or "Students complete the matching worksheet and submit it for review."
    assessment = module.get("assessment") or "The module passes when the student can explain the decision model, fill the worksheet, and identify review gates."
    production_output = module.get("production_output") or f"{title} Output"
    review_gate = "Human review required before public or client use." if risk_level == "high" else "Instructor review required before release."

    overview = f"""{frontmatter_for_course_file("course_module", brand, module_id, number, risk_level)}
# Module {number}: {title}

## Teaching Goal

{teaching_goal}

## Learning Outcomes

- Explain the module decision model in plain language.
- Complete the matching AIvaMax worksheet.
- Identify what is public-course content, internal SOP content, and client-delivery content.
- Apply the review gate before using the output in a real project.

## Production Output

{production_output}

## Release Boundary

{review_gate}

## Source Trace

Derived from the AIvaMax V2 module teaching pack and linked to the internal course factory manifest.
"""

    lesson = f"""{frontmatter_for_course_file("lesson_plan", brand, module_id, number, risk_level)}
# Lesson Plan - Module {number}: {title}

## Teaching Goal

{teaching_goal}

## Lesson Flow

{lesson_flow}

## Instructor Demo

Use one realistic project brief and show how this module changes the operating decision. Keep the demo focused on method, worksheet completion, and review gates.

## Public/Private Boundary

Public teaching may include frameworks, worksheets, examples, and review logic. Internal execution details stay in SOPs until they pass risk review.

## Source Trace

Derived from `_V2-Module-Teaching-Pack.md`, section `Module {number} - {title}`.
"""

    workbook = f"""{frontmatter_for_course_file("workbook", brand, module_id, number, risk_level)}
# Workbook - Module {number}: {title}

## Student Task

{workbook_task}

## Context Setup

Before filling the worksheet, define one project. Use a real or realistic product, one target audience, one primary market, one campaign duration, and one measurable business goal.

## Worksheet

| Field | Student answer | Review note |
| --- | --- | --- |
| Project context |  |  |
| Primary decision |  |  |
| Supporting evidence |  |  |
| Output draft |  |  |
| Risk or review gate |  |  |
| Next action |  |  |

## Evidence And Assumptions

| Question | Student answer |
| --- | --- |
| What evidence supports this decision? | |
| What is still an assumption? | |
| What would change the recommendation? | |
| What should not be shown in a public lesson or client document? | |
| Who approves the final output? | |

## Review Checklist

- The answer names a specific audience and goal.
- The worksheet is filled with project-specific details, not generic wording.
- Any claim about results, reach, leads, or conversion is marked as observed, estimated, or illustrative.
- Sensitive communication or high-risk execution includes a human review owner.
- The final output can be reused in a course module, SOP, or client delivery pack without exposing internal source traces.

## Submission Standard

The submission must be specific enough for another operator or instructor to review without asking for missing context.
"""

    instructor = f"""{frontmatter_for_course_file("instructor_guide", brand, module_id, number, risk_level)}
# Instructor Guide - Module {number}: {title}

## Facilitation Notes

- Start from the project brief, not from the tool or task list.
- Keep students focused on the decision model and final output.
- Ask students to explain why their output is appropriate for the audience, channel, and risk level.
- Require a review owner when the output affects client communication, public claims, or follow-up messaging.

## Discussion Prompts

- What information is missing from the project brief?
- Which assumption has the highest impact on this module?
- What should remain internal-only?
- What would make this output ready for client delivery?

## Risk Gate

{review_gate}

## Source Trace

Use the course factory manifest for internal traceability. Do not expose internal source traces in public course exports.
"""

    assessment_file = f"""{frontmatter_for_course_file("assessment", brand, module_id, number, risk_level)}
# Assessment - Module {number}: {title}

## Criteria

{assessment}

## Rubric

| Criterion | Pass condition |
| --- | --- |
| Clarity | The output explains the decision and the next action. |
| Fit | The output matches the project goal, audience, platform, and cycle. |
| Evidence | Key assumptions are visible and reviewable. |
| Boundary | Public, internal, client, and sales-preview use are not mixed. |
| Risk | Sensitive claims or communication include human review. |

## Pass/Revise Decision

- `pass`: ready for the next course or delivery step.
- `revise`: missing context, unclear assumptions, or weak review gate.
- `blocked`: source exposure, unsupported claims, or high-risk communication without review.
"""

    files = {
        "00_Module-Overview.md": overview,
        "01_Lesson-Plan.md": lesson,
        "02_Workbook.md": workbook,
        "03_Instructor-Guide.md": instructor,
        "04_Assessment.md": assessment_file,
    }
    return {name: redact_public_text(content, brand_config) for name, content in files.items()}


def append_course_factory_derivations(data_dir: Path, records: list[dict]) -> None:
    if not records:
        return
    derivations = vendor_source_index_dir(data_dir) / "derivations.jsonl"
    derivations.parent.mkdir(parents=True, exist_ok=True)
    with derivations.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def write_course_factory_manifest(course_dir: Path, data_dir: Path, modules: list[dict], written: list[Path], brand_config: dict) -> Path:
    module_entries = []
    for module_dir in course_module_dirs(course_dir):
        number = module_dir.name[:2]
        module_info = next((item for item in modules if item["number"] == number), {})
        module_entries.append({
            "module_id": module_dir.name,
            "module_number": number,
            "title": module_info.get("title", module_dir.name),
            "risk_level": "high" if number in {"08", "11"} else "medium",
            "files": [
                {
                    "name": name,
                    "path": safe_rel(module_dir / name, data_dir),
                    "exists": (module_dir / name).exists(),
                    "visibility": "internal",
                    "source_section": f"Module {number}",
                }
                for name in COURSE_FACTORY_REQUIRED_FILES
            ],
        })
    manifest = {
        "generated_at": now_iso(),
        "public_brand": public_brand(brand_config),
        "course_name": course_dir.name,
        "course_dir": safe_rel(course_dir, data_dir),
        "teaching_pack": safe_rel(course_dir / "_V2-Module-Teaching-Pack.md", data_dir),
        "module_count": len(module_entries),
        "required_files_per_module": COURSE_FACTORY_REQUIRED_FILES,
        "written_files": [safe_rel(path, data_dir) for path in written],
        "modules": module_entries,
    }
    path = course_dir / "course_factory_manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def build_course_factory_files(
    data_dir: Path,
    course_dir: Path,
    teaching_pack: Path,
    brand_config: dict,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    if not teaching_pack.exists():
        raise FileNotFoundError(f"Teaching pack not found: {teaching_pack}")
    modules = parse_course_teaching_pack(teaching_pack.read_text(encoding="utf-8", errors="ignore"))
    if len(modules) < 12:
        raise ValueError(f"Teaching pack has only {len(modules)} module sections; expected 12.")
    module_dirs = {path.name[:2]: path for path in course_module_dirs(course_dir)}
    written: list[Path] = []
    trace_records: list[dict] = []
    for module in modules:
        module_dir = module_dirs.get(module["number"])
        if not module_dir:
            module_dir = course_dir / f"{module['number']}-{slugify(module['title'], 'module')}"
            if not dry_run:
                module_dir.mkdir(parents=True, exist_ok=True)
        files = render_course_factory_module_files(module_dir, module, brand_config)
        for name, content in files.items():
            path = module_dir / name
            if path.exists() and not force:
                continue
            if not dry_run:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            written.append(path)
            trace_records.append({
                "generated_at": now_iso(),
                "derivation_type": "course_factory_module_file",
                "source_corpus": "course_factory",
                "source_file": safe_rel(teaching_pack, data_dir),
                "source_section": f"Module {module['number']} - {module['title']}",
                "output_path": safe_rel(path, data_dir),
                "output_hash": sha1_text(content),
                "visibility": "internal",
                "public_brand": public_brand(brand_config),
                "risk_level": "high" if module["number"] in {"08", "11"} else "medium",
            })
    manifest_path = course_dir / "course_factory_manifest.json"
    if not dry_run:
        manifest_path = write_course_factory_manifest(course_dir, data_dir, modules, written, brand_config)
        append_course_factory_derivations(data_dir, trace_records)
    return {
        "course_dir": safe_rel(course_dir, data_dir),
        "teaching_pack": safe_rel(teaching_pack, data_dir),
        "module_sections": len(modules),
        "written_count": len(written),
        "manifest_path": safe_rel(manifest_path, data_dir),
        "dry_run": dry_run,
    }


def run_course_factory_build(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    brand_config = load_brand_config(Path(args.brand_config))
    course_dir = resolve_course_factory_dir(data_dir, args.course_dir, args.course)
    teaching_pack = resolve_existing_cli_path(args.teaching_pack) if args.teaching_pack else course_dir / "_V2-Module-Teaching-Pack.md"
    try:
        result = build_course_factory_files(
            data_dir=data_dir,
            course_dir=course_dir,
            teaching_pack=teaching_pack,
            brand_config=brand_config,
            force=args.force,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Course factory build: {course_dir}")
        print(f"Written files: {result['written_count']}")
        print(f"Manifest: {result['manifest_path']}")
    return 0


def audit_course_factory(course_dir: Path, data_dir: Path, brand_config: dict) -> dict:
    violations: list[dict] = []
    warnings_list: list[dict] = []
    module_dirs = course_module_dirs(course_dir)
    if len(module_dirs) != 12:
        violations.append({"path": safe_rel(course_dir, data_dir), "issue": "module_count", "detail": f"Expected 12 modules, found {len(module_dirs)}"})
    manifest_path = course_dir / "course_factory_manifest.json"
    if not manifest_path.exists():
        violations.append({"path": safe_rel(manifest_path, data_dir), "issue": "missing_manifest", "detail": "course_factory_manifest.json is required"})
    teaching_pack = course_dir / "_V2-Module-Teaching-Pack.md"
    if not teaching_pack.exists():
        violations.append({"path": safe_rel(teaching_pack, data_dir), "issue": "missing_teaching_pack", "detail": "_V2-Module-Teaching-Pack.md is required"})
    for module_dir in module_dirs:
        number = module_dir.name[:2]
        for name in COURSE_FACTORY_REQUIRED_FILES:
            path = module_dir / name
            if not path.exists():
                violations.append({"path": safe_rel(path, data_dir), "issue": "missing_file", "detail": name})
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            if len(clean_ws(content)) < 900 and name != "00_Module-Overview.md":
                warnings_list.append({"path": safe_rel(path, data_dir), "issue": "thin_file", "detail": f"{name} is under 900 chars"})
            if name in {"01_Lesson-Plan.md", "02_Workbook.md", "04_Assessment.md"} and "Source Trace" not in content and name == "01_Lesson-Plan.md":
                warnings_list.append({"path": safe_rel(path, data_dir), "issue": "missing_source_trace", "detail": name})
        if number in {"08", "11"}:
            combined = "\n".join((module_dir / name).read_text(encoding="utf-8", errors="ignore") for name in COURSE_FACTORY_REQUIRED_FILES if (module_dir / name).exists()).lower()
            if "risk_level: high" not in combined:
                violations.append({"path": safe_rel(module_dir, data_dir), "issue": "missing_high_risk_label", "detail": "Modules 08 and 11 require high risk labels"})
            if "human review" not in combined and "review gate" not in combined:
                violations.append({"path": safe_rel(module_dir, data_dir), "issue": "missing_human_review_gate", "detail": "High-risk modules require human review wording"})
    brand_violations = scan_brand_violations(course_dir, brand_config)
    return {
        "course_dir": safe_rel(course_dir, data_dir),
        "module_count": len(module_dirs),
        "manifest_exists": manifest_path.exists(),
        "teaching_pack_exists": teaching_pack.exists(),
        "violations": violations,
        "warnings": warnings_list,
        "brand_violations": brand_violations,
        "passed": not violations and not brand_violations,
    }


def run_course_factory_audit(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    brand_config = load_brand_config(Path(args.brand_config))
    course_dir = resolve_course_factory_dir(data_dir, args.course_dir, args.course)
    result = audit_course_factory(course_dir, data_dir, brand_config)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Course factory audit: {'passed' if result['passed'] else 'failed'}")
        print(f"Modules: {result['module_count']}")
        print(f"Violations: {len(result['violations'])}")
        print(f"Warnings: {len(result['warnings'])}")
        print(f"Brand violations: {len(result['brand_violations'])}")
        for item in (result["violations"] + result["brand_violations"])[:20]:
            print(f"- {item}")
    return 0 if result["passed"] else 1


def client_pack_slug(client_code: str, industry: str, goal: str, days: int) -> str:
    base = client_code or f"{industry}-{goal}-{days}d"
    return slugify(base, fallback="client-pack", max_len=72)


def client_pack_strategy(industry: str, goal: str) -> dict:
    key = industry.lower()
    if "ecom" in key or "commerce" in key or "retail" in key:
        return {
            "platforms": [("Instagram", "30%", "Visual trust and product discovery"), ("TikTok", "30%", "Short-video demand testing"), ("Pinterest", "20%", "Visual search and long-tail intent"), ("Facebook", "10%", "Groups and retargetable community touchpoints"), ("YouTube", "10%", "Proof and product education")],
            "pillars": ["Problem/use case", "Product proof", "Buyer story", "Comparison", "Offer bridge"],
        }
    if "local" in key or "service" in key:
        return {
            "platforms": [("Facebook", "35%", "Local groups and community trust"), ("Instagram", "25%", "Visual proof and before/after content"), ("TikTok", "15%", "Local discovery and short-video reach"), ("YouTube", "15%", "Searchable service proof"), ("LinkedIn", "10%", "B2B referral and professional trust")],
            "pillars": ["Local pain", "Service proof", "FAQ", "Before/after", "Booking bridge"],
        }
    if "education" in key or "course" in key:
        return {
            "platforms": [("YouTube", "30%", "Searchable lessons and trust"), ("TikTok", "20%", "Short learning clips"), ("Instagram", "20%", "Workbook and student proof"), ("Facebook", "15%", "Community discussion"), ("LinkedIn", "15%", "Professional credibility")],
            "pillars": ["Learning pain", "Method preview", "Student proof", "FAQ", "Trial lesson bridge"],
        }
    return {
        "platforms": [("LinkedIn", "35%", "B2B trust and decision-maker discovery"), ("X", "25%", "Opinion and topical reach"), ("Reddit", "15%", "Pain discovery and community learning"), ("YouTube", "15%", "Product proof and education"), ("Facebook", "10%", "Small business community presence")],
        "pillars": ["Problem education", "Method explanation", "Proof", "Comparison", "Offer bridge"],
    }


def render_client_pack_files(args: argparse.Namespace, brand_config: dict, pack_id: str) -> dict[str, str]:
    brand = public_brand(brand_config)
    industry = args.industry
    product = args.product
    goal = args.goal
    market = args.market
    days = int(args.days)
    strategy = client_pack_strategy(industry, goal)
    platform_rows = "\n".join(f"| {name} | {weight} | {job} |" for name, weight, job in strategy["platforms"])
    pillar_rows = "\n".join(f"| {pillar} | Draft 3-5 topics tied to {product} and {market}. |" for pillar in strategy["pillars"])
    calendar_rows = []
    for day in range(1, days + 1):
        if day <= 3:
            job = "Setup and readiness"
        elif day % 7 == 0:
            job = "Weekly review"
        elif day <= 14:
            job = "Content angle testing"
        elif day <= 24:
            job = "Lead signal capture"
        else:
            job = "Conversion support and report"
        platform = strategy["platforms"][(day - 1) % len(strategy["platforms"])][0]
        calendar_rows.append(f"| Day {day} | {job} | {platform} | {product} angle {day} | Human review |")
    calendar_table = "\n".join(calendar_rows)
    brief = f"""---
type: client_delivery
public_brand: {brand}
pack_id: {pack_id}
visibility: client_delivery
status: draft
---

# Client Brief

| Field | Value |
| --- | --- |
| Pack ID | {pack_id} |
| Product | {product} |
| Industry | {industry} |
| Market | {market} |
| Primary goal | {goal} |
| Duration | {days} days |

## Scope

This pack converts the project brief into a client-readable growth plan. Internal source traces and operator-only notes are excluded.
"""
    strategy_plan = f"""---
type: strategy_plan
public_brand: {brand}
pack_id: {pack_id}
visibility: client_delivery
status: draft
---

# Strategy Plan

## Growth Hypothesis

The project should validate repeatable demand signals for {product} in {market} before scaling execution volume.

## Stages

| Stage | Days | Output |
| --- | --- | --- |
| Setup | 1-3 | Brief, assets, account roles, risk boundary |
| Test | 4-14 | Content angles and channel signals |
| Capture | 15-24 | Lead signals and response quality |
| Review | 25-{days} | Forecast, next-cycle recommendation, delivery report |
"""
    account = f"""---
type: account_matrix
public_brand: {brand}
pack_id: {pack_id}
visibility: client_delivery
status: draft
---

# Account Matrix

| Role | Job | Content focus | Owner | Risk |
| --- | --- | --- | --- | --- |
| Brand account | Authority and conversion path | Product clarity, proof, CTA | Client marketing | low |
| Expert/founder role | Trust and point of view | Industry insight and method | Client sponsor | medium |
| Product education role | Explain use cases | Demo, FAQ, workflow | Product owner | low |
| Community response role | Learn and answer | Helpful replies | Delivery owner | medium |
| Sales handoff role | Route qualified interest | Booking and next step | Sales owner | medium |
"""
    weights = f"""---
type: platform_weights
public_brand: {brand}
pack_id: {pack_id}
visibility: client_delivery
status: draft
---

# Platform Weights

| Platform | Weight | Job |
| --- | --- | --- |
{platform_rows}

## Adjustment Rule

After Day 14, move effort away from weak response channels and toward the strongest qualified signal channel.
"""
    calendar = f"""---
type: content_calendar
public_brand: {brand}
pack_id: {pack_id}
visibility: client_delivery
status: draft
---

# {days}-Day Calendar

| Day | Job | Platform | Topic | Review |
| --- | --- | --- | --- | --- |
{calendar_table}
"""
    topics = f"""---
type: topic_bank
public_brand: {brand}
pack_id: {pack_id}
visibility: client_delivery
status: draft
---

# Content Topic Bank

| Pillar | Topic direction |
| --- | --- |
{pillar_rows}

## CTA Bank

- Ask for the checklist.
- Watch the demo.
- Book a consultation.
- Reply with the main bottleneck.
- Request a project review.
"""
    review = f"""---
type: review_forecast
public_brand: {brand}
pack_id: {pack_id}
visibility: client_delivery
status: draft
---

# Review And Forecast

| Scenario | Condition | Lead signal range |
| --- | --- | --- |
| Conservative | New audience, limited proof | Low but measurable |
| Expected | Clear content and review rhythm | Repeatable signal pattern |
| Upside | Strong proof and fast follow-up | Strong signal and next-cycle scale case |

## Forecast Rule

Use ranges and assumptions. Do not present guaranteed reach, leads, sales, or revenue.
"""
    risk = f"""---
type: risk_boundary
public_brand: {brand}
pack_id: {pack_id}
visibility: client_delivery
status: draft
risk_level: medium
---

# Risk Boundary

| Area | Rule |
| --- | --- |
| Claims | Use evidence, examples, and ranges. |
| Comments | Add value and context before CTA. |
| Messages | Use opt-in, relevant, human-approved follow-up only. |
| Forecast | Present assumptions, not guarantees. |
| Source trace | Keep internal-only. |
"""
    readme = f"""---
type: client_pack_readme
public_brand: {brand}
pack_id: {pack_id}
visibility: internal
status: draft
---

# Delivery README

Files 00-07 are client-facing draft assets. This README and source trace records remain internal.
"""
    manifest = {
        "generated_at": now_iso(),
        "public_brand": brand,
        "pack_id": pack_id,
        "industry": industry,
        "product": product,
        "market": market,
        "goal": goal,
        "days": days,
        "visibility": "client_delivery",
        "files": [
            "00_Client-Brief.md",
            "01_Strategy-Plan.md",
            "02_Account-Matrix.md",
            "03_Platform-Weights.md",
            "04_Content-Calendar.md",
            "05_Content-Topic-Bank.md",
            "06_Review-Forecast.md",
            "07_Risk-Boundary.md",
            "08_Delivery-README.md",
        ],
    }
    files = {
        "00_Client-Brief.md": brief,
        "01_Strategy-Plan.md": strategy_plan,
        "02_Account-Matrix.md": account,
        "03_Platform-Weights.md": weights,
        "04_Content-Calendar.md": calendar,
        "05_Content-Topic-Bank.md": topics,
        "06_Review-Forecast.md": review,
        "07_Risk-Boundary.md": risk,
        "08_Delivery-README.md": readme,
        "manifest.json": json.dumps(manifest, ensure_ascii=False, indent=2),
    }
    return {name: redact_public_text(content, brand_config) for name, content in files.items()}


def run_client_pack_generate(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    brand_config = load_brand_config(Path(args.brand_config))
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    pack_id = client_pack_slug(args.client_code, args.industry, args.goal, int(args.days))
    out_dir = Path(args.out) if args.out else matrix_root / "50_Projects" / "Samples" / pack_id
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        print(f"Client pack already exists: {out_dir}. Use --force to overwrite.", file=sys.stderr)
        return 1
    files = render_client_pack_files(args, brand_config, pack_id)
    written = [out_dir / name for name in files]
    if not args.dry_run:
        write_named_files(out_dir, files, brand_config, force=True)
        append_course_factory_derivations(data_dir, [{
            "generated_at": now_iso(),
            "derivation_type": "client_pack_generate",
            "source_corpus": "course_factory",
            "source_file": "AIvaMax course factory templates",
            "output_path": safe_rel(out_dir, data_dir),
            "visibility": "client_delivery",
            "public_brand": public_brand(brand_config),
            "pack_id": pack_id,
        }])
    violations = [] if args.dry_run else scan_brand_violations(out_dir, brand_config)
    result = {
        "pack_id": pack_id,
        "out_dir": safe_rel(out_dir, data_dir),
        "files": [safe_rel(path, data_dir) for path in written],
        "brand_audit_passed": not violations,
        "violation_count": len(violations),
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Client pack: {out_dir}")
        print(f"Files: {len(written)}")
        print(f"Brand audit: {'passed' if not violations else 'failed'}")
    return 0 if not violations else 1


def simple_markdown_to_html(title: str, markdown: str) -> str:
    body: list[str] = []
    in_ul = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            if in_ul:
                body.append("</ul>")
                in_ul = False
            continue
        if stripped.startswith("#"):
            if in_ul:
                body.append("</ul>")
                in_ul = False
            level = min(len(stripped) - len(stripped.lstrip("#")), 4)
            text = stripped[level:].strip()
            body.append(f"<h{level}>{html_lib.escape(text)}</h{level}>")
        elif stripped.startswith("- "):
            if not in_ul:
                body.append("<ul>")
                in_ul = True
            body.append(f"<li>{html_lib.escape(stripped[2:].strip())}</li>")
        else:
            if in_ul:
                body.append("</ul>")
                in_ul = False
            body.append(f"<p>{html_lib.escape(stripped)}</p>")
    if in_ul:
        body.append("</ul>")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{html_lib.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 48px; line-height: 1.6; color: #1f2937; }}
    h1, h2, h3 {{ color: #111827; }}
    p, li {{ max-width: 880px; }}
  </style>
</head>
<body>
{chr(10).join(body)}
</body>
</html>
"""


def render_sales_preview_files(course_dir: Path, brand_config: dict, include_html: bool) -> dict[str, str]:
    brand = public_brand(brand_config)
    course_name = course_dir.name
    index_text = (course_dir / "_Course-Index.md").read_text(encoding="utf-8", errors="ignore") if (course_dir / "_Course-Index.md").exists() else ""
    teaching_pack = (course_dir / "_V2-Module-Teaching-Pack.md").read_text(encoding="utf-8", errors="ignore") if (course_dir / "_V2-Module-Teaching-Pack.md").exists() else ""
    modules = parse_course_teaching_pack(teaching_pack)
    module_list = "\n".join(f"- Module {item['number']}: {item['title']}" for item in modules[:12])
    first_goal = modules[0]["teaching_goal"] if modules else "Understand the AIvaMax social automation growth system."
    offer = f"""---
type: sales_preview
public_brand: {brand}
visibility: sales_preview
status: draft
---

# {course_name} - Sales Preview

## Course Promise

This course teaches a structured, review-driven way to turn social media growth work into reusable strategy, worksheets, SOPs, playbooks, and client delivery packs.

## Module Map

{module_list}

## What Buyers See

- A clear growth system map.
- Practical worksheets for intake, accounts, platforms, content, review, and delivery.
- Human review gates for sensitive communication and public claims.
- Client-ready delivery pack examples.
"""
    trial = f"""---
type: trial_lesson
public_brand: {brand}
visibility: sales_preview
status: draft
---

# Trial Lesson

## Topic

Module 01: Social Automation Growth Map

## Teaching Goal

{first_goal}

## Trial Activity

Students map one product into four blocks: audience, channel, content, and review gate.
"""
    workbook = f"""---
type: workbook_sample
public_brand: {brand}
visibility: sales_preview
status: draft
---

# Workbook Sample

| Field | Student input |
| --- | --- |
| Product or service | |
| Primary audience | |
| Main pain point | |
| Primary platform | |
| Content pillar | |
| Review gate | |
"""
    faq = f"""---
type: sales_faq
public_brand: {brand}
visibility: sales_preview
status: draft
---

# FAQ

## Is this a tool tutorial?

No. It is a course factory for building repeatable social growth systems, with tool-specific execution details kept internal unless reviewed.

## Does the course promise leads or sales?

No. It teaches planning, execution structure, review, and forecast ranges. Outcomes depend on offer, market, assets, and follow-up quality.

## Are comments and messages included?

The course teaches principles, review gates, and safe rewriting. Sensitive templates require human approval before use.
"""
    checklist = f"""---
type: delivery_checklist
public_brand: {brand}
visibility: sales_preview
status: draft
---

# Delivery Checklist

- Course module map ready.
- Workbook sample ready.
- Client delivery sample available.
- Risk boundary explained.
- No private source names or paths.
- No guaranteed outcome claims.
"""
    files = {
        "01_Course-Offer.md": offer,
        "02_Trial-Lesson.md": trial,
        "03_Workbook-Sample.md": workbook,
        "04_FAQ.md": faq,
        "05_Delivery-Checklist.md": checklist,
    }
    if include_html:
        for name, content in list(files.items()):
            files[name.replace(".md", ".html")] = simple_markdown_to_html(name.removesuffix(".md"), content)
    return {name: redact_public_text(content, brand_config) for name, content in files.items()}


def run_sales_preview_generate(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    brand_config = load_brand_config(Path(args.brand_config))
    course_dir = resolve_course_factory_dir(data_dir, args.course_dir, args.course)
    include_html = args.format in {"html", "all"}
    files = render_sales_preview_files(course_dir, brand_config, include_html)
    if args.format == "md":
        files = {name: content for name, content in files.items() if name.endswith(".md")}
    out_dir = Path(args.out) if args.out else data_dir / "obsidian" / "AIvaMax_Matrix" / "public_export" / course_dir.name / "course_factory_sales_preview"
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        print(f"Sales preview already exists: {out_dir}. Use --force to overwrite.", file=sys.stderr)
        return 1
    if not args.dry_run:
        write_named_files(out_dir, files, brand_config, force=True)
        append_course_factory_derivations(data_dir, [{
            "generated_at": now_iso(),
            "derivation_type": "sales_preview_generate",
            "source_corpus": "course_factory",
            "source_file": safe_rel(course_dir / "_V2-Module-Teaching-Pack.md", data_dir),
            "output_path": safe_rel(out_dir, data_dir),
            "visibility": "sales_preview",
            "public_brand": public_brand(brand_config),
        }])
    violations = [] if args.dry_run else scan_brand_violations(out_dir, brand_config)
    result = {
        "course_dir": safe_rel(course_dir, data_dir),
        "out_dir": safe_rel(out_dir, data_dir),
        "files": [safe_rel(out_dir / name, data_dir) for name in files],
        "brand_audit_passed": not violations,
        "violation_count": len(violations),
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Sales preview: {out_dir}")
        print(f"Files: {len(files)}")
        print(f"Brand audit: {'passed' if not violations else 'failed'}")
    return 0 if not violations else 1


def extract_h2_block(markdown: str, heading: str) -> str:
    body = strip_markdown_frontmatter(markdown)
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.M)
    match = pattern.search(body)
    if not match:
        return ""
    start = match.end()
    next_match = re.search(r"^##\s+.+?\s*$", body[start:], re.M)
    end = start + next_match.start() if next_match else len(body)
    return body[start:end].strip()


def remove_internal_course_sections(markdown: str) -> str:
    body = strip_markdown_frontmatter(markdown)
    lines = body.splitlines()
    kept: list[str] = []
    skip = False
    blocked = {"source trace", "public/private boundary", "release boundary"}
    for line in lines:
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            title = heading.group(1).strip().lower()
            skip = title in blocked
            if skip:
                continue
        if not skip:
            kept.append(line)
    return "\n".join(kept).strip()


def render_course_factory_full_export(course_dir: Path, brand_config: dict, include_html: bool) -> dict[str, str]:
    brand = public_brand(brand_config)
    course_name = course_dir.name
    modules = []
    for module_dir in course_module_dirs(course_dir):
        files = _read_existing_files(module_dir, COURSE_FACTORY_REQUIRED_FILES)
        overview = files.get("00_Module-Overview.md", "")
        title = markdown_title(overview, fallback=module_dir.name)
        output = extract_h2_block(overview, "Production Output") or "Course worksheet output"
        modules.append({
            "id": module_dir.name,
            "number": module_dir.name[:2],
            "title": title,
            "output": clean_ws(output),
            "files": files,
        })
    module_rows = "\n".join(f"| {item['number']} | {item['title']} | {item['output']} |" for item in modules)
    index_md = f"""---
type: full_course_export_index
public_brand: {brand}
visibility: public_course
status: draft
---

# {course_name} - Full Export Index

## Module Map

| No. | Module | Output |
| --- | --- | --- |
{module_rows}

## Export Contents

- `01_Student-Manual.md`
- `02_Instructor-Manual.md`
- `03_Assessment-Pack.md`
- `04_Sales-Overview.md`
"""
    student_parts = [
        f"""---
type: student_manual
public_brand: {brand}
visibility: public_course
status: draft
---

# {course_name} - Student Manual
"""
    ]
    instructor_parts = [
        f"""---
type: instructor_manual
public_brand: {brand}
visibility: instructor_private
status: draft
---

# {course_name} - Instructor Manual
"""
    ]
    assessment_parts = [
        f"""---
type: assessment_pack
public_brand: {brand}
visibility: public_course
status: draft
---

# {course_name} - Assessment Pack
"""
    ]
    for item in modules:
        files = item["files"]
        student_parts.append(f"\n# {item['title']}\n")
        for name in ["00_Module-Overview.md", "01_Lesson-Plan.md", "02_Workbook.md"]:
            if name in files:
                student_parts.append(remove_internal_course_sections(files[name]))
        instructor_parts.append(f"\n# {item['title']}\n")
        for name in ["00_Module-Overview.md", "01_Lesson-Plan.md", "03_Instructor-Guide.md"]:
            if name in files:
                instructor_parts.append(remove_internal_course_sections(files[name]))
        assessment_parts.append(f"\n# {item['title']}\n")
        if "04_Assessment.md" in files:
            assessment_parts.append(remove_internal_course_sections(files["04_Assessment.md"]))
    sales_md = f"""---
type: sales_overview
public_brand: {brand}
visibility: sales_preview
status: draft
---

# {course_name} - Sales Overview

## What This Course Delivers

This course teaches a structured social growth production system: intake, account matrix, platform weights, content calendar, lead review, naming, forecasting, risk gates, and client delivery packs.

## Module Outcomes

| No. | Outcome |
| --- | --- |
{chr(10).join(f"| {item['number']} | {item['output']} |" for item in modules)}

## Boundary

The public course teaches frameworks, worksheets, examples, and review logic. Sensitive communication and operational execution details require human approval.
"""
    files = {
        "00_Course-Index.md": index_md,
        "01_Student-Manual.md": "\n\n".join(student_parts),
        "02_Instructor-Manual.md": "\n\n".join(instructor_parts),
        "03_Assessment-Pack.md": "\n\n".join(assessment_parts),
        "04_Sales-Overview.md": sales_md,
    }
    files = {name: redact_public_text(content, brand_config) for name, content in files.items()}
    if include_html:
        for name, content in list(files.items()):
            files[name.replace(".md", ".html")] = simple_markdown_to_html(name.removesuffix(".md"), content)
    return files


def run_course_factory_export_all(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    brand_config = load_brand_config(Path(args.brand_config))
    course_dir = resolve_course_factory_dir(data_dir, args.course_dir, args.course)
    audit = audit_course_factory(course_dir, data_dir, brand_config)
    if not audit["passed"] and not args.skip_audit:
        print("Course factory audit failed. Use --skip-audit only for draft debugging.", file=sys.stderr)
        if args.json:
            print(json.dumps(audit, ensure_ascii=False, indent=2))
        return 1
    include_html = args.format in {"html", "all"}
    files = render_course_factory_full_export(course_dir, brand_config, include_html)
    if args.format == "md":
        files = {name: content for name, content in files.items() if name.endswith(".md")}
    out_dir = Path(args.out) if args.out else data_dir / "obsidian" / "AIvaMax_Matrix" / "public_export" / course_dir.name / "course_factory_full_export"
    if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
        print(f"Full course export already exists: {out_dir}. Use --force to overwrite.", file=sys.stderr)
        return 1
    if not args.dry_run:
        write_named_files(out_dir, files, brand_config, force=True)
        append_course_factory_derivations(data_dir, [{
            "generated_at": now_iso(),
            "derivation_type": "course_factory_export_all",
            "source_corpus": "course_factory",
            "source_file": safe_rel(course_dir / "course_factory_manifest.json", data_dir),
            "output_path": safe_rel(out_dir, data_dir),
            "visibility": "public_course",
            "public_brand": public_brand(brand_config),
        }])
    violations = [] if args.dry_run else scan_brand_violations(out_dir, brand_config)
    result = {
        "course_dir": safe_rel(course_dir, data_dir),
        "out_dir": safe_rel(out_dir, data_dir),
        "files": [safe_rel(out_dir / name, data_dir) for name in files],
        "audit_passed": audit["passed"],
        "brand_audit_passed": not violations,
        "violation_count": len(violations),
        "dry_run": args.dry_run,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Full course export: {out_dir}")
        print(f"Files: {len(files)}")
        print(f"Brand audit: {'passed' if not violations else 'failed'}")
    return 0 if not violations else 1


def default_course_factory_client_scenarios() -> list[dict]:
    return [
        {
            "client_code": "AI-SaaS-Pilot",
            "industry": "AI SaaS",
            "product": "AI workflow automation service",
            "market": "United States B2B",
            "goal": "lead_generation",
            "days": 30,
        },
        {
            "client_code": "Local-Service-Pilot",
            "industry": "local service",
            "product": "local service booking offer",
            "market": "United States local market",
            "goal": "appointment_generation",
            "days": 30,
        },
        {
            "client_code": "Education-Course-Pilot",
            "industry": "education course",
            "product": "online course offer",
            "market": "global Chinese-speaking audience",
            "goal": "course_sales",
            "days": 30,
        },
    ]


def normalize_course_factory_client_scenario(raw: dict, index: int) -> dict:
    scenario = {
        "client_code": raw.get("client_code") or raw.get("code") or f"Client-Pack-{index:02d}",
        "industry": raw.get("industry") or "AI SaaS",
        "product": raw.get("product") or "growth offer",
        "market": raw.get("market") or "United States",
        "goal": raw.get("goal") or "lead_generation",
        "days": int(raw.get("days") or 30),
    }
    if scenario["days"] < 1:
        raise ValueError(f"Client scenario {index} has invalid days: {scenario['days']}")
    return scenario


def load_course_factory_client_scenarios(path: str | None) -> list[dict]:
    if not path:
        return default_course_factory_client_scenarios()
    source = resolve_existing_cli_path(path)
    data = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        scenarios = data.get("scenarios") or data.get("client_packs") or data.get("clients")
    else:
        scenarios = data
    if not isinstance(scenarios, list):
        raise ValueError("Client scenarios must be a list or an object with scenarios/client_packs/clients.")
    normalized: list[dict] = []
    for index, item in enumerate(scenarios, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Client scenario {index} must be an object.")
        normalized.append(normalize_course_factory_client_scenario(item, index))
    return normalized


def render_course_factory_run_report(report: dict) -> str:
    client_rows = "\n".join(
        f"| {item['pack_id']} | {item['industry']} | {item['goal']} | {item['out_dir']} | {'pass' if item['brand_audit_passed'] else 'fail'} |"
        for item in report.get("client_packs", [])
    ) or "| - | - | - | - | - |"
    stage_rows = "\n".join(
        f"| {name} | {'pass' if value else 'fail'} |"
        for name, value in [
            ("course_factory_audit", report.get("course_factory_audit", {}).get("passed", False)),
            ("full_export_brand_audit", report.get("full_export", {}).get("brand_audit_passed", False)),
            ("sales_preview_brand_audit", report.get("sales_preview", {}).get("brand_audit_passed", False)),
            ("client_pack_brand_audit", all(item.get("brand_audit_passed") for item in report.get("client_packs", []))),
            ("matrix_artifact_audit", report.get("artifact_audit", {}).get("passed", False)),
            ("matrix_brand_audit", report.get("brand_audit", {}).get("passed", False)),
        ]
    )
    return f"""---
type: course_factory_production_run
visibility: internal
status: draft
generated_at: {report['generated_at']}
---

# Course Factory Production Run

## Summary

| Field | Value |
| --- | --- |
| Course | {report['course_name']} |
| Course directory | {report['course_dir']} |
| Overall passed | {report['passed']} |
| Dry run | {report['dry_run']} |

## Stage Gates

| Gate | Result |
| --- | --- |
{stage_rows}

## Outputs

| Output | Path |
| --- | --- |
| Full course export | {report.get('full_export', {}).get('out_dir', '')} |
| Sales preview | {report.get('sales_preview', {}).get('out_dir', '')} |
| Production report JSON | {report.get('report_json', '')} |

## Client Packs

| Pack | Industry | Goal | Path | Brand |
| --- | --- | --- | --- | --- |
{client_rows}

## Next Operating Decision

- If all gates pass, this course factory is ready for repeatable public export and sample client-pack production.
- If any gate fails, fix the specific output folder before expanding more client scenarios.
- Keep vendor source material internal and continue using source traces only inside private production records.
"""


def run_course_factory_run_all(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    brand_config = load_brand_config(Path(args.brand_config))
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    course_dir = resolve_course_factory_dir(data_dir, args.course_dir, args.course)
    build_result = None
    teaching_pack = resolve_existing_cli_path(args.teaching_pack) if args.teaching_pack else course_dir / "_V2-Module-Teaching-Pack.md"
    if args.build:
        try:
            build_result = build_course_factory_files(
                data_dir=data_dir,
                course_dir=course_dir,
                teaching_pack=teaching_pack,
                brand_config=brand_config,
                force=args.force,
                dry_run=args.dry_run,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    audit = audit_course_factory(course_dir, data_dir, brand_config)
    if not audit["passed"] and not args.skip_audit:
        print("Course factory audit failed. Use --skip-audit only for draft debugging.", file=sys.stderr)
        if args.json:
            print(json.dumps(audit, ensure_ascii=False, indent=2))
        return 1

    include_html = args.format in {"html", "all"}
    full_files = render_course_factory_full_export(course_dir, brand_config, include_html)
    sales_files = render_sales_preview_files(course_dir, brand_config, include_html)
    if args.format == "md":
        full_files = {name: content for name, content in full_files.items() if name.endswith(".md")}
        sales_files = {name: content for name, content in sales_files.items() if name.endswith(".md")}

    export_root = Path(args.export_root) if args.export_root else matrix_root / "public_export" / course_dir.name
    full_out = export_root / "course_factory_full_export"
    sales_out = export_root / "course_factory_sales_preview"
    if not args.force:
        for out_dir in [full_out, sales_out]:
            if out_dir.exists() and any(out_dir.iterdir()):
                print(f"Output already exists: {out_dir}. Use --force to overwrite.", file=sys.stderr)
                return 1

    if not args.dry_run:
        write_named_files(full_out, full_files, brand_config, force=True)
        write_named_files(sales_out, sales_files, brand_config, force=True)
        append_course_factory_derivations(data_dir, [
            {
                "generated_at": now_iso(),
                "derivation_type": "course_factory_run_all_full_export",
                "source_corpus": "course_factory",
                "source_file": safe_rel(course_dir / "course_factory_manifest.json", data_dir),
                "output_path": safe_rel(full_out, data_dir),
                "visibility": "public_course",
                "public_brand": public_brand(brand_config),
            },
            {
                "generated_at": now_iso(),
                "derivation_type": "course_factory_run_all_sales_preview",
                "source_corpus": "course_factory",
                "source_file": safe_rel(course_dir / "_V2-Module-Teaching-Pack.md", data_dir),
                "output_path": safe_rel(sales_out, data_dir),
                "visibility": "sales_preview",
                "public_brand": public_brand(brand_config),
            },
        ])

    full_violations = [] if args.dry_run else scan_brand_violations(full_out, brand_config)
    sales_violations = [] if args.dry_run else scan_brand_violations(sales_out, brand_config)

    client_results: list[dict] = []
    if not args.no_client_packs:
        try:
            scenarios = load_course_factory_client_scenarios(args.client_scenarios)
        except (json.JSONDecodeError, ValueError, FileNotFoundError) as exc:
            print(f"Client scenarios error: {exc}", file=sys.stderr)
            return 1
        client_root = Path(args.client_root) if args.client_root else matrix_root / "50_Projects" / "Samples"
        for scenario in scenarios:
            pack_args = argparse.Namespace(**scenario)
            pack_id = client_pack_slug(pack_args.client_code, pack_args.industry, pack_args.goal, int(pack_args.days))
            out_dir = client_root / pack_id
            if out_dir.exists() and any(out_dir.iterdir()) and not args.force:
                print(f"Client pack already exists: {out_dir}. Use --force to overwrite.", file=sys.stderr)
                return 1
            files = render_client_pack_files(pack_args, brand_config, pack_id)
            if not args.dry_run:
                write_named_files(out_dir, files, brand_config, force=True)
                append_course_factory_derivations(data_dir, [{
                    "generated_at": now_iso(),
                    "derivation_type": "course_factory_run_all_client_pack",
                    "source_corpus": "course_factory",
                    "source_file": "AIvaMax course factory templates",
                    "output_path": safe_rel(out_dir, data_dir),
                    "visibility": "client_delivery",
                    "public_brand": public_brand(brand_config),
                    "pack_id": pack_id,
                }])
            violations = [] if args.dry_run else scan_brand_violations(out_dir, brand_config)
            client_results.append({
                "pack_id": pack_id,
                "industry": pack_args.industry,
                "product": pack_args.product,
                "market": pack_args.market,
                "goal": pack_args.goal,
                "days": int(pack_args.days),
                "out_dir": safe_rel(out_dir, data_dir),
                "file_count": len(files),
                "brand_audit_passed": not violations,
                "violation_count": len(violations),
            })

    brand_violations = [] if args.dry_run else scan_brand_violations(matrix_root, brand_config)
    artifact_violations = [] if args.dry_run else scan_artifact_violations(matrix_root)
    report_dir = Path(args.report_dir) if args.report_dir else matrix_root / "00_Dashboards"
    report_stem = args.report_name or f"course_factory_run_{dt.datetime.now(dt.UTC).strftime('%Y%m%d%H%M%S')}"
    report_json_path = report_dir / f"{report_stem}.json"
    report_md_path = report_dir / f"{report_stem}.md"
    passed = (
        audit["passed"]
        and not full_violations
        and not sales_violations
        and all(item["brand_audit_passed"] for item in client_results)
        and not brand_violations
        and not artifact_violations
    )
    report = {
        "generated_at": now_iso(),
        "public_brand": public_brand(brand_config),
        "course_name": course_dir.name,
        "course_dir": safe_rel(course_dir, data_dir),
        "dry_run": args.dry_run,
        "build": build_result,
        "course_factory_audit": audit,
        "full_export": {
            "out_dir": safe_rel(full_out, data_dir),
            "file_count": len(full_files),
            "brand_audit_passed": not full_violations,
            "violation_count": len(full_violations),
        },
        "sales_preview": {
            "out_dir": safe_rel(sales_out, data_dir),
            "file_count": len(sales_files),
            "brand_audit_passed": not sales_violations,
            "violation_count": len(sales_violations),
        },
        "client_packs": client_results,
        "brand_audit": {"passed": not brand_violations, "violation_count": len(brand_violations)},
        "artifact_audit": {"passed": not artifact_violations, "violation_count": len(artifact_violations)},
        "report_json": safe_rel(report_json_path, data_dir),
        "report_md": safe_rel(report_md_path, data_dir),
        "passed": passed,
    }
    if not args.dry_run:
        report_dir.mkdir(parents=True, exist_ok=True)
        report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report_md_path.write_text(render_course_factory_run_report(report), encoding="utf-8")
        append_course_factory_derivations(data_dir, [{
            "generated_at": now_iso(),
            "derivation_type": "course_factory_run_all_report",
            "source_corpus": "course_factory",
            "source_file": safe_rel(course_dir / "course_factory_manifest.json", data_dir),
            "output_path": safe_rel(report_md_path, data_dir),
            "visibility": "internal",
            "public_brand": public_brand(brand_config),
        }])

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Course factory production run: {'passed' if passed else 'failed'}")
        print(f"Full export: {full_out}")
        print(f"Sales preview: {sales_out}")
        print(f"Client packs: {len(client_results)}")
        print(f"Report: {report_md_path}")
    return 0 if passed else 1


def query_terms(query: str) -> list[str]:
    query = clean_ws(query.lower())
    terms = [query] if query else []
    terms.extend(re.findall(r"[a-z0-9][a-z0-9\-]{1,}", query))
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", query)
    terms.extend(cjk)
    seen: set[str] = set()
    unique: list[str] = []
    for term in terms:
        if term and term not in seen:
            unique.append(term)
            seen.add(term)
    return unique


def score_record(record: dict, terms: list[str]) -> float:
    title = record.get("title", "").lower()
    headings = "\n".join(record.get("headings", [])).lower()
    text = record.get("text", "").lower()
    url = record.get("url", "").lower()
    category = record.get("category", "").lower()

    score = 0.0
    for term in terms:
        score += title.count(term) * 12
        score += headings.count(term) * 6
        score += text.count(term) * 1
        score += url.count(term) * 3
        score += category.count(term) * 2
    if record.get("category") in {"feature", "knowledge"}:
        score *= 1.08
    if record.get("category") == "vendor-template":
        score *= 1.15
    return score


def make_snippet(record: dict, terms: list[str], width: int = 260) -> str:
    text = clean_ws(record.get("text") or record.get("summary") or "")
    low = text.lower()
    pos = -1
    for term in terms:
        pos = low.find(term)
        if pos >= 0:
            break
    if pos < 0:
        return text[:width]
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix


def search_records(records: list[dict], query: str, top: int) -> list[tuple[float, dict, str]]:
    terms = query_terms(query)
    scored: list[tuple[float, dict, str]] = []
    for record in records:
        score = score_record(record, terms)
        if score > 0:
            scored.append((score, record, make_snippet(record, terms)))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[:top]


def source_category_priority(category: str) -> int:
    priorities = {
        "vendor-template": 0,
        "knowledge": 0,
        "feature": 1,
        "blog": 2,
        "knowledge-index": 3,
        "blog-index": 9,
    }
    return priorities.get(category, 5)


def redact_public_text(value: str, brand_config: dict) -> str:
    text = str(value or "")
    for source, target in sorted(
        brand_config.get("capability_map", {}).items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        text = re.sub(re.escape(source), target, text, flags=re.I)
    text = re.sub(r"https?://(?:www\.)?jarveepro\.com[^\s\])>]*", "internal source", text, flags=re.I)
    text = re.sub(r"https?://blog\.jarveepro\.com[^\s\])>]*", "internal source", text, flags=re.I)
    text = re.sub(r"\bblog\.jarveepro\.com\b", "internal source", text, flags=re.I)
    text = re.sub(r"\b(?:www\.)?jarveepro\.com\b", "internal source", text, flags=re.I)
    text = re.sub(r"\bJarveePro\b", public_brand(brand_config), text, flags=re.I)
    return text


def normalize_lang(lang: str | None) -> str:
    value = (lang or "zh-CN").strip().lower()
    if value in {"zh", "zh-cn", "cn", "chinese"}:
        return "zh-CN"
    if value in {"bi", "bilingual", "zh-en", "cn-en"}:
        return "bilingual"
    if value in {"en", "en-us", "english"}:
        return "en"
    return "zh-CN"


def normalize_depth(depth: str | None) -> str:
    value = (depth or "brief").strip().lower()
    if value in {"deep", "execution", "manual", "执行手册"}:
        return "deep"
    if value in {"course", "lesson", "training", "课程"}:
        return "course"
    return "brief"


def normalize_sop_layer(layer: str | None) -> str:
    value = (layer or "standard").strip().lower()
    if value in {"public", "course", "public-course", "public_course"}:
        return "public"
    if value in {"internal", "ops", "internal-ops", "internal_ops"}:
        return "internal"
    if value in {"dual", "dual-layer", "dual_layer", "both"}:
        return "dual"
    return "standard"


PLATFORM_PLAYBOOKS: dict[str, dict] = {
    "instagram": {
        "display": "Instagram",
        "folder": "Instagram",
        "positioning": "视觉信任、轻互动、主页承接和评论区信号驱动的平台。",
        "preferences": ["Reels 与短视频节奏", "评论区问题识别", "主页信任资产", "Stories 轻触达", "收藏与转发信号"],
        "audiences": ["课程/工具兴趣用户", "内容创作者", "小团队运营者", "正在比较解决方案的轻咨询用户"],
        "entry_points": ["Reels", "帖子评论区", "Stories", "主页简介", "精选集合"],
        "conversion_path": "内容曝光 -> 评论区价值回应 -> 主页信任判断 -> 用户主动询问 -> 人工跟进。",
        "tactics": ["新号先做内容与浏览节奏", "评论以价值补充为主", "把私信阶段放到明确互动之后", "每 7 天复盘一次内容支柱与账号稳定性"],
        "course_focus": ["账号冷启动", "评论区轻获客", "Reels 内容矩阵", "主页信任资产"],
        "policy_refs": [
            "Instagram Terms: https://www.facebook.com/help/instagram/581066165581870",
            "Instagram Community Guidelines: https://www.facebook.com/help/477434105621119?locale=en_GB",
        ],
    },
    "facebook": {
        "display": "Facebook",
        "folder": "Facebook",
        "positioning": "社群、主页、评论和本地信任关系驱动的平台。",
        "preferences": ["Groups 主题讨论", "Page 内容沉淀", "评论与消息线索", "本地/兴趣社群", "长文解释型内容"],
        "audiences": ["本地服务用户", "兴趣社群成员", "B2C 消费用户", "社群管理员与小企业主"],
        "entry_points": ["Groups", "Page posts", "评论区", "Marketplace", "Messenger"],
        "conversion_path": "社群内容/讨论 -> 价值回复 -> 主页或页面信任 -> 用户提问 -> 人工承接。",
        "tactics": ["先做社群相关性筛选", "避免同文跨群重复发布", "帖子与评论分开记录", "把链接与硬转化动作放到高信任账号和人工审核后"],
        "course_focus": ["Facebook Groups 获客", "主页内容排程", "评论线索识别", "社群规则适配"],
        "policy_refs": [
            "Instagram/Meta Terms: https://www.facebook.com/help/instagram/581066165581870",
            "Meta Community Guidelines reference: https://www.facebook.com/help/477434105621119?locale=en_GB",
        ],
    },
    "tiktok": {
        "display": "TikTok",
        "folder": "TikTok",
        "positioning": "短视频兴趣分发、热点跟随和账号内容一致性驱动的平台。",
        "preferences": ["短视频完播", "热点音频/话题", "账号垂直标签", "评论区需求", "直播或橱窗承接"],
        "audiences": ["内容消费用户", "兴趣标签用户", "年轻消费群体", "想快速理解工具/课程的人"],
        "entry_points": ["For You feed", "短视频评论区", "搜索关键词", "话题标签", "主页合集"],
        "conversion_path": "短视频触达 -> 评论或收藏信号 -> 主页连续内容验证 -> 用户主动询问 -> 人工承接。",
        "tactics": ["先固定账号内容标签", "小批量测试 3-5 个内容角度", "评论只做上下文相关回复", "复盘完播、评论质量和主页访问"],
        "course_focus": ["短视频矩阵", "热点筛选", "账号标签冷启动", "评论信号识别"],
        "policy_refs": [
            "TikTok Integrity and Authenticity: https://www.tiktok.com/community-guidelines/en/integrity-authenticity",
            "TikTok Community Guidelines: https://support.tiktok.com/en/safety-hc/account-and-user-safety/community-guidelines",
        ],
    },
    "linkedin": {
        "display": "LinkedIn",
        "folder": "LinkedIn",
        "positioning": "专业身份、内容可信度和 B2B 关系建立驱动的平台。",
        "preferences": ["专业观点内容", "个人主页可信度", "精准连接请求", "评论区专业互动", "长周期线索培育"],
        "audiences": ["B2B 决策者", "招聘/HR", "创始人", "销售负责人", "专业服务购买者"],
        "entry_points": ["个人主页", "公司主页", "行业帖子评论", "连接请求", "私信跟进"],
        "conversion_path": "专业内容/评论 -> 主页可信度判断 -> 连接建立 -> 人工个性化沟通 -> 预约或资料发送。",
        "tactics": ["先优化个人和公司主页", "评论必须体现专业上下文", "连接请求低频且个性化", "线索分层后再进入人工跟进"],
        "course_focus": ["B2B 线索筛选", "专业内容矩阵", "连接请求边界", "人工跟进脚本"],
        "policy_refs": [
            "LinkedIn Prohibited Software: https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions?lang=en",
        ],
    },
    "x_twitter": {
        "display": "X/Twitter",
        "folder": "X_Twitter",
        "positioning": "实时话题、观点表达、互动速度和公开讨论驱动的平台。",
        "preferences": ["实时热点", "短观点", "Thread", "引用与回复", "关键词监听"],
        "audiences": ["创作者", "科技/AI 用户", "投资与创业人群", "新闻热点参与者", "工具早期采用者"],
        "entry_points": ["关键词搜索", "话题帖", "Thread", "公开回复", "个人主页"],
        "conversion_path": "关键词/热点监听 -> 高质量公开回复 -> 主页信任 -> 用户互动 -> 人工跟进或内容引导。",
        "tactics": ["先做关键词监听", "回复要有观点和上下文", "避免重复转发和机械互动", "用 Thread 承接复杂主题"],
        "course_focus": ["实时信号监听", "公开回复获客", "Thread 内容矩阵", "关键词线索池"],
        "policy_refs": [
            "X Automation Rules: https://help.x.com/en/rules-and-policies/twitter-automation.html",
        ],
    },
}


def platform_key(platform: str | None) -> str:
    value = slugify(platform or "instagram", fallback="instagram").replace("-", "_").lower()
    aliases = {
        "ig": "instagram",
        "meta": "facebook",
        "fb": "facebook",
        "twitter": "x_twitter",
        "x": "x_twitter",
        "x_twitter": "x_twitter",
        "linkedin": "linkedin",
        "linked_in": "linkedin",
        "tiktok": "tiktok",
        "tik_tok": "tiktok",
    }
    return aliases.get(value, value if value in PLATFORM_PLAYBOOKS else "instagram")


def platform_keys_for_request(platform: str | None) -> list[str]:
    value = (platform or "instagram").strip().lower()
    if value in {"all", "*"}:
        return list(PLATFORM_PLAYBOOKS.keys())
    return [platform_key(platform)]


BOUNDARY_MATRIX: list[dict[str, str]] = [
    {
        "level": "绿色",
        "meaning": "可作为公开课程与日常 SOP 的稳定动作。",
        "examples": "内容准备、排程、人工审核、正常互动、每日记录、复盘。",
        "strategy": "继续执行，并保留记录。",
    },
    {
        "level": "黄色",
        "meaning": "可以做小范围验证，但必须有人审、上限和暂停条件。",
        "examples": "自动化辅助、批量账号管理、评论/私信测试、外部素材导入、跨账号内容变体。",
        "strategy": "降级执行，先小批量测试，异常即暂停。",
    },
    {
        "level": "红色",
        "meaning": "不进入公开课程，不作为推荐执行动作。",
        "examples": "垃圾内容、虚假互动、未经同意的高频触达、平台限制对抗、账号欺骗。",
        "strategy": "放弃或改写为合规的人工审核流程。",
    },
]


UNSAFE_PUBLIC_TRAINING_TERMS = ["规避检测", "绕过封控", "批量滥用", "突破限制"]


def scan_public_training_violations(text: str) -> list[str]:
    low = text.lower()
    return [term for term in UNSAFE_PUBLIC_TRAINING_TERMS if term.lower() in low]


def is_zh_lang(lang: str | None) -> bool:
    return normalize_lang(lang) in {"zh-CN", "bilingual"}


def bilingual_label(zh: str, en: str, lang: str | None) -> str:
    mode = normalize_lang(lang)
    if mode == "en":
        return en
    if mode == "bilingual":
        return f"{zh} / {en}"
    return zh


def localized_decision(value: str, lang: str | None) -> str:
    decision = (value or "unknown").lower()
    if not is_zh_lang(lang):
        return decision
    mapping = {
        "pass": "通过",
        "revise": "需补充后执行",
        "block": "阻断",
        "unknown": "未知",
    }
    label = mapping.get(decision, decision)
    return f"{label} ({decision})" if normalize_lang(lang) == "bilingual" else label


def translate_known_issue(text: str, lang: str | None) -> str:
    if not is_zh_lang(lang):
        return text
    mapping = {
        "EvidencePack is empty.": "EvidencePack 为空。",
        "Generate source-backed evidence before SOP approval.": "先生成有内部依据支撑的 EvidencePack，再审批 SOP。",
        "Proxy inventory is unknown.": "代理资源清单未知。",
        "Record proxy count and one-account-one-proxy binding status.": "补充代理数量，以及一账号一代理的绑定状态。",
        "Account maturity is new or unknown.": "账号成熟度为新号或未知。",
        "Keep the SOP in conservative warm-up and light validation mode.": "保持保守冷启动和轻量验证，不进入放量阶段。",
        "Mass DM is not explicitly forbidden in the task policy.": "任务策略没有明确禁止批量私信。",
        "Forbid mass DM in the first 14 days.": "前 14 天明确禁止批量私信。",
        "High-frequency commenting is allowed.": "策略允许高频评论。",
        "Limit comments to conservative daily validation ranges.": "评论量必须限制在保守的每日验证范围内。",
    }
    return mapping.get(text, text)


def confidence_for_record(record: dict) -> str:
    category = record.get("category", "")
    if category in {"knowledge", "feature"}:
        return "high"
    if category == "blog":
        return "medium"
    return "low"


def claim_type_for_record(record: dict) -> str:
    category = record.get("category", "")
    if category == "vendor-template":
        return "execution_framework"
    if category in {"knowledge", "feature"}:
        return "knowledge_fact"
    if category == "blog":
        return "strategy_context"
    return "discovery_context"


def public_evidence_item(score: float, record: dict, snippet: str, brand_config: dict) -> dict:
    basis_id = f"PUB-{record.get('id', sha1_text(record.get('url', ''))[:12]).upper()}"
    return {
        "basis_id": basis_id,
        "title": redact_public_text(record.get("title", ""), brand_config),
        "category": record.get("category", "unknown"),
        "source_basis": "internal knowledge base",
        "claim": redact_public_text(snippet or record.get("summary", ""), brand_config),
        "claim_type": claim_type_for_record(record),
        "confidence": confidence_for_record(record),
        "score": round(score, 3),
    }


def private_evidence_item(score: float, record: dict, snippet: str, brand_config: dict) -> dict:
    item = public_evidence_item(score, record, snippet, brand_config)
    item.update({
        "source_brand": brand_config.get("source_adapters", {}).get(DEFAULT_SOURCE, {}).get("source_brand", "JarveePro"),
        "source_url": record.get("url"),
        "source_note": record.get("note_path"),
        "raw_title": record.get("title"),
        "raw_path": record.get("raw_path"),
    })
    return item


def write_or_print(content: str, out: str | None, dry_run: bool = False) -> None:
    if out and not dry_run:
        path = Path(out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote: {path}")
    else:
        print(content)


def write_json_or_print(data: dict | list, out: str | None, dry_run: bool = False) -> None:
    content = json.dumps(data, ensure_ascii=False, indent=2)
    write_or_print(content, out, dry_run=dry_run)


def load_json_file(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_aivamax_matrix_dirs(data_dir: Path) -> Path:
    root = data_dir / "obsidian" / "AIvaMax_Matrix"
    for child in [
        "00_Dashboards",
        "10_Evidence",
        "20_Risks",
        "20_Risks/Platform_Boundaries",
        "30_SOPs",
        "40_Playbooks",
        "40_Playbooks/Case_Plans",
        "40_Playbooks/Media_Plans",
        "40_Playbooks/Platforms/Instagram",
        "40_Playbooks/Platforms/Facebook",
        "40_Playbooks/Platforms/TikTok",
        "40_Playbooks/Platforms/LinkedIn",
        "40_Playbooks/Platforms/X_Twitter",
        "50_Projects",
        "60_Reviews",
        "70_Courses",
        "public_export",
        "90_Templates",
    ]:
        (root / child).mkdir(parents=True, exist_ok=True)
    return root


def aivamax_matrix_template_files(brand_config: dict) -> dict[str, str]:
    brand = public_brand(brand_config)
    return {
        "00_Dashboards/Matrix MOC.md": f"""---
type: dashboard
public_brand: {brand}
status: active
---

# {brand} Matrix MOC

## Operating Areas
- [[Instagram Command Center]]
- [[Risk Overview]]
- [[Course Builder]]

## Knowledge Layers
- Evidence: [[../10_Evidence]]
- Risks: [[../20_Risks]]
- SOPs: [[../30_SOPs]]
- Playbooks: [[../40_Playbooks]]
- Projects: [[../50_Projects]]
- Reviews: [[../60_Reviews]]
- Courses: [[../70_Courses]]
- Templates: [[../90_Templates]]

## Default Workflow
1. Create a TaskBrief.
2. Generate a public EvidencePack.
3. Compile an SOP.
4. Run risk review.
5. Save the project.
6. Run brand audit.
""",
        "00_Dashboards/Instagram Command Center.md": f"""---
type: dashboard
public_brand: {brand}
platforms: [instagram]
status: active
---

# Instagram Command Center

## Active SOPs
- [[../30_SOPs/SOP-IG-Comment-LeadGen-14D]]

## Active Projects
```dataview
TABLE status, risk_level, duration_days
FROM "AIvaMax_Matrix/50_Projects"
WHERE contains(platforms, "instagram")
SORT file.mtime DESC
```

## Review Questions
- Are account maturity and proxy binding known?
- Has the SOP passed risk review?
- Has the public output passed brand audit?
""",
        "00_Dashboards/Risk Overview.md": f"""---
type: dashboard
public_brand: {brand}
status: active
---

# Risk Overview

## Risk Areas
- Account maturity
- Proxy binding
- Comment frequency
- DM timing
- Repeated templates
- Missing human review

## Audit Rule
No campaign is ready for human execution until the risk decision is `pass` or the required changes are explicitly accepted by a human reviewer.
""",
        "00_Dashboards/Course Builder.md": f"""---
type: dashboard
public_brand: {brand}
status: draft
---

# Course Builder

## Course Tracks
- [[../70_Courses/AIvaMax智能营销矩阵入门课/README]]
- [[../70_Courses/AIvaMax账号安全与获客SOP课/README]]
- [[../70_Courses/AIvaMax多智能体营销作战课/README]]

## Publishing Rule
Course lessons must be generated from AIvaMax public SOPs and reviews, not from private source notes.
""",
        "90_Templates/TEMPLATE-Evidence.md": f"""---
type: evidence
evidence_id:
public_brand: {brand}
status: draft
platforms: []
modules: []
actions: []
claim_type:
confidence:
source_basis: internal knowledge base
created:
---

# Evidence

## Claim

## Applies To

## Limits

## Related SOPs
""",
        "90_Templates/TEMPLATE-Risk.md": f"""---
type: risk
risk_id:
public_brand: {brand}
status: draft
platforms: []
severity:
risk_area:
evidence: []
related_sops: []
created:
---

# Risk

## Description

## Triggers

## Pause Conditions

## Mitigation
""",
        "90_Templates/TEMPLATE-SOP.md": f"""---
type: sop
sop_id:
public_brand: {brand}
status: draft_for_review
platforms: []
duration_days:
risk_level:
evidence: []
risks: []
---

# SOP

## 1. Task Brief

## 2. Evidence Map

## 3. Account And Environment Inventory

## 4. Execution Rhythm

## 5. Risk Controls

## 6. Daily Log

## 7. Review
""",
        "90_Templates/TEMPLATE-Project.md": f"""---
type: project
public_brand: {brand}
status: draft
platforms: []
risk_decision:
created:
---

# Project

## Brief

## Evidence

## SOP

## Risk Review

## Daily Log

## Final Review
""",
        "90_Templates/TEMPLATE-Agent-Run.md": f"""---
type: agent_run
public_brand: {brand}
run_id:
task_id:
status:
created:
---

# Agent Run

## Original Request

## TaskBrief

## EvidencePack

## SOPDraft

## RiskAudit

## BrandAudit

## Human Decision
""",
        "90_Templates/TEMPLATE-Review.md": f"""---
type: review
public_brand: {brand}
status: draft
project:
created:
---

# Review

## Results

## Metrics

## Risk Events

## Lessons

## Next Iteration
""",
        "70_Courses/AIvaMax智能营销矩阵入门课/README.md": f"""---
type: course
public_brand: {brand}
status: draft
---

# {brand} 智能营销矩阵入门课

## Course Goal
Teach the AIvaMax Matrix operating model: TaskBrief, EvidencePack, SOPDraft, RiskAudit, CampaignMemory, and BrandAudit.

## Lesson Backlog
- Matrix overview
- Evidence-backed SOP thinking
- Human-reviewed execution
- Review-driven improvement
""",
        "70_Courses/AIvaMax账号安全与获客SOP课/README.md": f"""---
type: course
public_brand: {brand}
status: draft
---

# {brand} 账号安全与获客 SOP 课

## Course Goal
Teach conservative account safety, light lead-generation validation, pause conditions, and review routines.

## Lesson Backlog
- Account maturity and environment inventory
- Conservative 14-day validation rhythm
- Comment lead-generation boundaries
- Risk review and pause decisions
""",
        "70_Courses/AIvaMax多智能体营销作战课/README.md": f"""---
type: course
public_brand: {brand}
status: draft
---

# {brand} 多智能体营销作战课

## Course Goal
Teach how Intake, Knowledge, SOP, Risk, and Memory agents cooperate inside the AIvaMax workflow.

## Lesson Backlog
- Agent roles
- Evidence handoff
- Risk gatekeeping
- Project memory and review loops
""",
    }


def run_init_matrix(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    matrix_root = ensure_aivamax_matrix_dirs(Path(args.data_dir))
    files = aivamax_matrix_template_files(brand_config)
    written: list[Path] = []
    skipped: list[Path] = []
    for rel_path, content in files.items():
        path = matrix_root / rel_path
        if path.exists() and not args.force:
            skipped.append(path)
            continue
        if not args.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(redact_public_text(content, brand_config), encoding="utf-8")
        written.append(path)
    if args.json:
        print(json.dumps({
            "matrix_root": str(matrix_root),
            "written": [str(path) for path in written],
            "skipped": [str(path) for path in skipped],
            "dry_run": args.dry_run,
        }, ensure_ascii=False, indent=2))
    else:
        action = "Would write" if args.dry_run else "Wrote"
        for path in written:
            print(f"{action}: {path}")
        for path in skipped:
            print(f"Skipped existing: {path}")
        print(f"AIvaMax Matrix root: {matrix_root}")
    return 0


def run_search(args: argparse.Namespace) -> int:
    records = load_source_records(Path(args.data_dir), getattr(args, "corpus", "web"))
    results = search_records(records, args.query, args.top)
    if args.json:
        print(json.dumps([{"score": s, "record": r, "snippet": sn} for s, r, sn in results], ensure_ascii=False, indent=2))
        return 0
    if not results:
        print("No matches. Try broader keywords or run sync again.")
        return 1
    for idx, (score, record, snippet) in enumerate(results, 1):
        print(f"{idx}. [{record['category']}] {record['title']}  score={score:.1f}")
        if record.get("source_corpus") == "vendor" or record.get("source_type") == "vendor_source_doc":
            print(f"   Source: {record.get('source_doc')} :: {record.get('section')}")
            print(f"   Path: {Path(args.data_dir) / record.get('source_path', '')}")
        else:
            print(f"   URL: {record.get('url', '')}")
            print(f"   Note: {Path(args.data_dir) / record.get('note_path', '')}")
        print(f"   {snippet}\n")
    return 0


def run_sync_source(args: argparse.Namespace) -> int:
    if args.source != DEFAULT_SOURCE:
        print(f"Unsupported source adapter: {args.source}", file=sys.stderr)
        return 2
    return run_sync(args)


def run_search_source(args: argparse.Namespace) -> int:
    if args.source != DEFAULT_SOURCE:
        print(f"Unsupported source adapter: {args.source}", file=sys.stderr)
        return 2
    return run_search(args)


def build_task_brief(args: argparse.Namespace, brand_config: dict) -> dict:
    task_id = slugify(
        args.task_id
        or f"{args.platform}-{args.template or 'custom'}-{args.accounts or 'unknown'}-{args.days}",
        fallback="aivamax-task",
    )
    scenario = args.scenario or "account_safety_comment_leadgen"
    template = args.template or "custom"
    scenario_text = f"{scenario} {template}".lower()
    if "content_matrix" in scenario_text or "reels" in scenario_text:
        allowed_actions = ["warmup", "research", "content_planning", "schedule", "publish", "monitor", "reply"]
        forbidden_actions = ["mass_dm", "high_frequency_comment", "spam_template", "unreviewed_repost"]
        success_metrics = [
            "content_publish_consistency",
            "profile_visit_rate",
            "comment_reply_rate",
            "qualified_leads",
            "risk_events",
        ]
    else:
        allowed_actions = ["warmup", "browse", "like", "comment", "monitor", "limited_dm"]
        forbidden_actions = ["mass_dm", "high_frequency_comment", "spam_template"]
        success_metrics = [
            "account_survival_rate",
            "comment_reply_rate",
            "qualified_leads",
            "risk_events",
        ]
    return {
        "task_id": task_id,
        "public_brand": public_brand(brand_config),
        "template": template,
        "platforms": [args.platform],
        "business_goal": args.goal,
        "scenario": scenario,
        "product_or_offer": args.offer or "unknown",
        "account_count": args.accounts if args.accounts is not None else "unknown",
        "account_stage": args.stage or "unknown",
        "duration_days": args.days,
        "risk_tolerance": args.risk,
        "allowed_actions": allowed_actions,
        "forbidden_actions": forbidden_actions,
        "resources": {
            "proxies": args.proxies or "unknown",
            "vps": args.vps or "unknown",
            "content_assets": args.content_assets or "unknown",
            "keywords": args.keyword or [],
        },
        "success_metrics": success_metrics,
        "source_policy": {
            "source_brand_visibility": "internal_only",
            "public_outputs_must_pass_brand_audit": True,
        },
        "created_at": now_iso(),
    }


def render_task_brief_markdown(brief: dict) -> str:
    keywords = ", ".join(brief.get("resources", {}).get("keywords", [])) or "unknown"
    return f"""---
type: task_brief
task_id: {brief.get('task_id')}
public_brand: {brief.get('public_brand')}
status: draft
---

# {brief.get('public_brand')} Task Brief

## Scenario
- Platform: {", ".join(brief.get("platforms", []))}
- Goal: {brief.get("business_goal")}
- Offer: {brief.get("product_or_offer")}
- Account count: {brief.get("account_count")}
- Account stage: {brief.get("account_stage")}
- Duration: {brief.get("duration_days")} days
- Risk tolerance: {brief.get("risk_tolerance")}
- Keywords: {keywords}

## Allowed Actions
{chr(10).join(f"- {item}" for item in brief.get("allowed_actions", []))}

## Forbidden Actions
{chr(10).join(f"- {item}" for item in brief.get("forbidden_actions", []))}
"""


def run_brief(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    brief = build_task_brief(args, brand_config)
    if args.format == "markdown":
        write_or_print(render_task_brief_markdown(brief), args.out, dry_run=args.dry_run)
    else:
        write_json_or_print(brief, args.out, dry_run=args.dry_run)
    return 0


def evidence_queries_for_brief(brief: dict) -> list[str]:
    platform = " ".join(brief.get("platforms", [])) or "Instagram"
    offer = brief.get("product_or_offer", "")
    scenario_text = f"{brief.get('scenario', '')} {brief.get('template', '')}".lower()
    if "content_matrix" in scenario_text or "reels" in scenario_text:
        base = [
            f"{platform} reels content strategy engagement safety",
            f"{platform} content planning scheduler campaign monitor",
            "Content Explorer campaign content intelligence publishing scheduler",
            f"{platform} account warm up proxy safety content publishing",
        ]
    else:
        base = [
            f"{platform} warm up account proxy safety",
            f"{platform} comment marketing high intent keywords lead generation",
            "AI Monitor real-time engagement Content Explorer campaign",
            f"{platform} DM safety gradual scale warm-up",
        ]
    if offer and offer != "unknown":
        if "content_matrix" in scenario_text or "reels" in scenario_text:
            base.append(f"{platform} {offer} reels content lead generation")
        else:
            base.append(f"{platform} {offer} comment lead generation")
    return base


def build_evidence_pack(
    brief: dict,
    records: list[dict],
    top: int,
    brand_config: dict,
    public_mode: bool = True,
) -> dict:
    queries = evidence_queries_for_brief(brief)
    by_id: dict[str, tuple[float, dict, str]] = {}
    for query in queries:
        for score, record, snippet in search_records(records, query, top):
            rid = record.get("id") or sha1_text(record.get("url", ""))[:12]
            old = by_id.get(rid)
            if not old or score > old[0]:
                by_id[rid] = (score, record, snippet)
    ranked = sorted(
        by_id.values(),
        key=lambda item: (source_category_priority(item[1].get("category", "")), -item[0]),
    )
    items = [
        public_evidence_item(score, record, snippet, brand_config)
        if public_mode else private_evidence_item(score, record, snippet, brand_config)
        for score, record, snippet in ranked[: max(top * 2, 10)]
        if public_mode or record.get("category") != "blog-index"
    ]
    return {
        "evidence_pack_id": f"EVPACK-{brief.get('task_id', 'task').upper()}",
        "public_brand": public_brand(brand_config),
        "public_mode": public_mode,
        "task_id": brief.get("task_id"),
        "source_adapter": "internal_source_adapter" if public_mode else DEFAULT_SOURCE,
        "generated_at": now_iso(),
        "queries": queries,
        "items": items,
    }


def render_evidence_pack_markdown(pack: dict) -> str:
    lines = [
        "---",
        "type: evidence_pack",
        f"evidence_pack_id: {pack.get('evidence_pack_id')}",
        f"public_brand: {pack.get('public_brand')}",
        "---",
        "",
        f"# {pack.get('public_brand')} Evidence Pack",
        "",
        "## Queries",
        "",
    ]
    lines.extend(f"- {query}" for query in pack.get("queries", []))
    lines.extend(["", "## Evidence", ""])
    for item in pack.get("items", []):
        lines.append(f"### {item.get('basis_id')}")
        lines.append(f"- Title: {item.get('title')}")
        lines.append(f"- Category: {item.get('category')}")
        lines.append(f"- Basis: {item.get('source_basis', 'internal knowledge base')}")
        lines.append(f"- Claim type: {item.get('claim_type')}")
        lines.append(f"- Confidence: {item.get('confidence')}")
        lines.append(f"- Claim: {item.get('claim')}")
        lines.append("")
    return "\n".join(lines)


def run_evidence(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    brief = load_json_file(args.brief)
    records = load_source_records(Path(args.data_dir), getattr(args, "corpus", "web"))
    pack = build_evidence_pack(
        brief,
        records,
        args.top,
        brand_config,
        public_mode=not args.internal,
    )
    if args.format == "markdown":
        write_or_print(render_evidence_pack_markdown(pack), args.out, dry_run=args.dry_run)
    else:
        write_json_or_print(pack, args.out, dry_run=args.dry_run)
    return 0


def render_sources(results: list[tuple[float, dict, str]]) -> str:
    lines = []
    for idx, (_, record, _) in enumerate(results, 1):
        lines.append(f"{idx}. [{record['title']}]({record['url']}) - `{record['category']}`")
    return "\n".join(lines)


def render_relevant_knowledge(results: list[tuple[float, dict, str]]) -> str:
    lines = []
    for idx, (_, record, snippet) in enumerate(results, 1):
        headings = record.get("headings", [])[:4]
        heading_part = "; ".join(headings) if headings else record.get("summary", "")
        lines.append(
            f"{idx}. **{record['title']}** (`{record['category']}`): "
            f"{clean_ws(heading_part)[:220]}\n   - Evidence: {snippet[:260]}"
        )
    return "\n".join(lines)


def run_task(args: argparse.Namespace) -> int:
    records = load_records(Path(args.data_dir))
    results = search_records(records, args.task, args.top)
    if not results:
        print("No source-backed context found. Run sync or try a broader task description.")
        return 1

    feature_docs = [r for _, r, _ in results if r.get("category") == "feature"]
    knowledge_docs = [r for _, r, _ in results if r.get("category") in {"knowledge", "knowledge-index"}]
    blog_docs = [r for _, r, _ in results if r.get("category") in {"blog", "blog-index"}]

    feature_line = ", ".join(doc["title"] for doc in feature_docs[:4]) or "Use the retrieved pages below to identify the closest JarveePro feature set."
    knowledge_line = ", ".join(doc["title"] for doc in knowledge_docs[:4]) or "No direct knowledge-base page appeared in the top results; verify with a broader search."
    blog_line = ", ".join(doc["title"] for doc in blog_docs[:3]) or "No strategy blog appeared in the top results."

    content = f"""# JarveePro Task Plan

## Task Understanding

User need: **{args.task}**

The plan below is generated from the local JarveePro index. Treat it as a source-backed draft: verify exact UI labels and account limits inside your JarveePro environment before executing.

## Relevant JarveePro Knowledge

{render_relevant_knowledge(results)}

## Recommended Workflow

1. Define the target outcome and platform scope. Write down the account type, target platform, target audience, limits, and success metric before opening JarveePro.
2. Map the task to JarveePro feature areas. Current likely feature references: {feature_line}
3. Check setup or troubleshooting references before automation. Current likely knowledge-base references: {knowledge_line}
4. Use strategic context where useful. Current likely blog references: {blog_line}
5. Configure in a small test batch first. Start with conservative volume, confirm login/session health, and validate the output manually.
6. Scale only after the test batch is stable. Increase volume gradually and keep a rollback note for settings that were changed.
7. Record the final operating recipe in Obsidian using `python jarveepro_cli.py export-obsidian` so the workflow becomes reusable.

## Configuration Checklist

- Accounts, proxies, cookies, and login state are valid.
- Target platform and action type are selected correctly.
- Search/list/import source is clean and deduplicated.
- Daily/hourly limits are conservative for the account age and platform.
- Error handling, retry behavior, and stop conditions are clear.
- Results are reviewed before scaling.

## Risks And Guardrails

- Respect platform rules, rate limits, and privacy expectations.
- Avoid mass messaging, scraping, or engagement patterns that could look abusive.
- Do not run new automation settings on high-value accounts without a small test.
- Keep a manual audit trail of source lists, settings, and observed outcomes.

## What To Verify Next

- Run `python jarveepro_cli.py search "{args.task}" --top {args.top}` and inspect the source notes.
- If the index is old, run `python jarveepro_cli.py sync --max-pages 300`.
- If the task is broad, split it into platform, feature, and execution-stage searches.

## Sources

{render_sources(results)}
"""
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"Wrote task plan: {out}")
    else:
        print(content)
    return 0


def run_teach(args: argparse.Namespace) -> int:
    records = load_records(Path(args.data_dir))
    results = search_records(records, args.topic, args.top)
    if not results:
        print("No source-backed context found. Run sync or try a broader topic.")
        return 1

    content = f"""# JarveePro Learning Path

Topic: **{args.topic}**

## Learning Goal

Understand the JarveePro concepts, product features, and operational playbook needed to handle this topic independently.

## Source-Backed Reading Order

{render_relevant_knowledge(results)}

## Study Sequence

1. **Concept map**: Read the top 3 pages and write a one-sentence purpose for each feature or method.
2. **Vocabulary**: Extract UI terms, platform terms, and action verbs from the source notes.
3. **Workflow reconstruction**: Convert the documentation into "input -> setting -> action -> expected result".
4. **Small exercise**: Create one low-risk test case and write expected observations before running it.
5. **Review**: Compare the actual result with the source-backed expectation and update your Obsidian note.

## Practice Prompts

- Explain this topic to me like I am setting it up for the first time.
- Give me the safest small-batch version of this workflow.
- What settings would I check if the result fails?
- Turn this topic into a reusable SOP for my agent platform.

## Sources

{render_sources(results)}
"""
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"Wrote learning path: {out}")
    else:
        print(content)
    return 0


def is_content_matrix_brief(brief: dict) -> bool:
    scenario_text = f"{brief.get('scenario', '')} {brief.get('template', '')}".lower()
    return "content_matrix" in scenario_text or "reels" in scenario_text


def platform_label(brief: dict) -> str:
    platform = (brief.get("platforms") or ["instagram"])[0]
    labels = {
        "instagram": "Instagram",
        "linkedin": "LinkedIn",
        "x": "X",
        "twitter": "X",
        "tiktok": "TikTok",
        "facebook": "Facebook",
    }
    return labels.get(str(platform).lower(), str(platform).title())


def sop_profile_for_brief(brief: dict, brand_config: dict, lang: str | None = "zh-CN") -> dict:
    brand = public_brand(brand_config)
    platform = platform_label(brief)
    days = brief.get("duration_days", 14)
    if is_zh_lang(lang):
        if is_content_matrix_brief(brief):
            return {
                "sop_id": f"SOP-{slugify(platform, 'platform').upper()}-ContentMatrix-{days}D",
                "title": bilingual_label(
                    f"{brand} {platform} 内容矩阵 {days} 天 SOP",
                    f"{brand} {platform} Content Matrix {days}-Day SOP",
                    lang,
                ),
                "scenario": f"{platform} 内容矩阵验证",
                "section6": bilingual_label("内容矩阵规则", "Content Matrix Rules", lang),
                "section7": bilingual_label("互动跟进边界", "Engagement Follow-Up Boundary", lang),
                "rules": [
                    "发布前先定义 3-5 个内容支柱，避免随意发内容。",
                    "用内容情报做选题和角度判断，不复制竞品内容。",
                    "每条标题、文案、CTA 都要结合产品和账号阶段做人审。",
                    "评论回复只使用人工确认过的回复方式，不做批量私信。",
                ],
            }
        return {
            "sop_id": f"SOP-{slugify(platform, 'platform').upper()}-Comment-LeadGen-{days}D",
            "title": bilingual_label(
                f"{brand} {platform} 账号安全与评论区轻获客 {days} 天 SOP",
                f"{brand} {platform} Account Safety + Comment Lead-Generation {days}-Day SOP",
                lang,
            ),
            "scenario": f"{platform} 账号安全冷启动与评论区轻获客验证",
            "section6": bilingual_label("评论区轻获客规则", "Comment Lead-Generation Rules", lang),
            "section7": bilingual_label("私信跟进边界", "DM Follow-Up Boundary", lang),
            "rules": [
                "优先寻找高意向信号，例如价格、链接、怎么做、是否安全、工具推荐等。",
                "每条评论都必须结合目标帖子、产品卖点和账号阶段做人审。",
                "避免重复模板，优先使用价值型评论，不做硬广式推销。",
            ],
        }
    if is_content_matrix_brief(brief):
        return {
            "sop_id": f"SOP-{slugify(platform, 'platform').upper()}-ContentMatrix-{days}D",
            "title": f"{brand} {platform} Content Matrix {days}-Day SOP",
            "scenario": f"{platform} content matrix validation",
            "section6": "Content Matrix Rules",
            "section7": "Engagement Follow-Up Boundary",
            "rules": [
                "Define 3-5 content pillars before publishing or scheduling.",
                "Use content intelligence for positioning and inspiration; do not copy competitor posts.",
                "Every caption, hook, and CTA must be reviewed against the offer and account stage.",
                "Reply to relevant comments manually or with human-approved templates only.",
            ],
        }
    return {
        "sop_id": f"SOP-{slugify(platform, 'platform').upper()}-Comment-LeadGen-{days}D",
        "title": f"{brand} {platform} Account Safety + Comment Lead-Generation {days}-Day SOP",
        "scenario": f"{platform} account safety cold-start + comment lead-generation validation",
        "section6": "Comment Lead-Generation Rules",
        "section7": "DM Follow-Up Boundary",
        "rules": [
            "Use high-intent signals such as buy, price, link, how, does it, and safe.",
            "Every outbound comment must be reviewed against the offer and target post context.",
            "Avoid repeated templates. Use value-first comments, not direct hard-selling.",
        ],
    }


def phase_rows_for_sop(brief: dict | None = None, lang: str | None = "zh-CN") -> list[dict]:
    if is_zh_lang(lang):
        if brief and is_content_matrix_brief(brief):
            return [
                {
                    "days": "第 0 天",
                    "goal": "内容系统准备",
                    "actions": "确认内容支柱、产品角度、审核负责人、素材清单、发布时间和风险边界。",
                    "limit": "不发布、不外联",
                },
                {
                    "days": "第 1-3 天",
                    "goal": "账号冷启动与赛道研究",
                    "actions": "浏览同赛道内容、收藏案例、草拟标题和文案，同时观察账号健康状态。",
                    "limit": "只研究和起草，不做规模互动",
                },
                {
                    "days": "第 4-7 天",
                    "goal": "内容批次验证",
                    "actions": "准备或排程已审核内容，测试 1-2 个内容支柱，记录早期反馈。",
                    "limit": "每个健康账号每天最多 1 条已审核内容",
                },
                {
                    "days": "第 8-10 天",
                    "goal": "信号复盘与评论处理",
                    "actions": "记录回复、收藏、主页访问、高意向评论，只回复明确相关的互动。",
                    "limit": "不做批量评论或批量私信",
                },
                {
                    "days": "第 11-14 天",
                    "goal": "迭代与下一批内容规划",
                    "actions": "保留有效选题，淘汰弱角度，准备下一批内容，并总结可复用经验。",
                    "limit": "放量必须经过人工复盘",
                },
            ]
        return [
            {
                "days": "第 0 天",
                "goal": "环境与账号准备",
                "actions": "绑定代理、检查重复代理、分组账号、准备关键词、确认人工审核负责人。",
                "limit": "不做任何外联动作",
            },
            {
                "days": "第 1-3 天",
                "goal": "建立正常账号行为",
                "actions": "浏览信息流、观看 Reels/Stories、轻量点赞、自然停顿，不发销售评论。",
                "limit": "每账号每天 0-1 条非推广评论",
            },
            {
                "days": "第 4-7 天",
                "goal": "积累账号信任",
                "actions": "继续冷启动，在相关帖子下做人审价值评论，观察账号健康。",
                "limit": "每账号每天 0-1 条价值评论",
            },
            {
                "days": "第 8-10 天",
                "goal": "观察潜在线索来源",
                "actions": "监控目标帖子和高意向评论，分类购买意图和问题意识。",
                "limit": "每个健康账号每天 1-2 条评论",
            },
            {
                "days": "第 11-14 天",
                "goal": "轻量获客验证",
                "actions": "测试已审核评论模板，只回复相关互动，准备复盘数据。",
                "limit": "每个健康账号每天 2-3 条评论；禁止批量私信",
            },
        ]
    if brief and is_content_matrix_brief(brief):
        return [
            {
                "days": "Day 0",
                "goal": "Content system readiness",
                "actions": "Define pillars, offer angle, review owner, asset inventory, posting windows, and risk limits.",
                "limit": "No publishing or outreach actions",
            },
            {
                "days": "Day 1-3",
                "goal": "Account warm-up and niche research",
                "actions": "Browse niche content, save examples, draft hooks, prepare captions, and observe account health.",
                "limit": "Research and drafting only; no scaled engagement",
            },
            {
                "days": "Day 4-7",
                "goal": "Content batch validation",
                "actions": "Prepare or schedule reviewed posts, test 1-2 content pillars, and monitor early signals.",
                "limit": "1 reviewed post or Reel per active account/day",
            },
            {
                "days": "Day 8-10",
                "goal": "Signal review and comment handling",
                "actions": "Track replies, saves, profile visits, and high-intent comments; respond only with reviewed replies.",
                "limit": "No mass comments or mass DM",
            },
            {
                "days": "Day 11-14",
                "goal": "Iteration and next-batch planning",
                "actions": "Keep winning topics, retire weak angles, prepare the next batch, and summarize learnings.",
                "limit": "Scale only after human review",
            },
        ]
    return [
        {
            "days": "Day 0",
            "goal": "Environment and account readiness",
            "actions": "Bind proxies, disable duplicate proxy binding, group accounts, prepare keywords, confirm manual review owner.",
            "limit": "No outreach actions",
        },
        {
            "days": "Day 1-3",
            "goal": "Identity and normal behavior footprint",
            "actions": "Browse feed, watch Reels/Stories, light likes, natural pauses, no sales comments.",
            "limit": "0-1 non-promotional comment per account/day",
        },
        {
            "days": "Day 4-7",
            "goal": "Trust accumulation",
            "actions": "Continue warm-up, add value-only comments on relevant posts, observe account health.",
            "limit": "0-1 value comment per account/day",
        },
        {
            "days": "Day 8-10",
            "goal": "Lead-source observation",
            "actions": "Monitor target posts and high-intent comments, classify buyer intent and problem-aware comments.",
            "limit": "1-2 comments per healthy account/day",
        },
        {
            "days": "Day 11-14",
            "goal": "Light lead-generation validation",
            "actions": "Test reviewed comment templates, reply only to relevant interactions, prepare review data.",
            "limit": "2-3 comments per healthy account/day; no mass DM",
        },
    ]


def mermaid_agent_flow(lang: str | None = "zh-CN") -> str:
    if is_zh_lang(lang):
        return """```mermaid
flowchart LR
  A["需求输入"] --> B["Intake Agent<br/>任务简报"]
  B --> C["Knowledge Agent<br/>公开证据包"]
  C --> D["SOP Agent<br/>执行方案"]
  D --> E["Risk Agent<br/>风险审核"]
  E --> F["Memory Agent<br/>项目沉淀"]
  F --> G["Course Agent<br/>课程模块"]
  G --> H["Brand Auditor<br/>品牌审计"]
```"""
    return """```mermaid
flowchart LR
  A["Request"] --> B["Intake Agent<br/>TaskBrief"]
  B --> C["Knowledge Agent<br/>EvidencePack"]
  C --> D["SOP Agent<br/>SOPDraft"]
  D --> E["Risk Agent<br/>RiskAudit"]
  E --> F["Memory Agent<br/>Project"]
  F --> G["Course Agent<br/>Course Module"]
  G --> H["Brand Auditor<br/>BrandAudit"]
```"""


def mermaid_sop_flow(brief: dict, lang: str | None = "zh-CN") -> str:
    if is_content_matrix_brief(brief):
        if is_zh_lang(lang):
            return """```mermaid
flowchart TD
  A["确认产品与账号阶段"] --> B["定义内容支柱"]
  B --> C["收集内容信号"]
  C --> D["生成并审核标题/文案/CTA"]
  D --> E["小批量发布"]
  E --> F["监控互动与风险"]
  F --> G["第14天复盘并决定是否放量"]
```"""
        return """```mermaid
flowchart TD
  A["Confirm offer and account stage"] --> B["Define content pillars"]
  B --> C["Collect content signals"]
  C --> D["Review hooks/captions/CTA"]
  D --> E["Publish small batch"]
  E --> F["Monitor engagement and risk"]
  F --> G["Day 14 review"]
```"""
    if is_zh_lang(lang):
        return """```mermaid
flowchart TD
  A["确认账号与代理环境"] --> B["冷启动正常行为"]
  B --> C["小量价值评论"]
  C --> D["识别高意向评论区"]
  D --> E["人审评论模板"]
  E --> F["轻量回复与线索记录"]
  F --> G["第14天复盘并决定下一阶段"]
```"""
    return """```mermaid
flowchart TD
  A["Confirm account and proxy environment"] --> B["Warm up normal behavior"]
  B --> C["Low-volume value comments"]
  C --> D["Identify high-intent comment areas"]
  D --> E["Human-reviewed comment templates"]
  E --> F["Light replies and lead log"]
  F --> G["Day 14 review"]
```"""


def mermaid_timeline(brief: dict, lang: str | None = "zh-CN") -> str:
    rows = phase_rows_for_sop(brief, lang)
    lines = ["```mermaid", "timeline", f"  title {bilingual_label('14 天执行节奏', '14-Day Execution Rhythm', lang)}"]
    for row in rows:
        lines.append(f"  {row['days']} : {row['goal']}")
    lines.append("```")
    return "\n".join(lines)


def mermaid_risk_map(lang: str | None = "zh-CN") -> str:
    if is_zh_lang(lang):
        return """```mermaid
flowchart TD
  A["风险审核"] --> B{"证据是否充分?"}
  B -- "否" --> R["需补充 EvidencePack"]
  B -- "是" --> C{"账号/代理是否明确?"}
  C -- "否" --> R
  C -- "是" --> D{"是否包含批量私信/高频动作?"}
  D -- "是" --> X["阻断"]
  D -- "否" --> P["通过或保守执行"]
```"""
    return """```mermaid
flowchart TD
  A["Risk Audit"] --> B{"Evidence ready?"}
  B -- "No" --> R["Revise"]
  B -- "Yes" --> C{"Account/proxy known?"}
  C -- "No" --> R
  C -- "Yes" --> D{"Mass DM or high frequency?"}
  D -- "Yes" --> X["Block"]
  D -- "No" --> P["Pass or conservative execution"]
```"""


def mermaid_structure_map(brief: dict, lang: str | None = "zh-CN") -> str:
    if is_content_matrix_brief(brief):
        if is_zh_lang(lang):
            return """```mermaid
mindmap
  root((内容矩阵))
    产品卖点
    目标用户
    内容支柱
    标题与CTA
    发布节奏
    互动信号
    风险复盘
```"""
        return """```mermaid
mindmap
  root((Content Matrix))
    Offer
    Audience
    Pillars
    Hooks and CTA
    Schedule
    Engagement signals
    Risk review
```"""
    if is_zh_lang(lang):
        return """```mermaid
mindmap
  root((账号安全检查))
    账号年龄
    资料完整度
    代理绑定
    VPS环境
    每日动作上限
    暂停条件
    人工复盘
```"""
    return """```mermaid
mindmap
  root((Account Safety Check))
    Account age
    Profile completeness
    Proxy binding
    VPS environment
    Daily action limit
    Pause conditions
    Human review
```"""


def render_visual_sections(brief: dict, lang: str | None = "zh-CN", visuals: str | None = "none") -> str:
    mode = (visuals or "none").lower()
    if mode not in {"mermaid", "all"}:
        return ""
    title = bilingual_label("可视化流程图", "Visual Workflow", lang)
    sections = [
        f"## {title}",
        "",
        f"### {bilingual_label('多智能体执行链路', 'Multi-Agent Flow', lang)}",
        mermaid_agent_flow(lang),
        "",
        f"### {bilingual_label('SOP 执行流程', 'SOP Flow', lang)}",
        mermaid_sop_flow(brief, lang),
        "",
        f"### {bilingual_label('14 天节奏图', '14-Day Timeline', lang)}",
        mermaid_timeline(brief, lang),
        "",
        f"### {bilingual_label('风险审核决策图', 'Risk Decision Map', lang)}",
        mermaid_risk_map(lang),
        "",
        f"### {bilingual_label('结构示意图', 'Structure Map', lang)}",
        mermaid_structure_map(brief, lang),
        "",
    ]
    return "\n".join(sections)


def render_media_sections(brief: dict, data_dir: Path, brand_config: dict, lang: str | None = "zh-CN") -> str:
    entries = matching_media_entries(load_media_index(data_dir).get("items", []), brief, approved_only=True)
    if not entries:
        return ""
    lines = [
        f"## {bilingual_label('配套截图素材', 'Matched Media Assets', lang)}",
        "",
    ]
    for item in entries[:8]:
        caption = redact_public_text(item.get("caption") or item.get("alt") or item.get("media_id"), brand_config)
        asset_path = item.get("asset_path", "")
        lines.append(f"![{caption}]({asset_path})")
        lines.append(f"- {caption}")
        lines.append("")
    return "\n".join(lines)


def markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def boundary_rows_markdown() -> str:
    lines = ["| 分层 | 含义 | 典型动作 | 处理策略 |", "|---|---|---|---|"]
    for row in BOUNDARY_MATRIX:
        lines.append(f"| {row['level']} | {row['meaning']} | {row['examples']} | {row['strategy']} |")
    return "\n".join(lines)


def platform_profile(platform: str | None) -> dict:
    return PLATFORM_PLAYBOOKS[platform_key(platform)]


def render_boundary_brief(platform: str | None, brand_config: dict, lang: str | None = "zh-CN") -> str:
    brand = public_brand(brand_config)
    profile = platform_profile(platform)
    if not is_zh_lang(lang):
        content = f"""---
type: boundary_brief
public_brand: {brand}
platform: {profile['display']}
status: active
---

# {brand} {profile['display']} Boundary Brief

This note translates platform policy and operational experience into execution boundaries. It is not a policy copy, and it is not a promise that any account action is risk-free.

## Green / Yellow / Red Matrix
{boundary_rows_markdown()}

## Operating Rules
- Use official policy as a red-line reference, not as the only tactical source.
- Keep public teaching focused on platform logic, human review, pause conditions, and review routines.
- Keep account batches, execution parameters, incidents, and experiments in internal-only project files.
- Any abnormal account signal requires pause, review, and a written recovery decision.

## Platform Notes
- Positioning: {profile['positioning']}
- Conversion path: {profile['conversion_path']}

## References
{markdown_list(profile['policy_refs'])}
"""
        return redact_public_text(content, brand_config)
    content = f"""---
type: boundary_brief
public_brand: {brand}
platform: {profile['display']}
status: active
---

# {brand} {profile['display']} 风险边界简报

这份简报不是照搬官方条款，也不是承诺任何账号动作零风险。它的作用是把平台规则、矩阵软件实操经验和课程交付口径翻译成清晰的红黄绿边界，让执行者知道什么可以公开讲、什么只能内部复盘、什么必须停止。

## 1. 红黄绿风险矩阵
{boundary_rows_markdown()}

## 2. 作战约束
- 官方政策只作为红线参考和风险解释，不作为唯一打法来源。
- 公开课程只讲平台逻辑、内容方法、人审、暂停条件和复盘机制。
- 账号批次、环境参数、异常事件、实验假设只进入内部执行稿。
- 任何账号异常都先暂停，再复盘，再决定继续、降级、恢复或放弃。

## 3. 平台差异提醒
- 平台定位: {profile['positioning']}
- 主要入口: {', '.join(profile['entry_points'])}
- 成交路径: {profile['conversion_path']}
- 课程重点: {', '.join(profile['course_focus'])}

## 4. 公开课可讲
- 平台偏好与用户画像。
- 内容入口、互动入口和主页承接路径。
- 账号安全检查、人工审核、复盘表和异常暂停。
- 用案例解释为什么先做小范围验证，而不是直接追求动作规模。

## 5. 只放内部执行稿
- 账号批次、代理/VPS/环境记录。
- 每日执行参数、实验假设、异常事件。
- 话术审核过程、失败记录、恢复记录。
- 团队复盘结论和下一轮测试条件。

## 6. 官方参考
{markdown_list(profile['policy_refs'])}
"""
    return redact_public_text(content, brand_config)


def render_platform_playbook(platform: str | None, brand_config: dict, lang: str | None = "zh-CN") -> str:
    brand = public_brand(brand_config)
    profile = platform_profile(platform)
    if not is_zh_lang(lang):
        content = f"""---
type: platform_playbook
public_brand: {brand}
platform: {profile['display']}
status: active
---

# {brand} {profile['display']} Platform Playbook

## Platform Positioning
{profile['positioning']}

## Preferences
{markdown_list(profile['preferences'])}

## Audience Profiles
{markdown_list(profile['audiences'])}

## Entry Points
{markdown_list(profile['entry_points'])}

## Conversion Path
{profile['conversion_path']}

## Tactics
{markdown_list(profile['tactics'])}

## Risk Boundaries
{boundary_rows_markdown()}
"""
        return redact_public_text(content, brand_config)
    content = f"""---
type: platform_playbook
public_brand: {brand}
platform: {profile['display']}
status: active
---

# {brand} {profile['display']} 平台专项打法库

## 1. 平台打法总览
{profile['positioning']}

```mermaid
flowchart LR
  A["平台信号"] --> B["内容入口"]
  B --> C["互动入口"]
  C --> D["主页/资料承接"]
  D --> E["人工跟进"]
  E --> F["复盘与下一轮优化"]
```

## 2. 平台偏好
{markdown_list(profile['preferences'])}

## 3. 用户画像
{markdown_list(profile['audiences'])}

## 4. 内容入口与转化路径
- 主要入口: {', '.join(profile['entry_points'])}
- 成交路径: {profile['conversion_path']}

## 5. 核心打法
{markdown_list(profile['tactics'])}

## 6. 红黄绿风险边界
{boundary_rows_markdown()}

## 7. 课程化表达
{markdown_list(profile['course_focus'])}

## 8. 公开课程与内部执行分工
| 层级 | 可以承载的内容 | 不承载的内容 |
|---|---|---|
| 公开课程层 | 平台逻辑、内容方法、账号安全、人审、暂停条件、复盘 | 账号批次、环境参数、异常细节、未验证实验 |
| 内部执行层 | 实验假设、账号分层、素材准备、动作记录、异常处理 | 对外销售页、公开学员讲义 |

## 9. 官方参考
{markdown_list(profile['policy_refs'])}
"""
    return redact_public_text(content, brand_config)


def render_execution_log_template(brief: dict, brand_config: dict, lang: str | None = "zh-CN") -> str:
    brand = public_brand(brand_config)
    platform = platform_profile((brief.get("platforms") or ["instagram"])[0])
    content = f"""---
type: execution_log
visibility: internal_only
public_brand: {brand}
platform: {platform['display']}
status: active
---

# {brand} 内部执行记录表

## 1. 实验假设
- 本轮目标:
- 目标平台:
- 账号批次:
- 内容/评论假设:
- 风险假设:

## 2. 每日记录
| 日期 | 账号批次 | 执行动作 | 上限 | 结果 | 风险事件 | 调整 |
|---|---|---|---|---|---|---|

## 3. 异常事件
| 时间 | 账号/批次 | 现象 | 初步原因 | 处理动作 | 恢复条件 |
|---|---|---|---|---|---|

## 4. 第 7 天复盘
- 保留动作:
- 降级动作:
- 暂停动作:
- 需要补充的素材/账号/环境:

## 5. 第 14 天复盘
- 有效入口:
- 有效内容:
- 有效互动方式:
- 风险事件:
- 下一轮是否继续:
"""
    return redact_public_text(content, brand_config)


def render_public_course_sop(
    brief: dict,
    evidence_pack: dict,
    brand_config: dict,
    lang: str | None = "zh-CN",
    visuals: str | None = "mermaid",
    data_dir: Path | None = None,
    depth: str | None = "brief",
) -> str:
    brand = public_brand(brand_config)
    profile = sop_profile_for_brief(brief, brand_config, lang)
    platform = platform_profile((brief.get("platforms") or ["instagram"])[0])
    evidence_rows = evidence_strategy_rows(evidence_pack, brand_config, limit=8)
    visual_sections = render_visual_sections(brief, lang, visuals)
    media_sections = ""
    if (visuals or "").lower() in {"media", "all"} and data_dir is not None:
        media_sections = render_media_sections(brief, data_dir, brand_config, lang)
    if normalize_depth(depth) == "course" and is_zh_lang(lang):
        content = render_course_grade_public_sop(
            brand=brand,
            title=profile["title"],
            sop_id=profile["sop_id"],
            platform=platform,
            offer=str(brief.get("product_or_offer", "unknown")),
            account_count=str(brief.get("account_count", "unknown")),
            account_stage=str(brief.get("account_stage", "unknown")),
            risk_tolerance=str(brief.get("risk_tolerance", "conservative")),
            visual_sections=visual_sections,
            media_sections=media_sections,
            boundary_rows=boundary_rows_markdown(),
            evidence_rows=evidence_rows,
            daily_rows=deep_daily_rows_for_sop(brief),
        )
        return redact_public_text(content, brand_config)
    content = f"""---
type: public_course_sop
visibility: public_course
public_brand: {brand}
sop_id: {profile['sop_id']}-PUBLIC
platform: {platform['display']}
status: draft_for_training
---

# {profile['title']} 公开课程版 SOP

## 1. 平台打法总览
{platform['positioning']}

{visual_sections}
{media_sections}

## 2. 平台用户画像
{markdown_list(platform['audiences'])}

## 3. 内容入口与转化路径
- 主要入口: {', '.join(platform['entry_points'])}
- 转化路径: {platform['conversion_path']}

## 4. 红黄绿风险边界
{boundary_rows_markdown()}

## 5. 公开课程可讲内容
- 如何做平台偏好分析、用户画像和内容入口选择。
- 如何做账号安全检查、素材准备、人工审核和每日复盘。
- 如何识别高意向评论、明确提问和主动互动信号。
- 如何设置暂停、降级、恢复和第 7/14 天复盘机制。

## 6. 团队私有资料边界
以下内容只进入团队私有项目资料，不放进公开课程讲义:
- 账号批次、代理/VPS/环境参数。
- 每日执行参数、实验假设和异常事件。
- 未验证的话术、素材失败记录和恢复过程。
- 团队复盘结论与下一轮测试条件。

## 7. 不进入公开课的内容
- 平台限制对抗细节。
- 未经验证的账号批次数据。
- 可被误解为高频触达或机械互动的执行细节。
- 学员无法自行判断风险的团队私有记录。

## 8. 暂停、降级、恢复、复盘机制
| 状态 | 触发信号 | 处理动作 |
|---|---|---|
| 暂停 | 登录验证、动作失败、负面反馈、异常提醒 | 停止当日动作，记录账号、时间、现象 |
| 降级 | 回复质量低、隐藏率高、素材重复 | 回到浏览、内容准备和人工审核 |
| 恢复 | 连续观察稳定，且风险事件可解释 | 小范围恢复，不直接扩大动作规模 |
| 复盘 | 第 7 天和第 14 天 | 判断继续、优化、暂停或换平台入口 |

## 9. 证据转译区
| 依据 ID | 类型 | 可信度 | 公开策略解释 |
|---|---|---|---|
{evidence_rows}

## 10. 课程作业
- 为 {platform['display']} 写出 3 个内容入口和 3 个互动入口。
- 写一份账号安全检查表。
- 写一份第 7 天复盘表。
- 把一个黄色动作改写成人工审核流程。
"""
    return redact_public_text(content, brand_config)


def render_internal_ops_sop(
    brief: dict,
    evidence_pack: dict,
    brand_config: dict,
    lang: str | None = "zh-CN",
) -> str:
    brand = public_brand(brand_config)
    profile = sop_profile_for_brief(brief, brand_config, lang)
    platform = platform_profile((brief.get("platforms") or ["instagram"])[0])
    content = f"""---
type: internal_ops_sop
visibility: internal_only
public_brand: {brand}
sop_id: {profile['sop_id']}-INTERNAL
platform: {platform['display']}
status: internal_draft
---

# {profile['title']} 内部执行版 SOP

## 1. 内部实验假设
- 目标: {brief.get('product_or_offer', 'unknown')}
- 平台: {platform['display']}
- 账号数量: {brief.get('account_count', 'unknown')}
- 账号阶段: {brief.get('account_stage', 'unknown')}
- 周期: {brief.get('duration_days', 14)} 天
- 风险偏好: {brief.get('risk_tolerance', 'conservative')}

## 2. 账号分层与资产准备
| 分层 | 进入条件 | 允许动作 | 暂停条件 |
|---|---|---|---|
| 新号 | 资料未稳定或历史活动少 | 浏览、内容准备、极轻互动 | 任何验证或动作异常 |
| 半熟号 | 有稳定登录和基础内容 | 小范围内容/评论验证 | 回复质量低或异常提醒 |
| 老号 | 有长期内容和互动记录 | 经人审的小批量测试 | 负面反馈或质量下降 |

## 3. 素材与话术准备
- 内容素材:
- 评论框架:
- 主页承接:
- 人工审核人:

## 4. 动作节奏记录
| 日期 | 账号批次 | 平台入口 | 动作 | 上限 | 观察指标 | 产出 |
|---|---|---|---|---|---|---|

## 5. 异常处理 SOP
| 异常 | 第一动作 | 复盘问题 | 恢复条件 |
|---|---|---|---|
| 登录验证 | 暂停该账号 | 环境、账号年龄、近期动作 | 重新稳定观察后再小范围恢复 |
| 动作失败 | 停止同类动作 | 是否频率过高、素材是否重复 | 降级到内容准备与浏览 |
| 负面反馈 | 停止相关话术 | 是否语境不匹配、是否太像推广 | 重写框架并重新人审 |
| 线索质量低 | 暂停放大 | 入口是否错误、用户画像是否偏差 | 换入口或换内容支柱 |

## 6. 不进入公开课程的内容
- 账号批次明细。
- 环境与代理记录。
- 每日动作参数和异常恢复记录。
- 未验证实验和失败复盘。

## 7. 复盘结论
- 第 7 天结论:
- 第 14 天结论:
- 下一轮测试条件:
"""
    return redact_public_text(content, brand_config)


def render_experiment_notes_template(brief: dict, brand_config: dict, lang: str | None = "zh-CN") -> str:
    brand = public_brand(brand_config)
    platform = platform_profile((brief.get("platforms") or ["instagram"])[0])
    content = f"""---
type: experiment_notes
visibility: internal_only
public_brand: {brand}
platform: {platform['display']}
status: internal_draft
---

# {brand} 内部实验记录

## 1. 实验边界
- 目标平台: {platform['display']}
- 目标产品/课程: {brief.get('product_or_offer', 'unknown')}
- 账号数量: {brief.get('account_count', 'unknown')}
- 账号阶段: {brief.get('account_stage', 'unknown')}
- 周期: {brief.get('duration_days', 14)} 天
- 本文件只用于团队内部复盘，不进入课程目录或公开导出。

## 2. 假设记录
| 假设 | 依据 | 验证方式 | 通过标准 | 暂停条件 |
|---|---|---|---|---|
| | | | | |

## 3. 执行参数记录
| 日期 | 账号批次 | 内容/评论入口 | 动作上限 | 人审负责人 | 备注 |
|---|---|---|---|---|---|

## 4. 异常与结论
| 时间 | 事件 | 影响范围 | 处理 | 结论 |
|---|---|---|---|---|

## 5. 下一轮建议
- 保留:
- 降级:
- 暂停:
- 需要补充:
"""
    return redact_public_text(content, brand_config)


def build_dual_sop_pack(
    brief: dict,
    evidence_pack: dict,
    brand_config: dict,
    lang: str | None = "zh-CN",
    visuals: str | None = "mermaid",
    data_dir: Path | None = None,
    depth: str | None = "brief",
) -> dict[str, str]:
    platform = (brief.get("platforms") or ["instagram"])[0]
    return {
        "PublicCourseSOP.md": render_public_course_sop(brief, evidence_pack, brand_config, lang=lang, visuals=visuals, data_dir=data_dir, depth=depth),
        "InternalOpsSOP.md": render_internal_ops_sop(brief, evidence_pack, brand_config, lang=lang),
        "BoundaryBrief.md": render_boundary_brief(platform, brand_config, lang=lang),
        "ExecutionLog.md": render_execution_log_template(brief, brand_config, lang=lang),
    }


def evidence_strategy_rows(evidence_pack: dict, brand_config: dict, limit: int = 8) -> str:
    rows = []
    for idx, item in enumerate(evidence_pack.get("items", [])[:limit], 1):
        basis_id = item.get("basis_id", f"PUB-{idx}")
        claim = redact_public_text(item.get("claim", ""), brand_config)
        lower = claim.lower()
        if "proxy" in lower or "account" in lower or "warm" in lower:
            strategy = "用于确认账号安全、代理隔离和冷启动节奏，转译为先检查环境、再限制动作量。"
        elif "content" in lower or "template" in lower or "publish" in lower:
            strategy = "用于确认内容和模板需要人审，转译为先准备素材与话术框架，再进入小批量验证。"
        elif "dm" in lower or "comment" in lower or "engagement" in lower:
            strategy = "用于确认互动动作必须保守，转译为低频评论、只跟进明确互动用户。"
        else:
            strategy = "作为内部知识依据使用，转译为保守执行、人工复核和可复盘记录。"
        rows.append(
            f"| {basis_id} | {item.get('claim_type', 'knowledge_fact')} | {item.get('confidence', 'unknown')} | {strategy} |"
        )
    return "\n".join(rows)


def deep_daily_rows_for_sop(brief: dict) -> list[dict]:
    if is_content_matrix_brief(brief):
        return [
            {"day": "第 1 天", "goal": "账号与内容资产盘点", "actions": "记录账号状态、素材数量、可发布主题、禁用动作；确认人审负责人。", "limit": "只做盘点和浏览", "observe": "账号登录、资料完整度、素材可用度", "output": "账号资产表、内容支柱草案"},
            {"day": "第 2 天", "goal": "赛道信号收集", "actions": "浏览同领域帖子，记录高频问题、钩子、评论需求，不复制原文。", "limit": "不发布、不私信", "observe": "常见痛点、互动强度、竞品内容形式", "output": "信号清单"},
            {"day": "第 3 天", "goal": "内容支柱确认", "actions": "确定 3-5 个内容支柱，每个支柱写 3 个选题。", "limit": "只起草，不发布", "observe": "选题与产品卖点是否一致", "output": "内容矩阵草表"},
            {"day": "第 4 天", "goal": "首批内容人审", "actions": "写标题、正文、CTA，检查是否夸张承诺或重复模板。", "limit": "每账号最多准备 1 条内容", "observe": "文案合规性和账号阶段匹配度", "output": "人审内容稿"},
            {"day": "第 5 天", "goal": "小批量发布验证", "actions": "发布或排程 1 条已审核内容，记录发布时间和主题。", "limit": "每健康账号 1 条", "observe": "发布成功率、初始互动", "output": "发布记录"},
            {"day": "第 6 天", "goal": "互动信号观察", "actions": "观察评论、收藏、主页访问，只回复明确相关的评论。", "limit": "不做批量回复", "observe": "高意向评论、负面反馈", "output": "互动记录"},
            {"day": "第 7 天", "goal": "中期复盘", "actions": "保留有效支柱，暂停弱内容，补充风险事件。", "limit": "不放量", "observe": "内容质量、账号稳定性", "output": "第 7 天复盘表"},
            {"day": "第 8 天", "goal": "第二批内容优化", "actions": "基于复盘改写钩子和 CTA，保留价值型表达。", "limit": "每账号最多 1 条", "observe": "主题清晰度", "output": "优化内容稿"},
            {"day": "第 9 天", "goal": "评论区线索识别", "actions": "记录用户问题、价格/链接/教程等信号，不主动硬推。", "limit": "只记录和轻量回复", "observe": "问题类型和需求强度", "output": "线索信号表"},
            {"day": "第 10 天", "goal": "轻量跟进边界确认", "actions": "只对明确互动用户做人工回复，不能批量私信。", "limit": "禁止批量私信", "observe": "回复质量和风险反馈", "output": "跟进记录"},
            {"day": "第 11 天", "goal": "复用有效角度", "actions": "把有效内容角度拆成 2-3 个变体，继续人审。", "limit": "不跨账号复制同文案", "observe": "变体差异度", "output": "变体清单"},
            {"day": "第 12 天", "goal": "稳定性检查", "actions": "检查账号、代理、发布成功率和异常反馈。", "limit": "异常账号暂停", "observe": "异常率、失败率", "output": "风险检查表"},
            {"day": "第 13 天", "goal": "准备结论", "actions": "汇总内容、互动、线索、风险事件，标注可放量条件。", "limit": "不新增高风险动作", "observe": "关键指标趋势", "output": "结论草稿"},
            {"day": "第 14 天", "goal": "最终复盘与下一阶段决策", "actions": "判断是否继续、暂停、优化或小幅扩大内容批次。", "limit": "放量必须人工批准", "observe": "账号存活、互动质量、线索质量", "output": "最终复盘表"},
        ]
    return [
        {"day": "第 1 天", "goal": "账号与环境确认", "actions": "逐个记录账号年龄、资料完整度、登录状态、代理绑定、VPS 环境和历史活跃。", "limit": "不做评论和私信", "observe": "登录是否稳定、是否有验证、代理是否重复", "output": "账号资产与环境检查表"},
        {"day": "第 2 天", "goal": "正常行为冷启动", "actions": "浏览信息流、观看 Reels/Stories、少量点赞收藏，不触发营销表达。", "limit": "每账号 0 条销售评论", "observe": "页面加载、动作失败、验证码、账号异常", "output": "冷启动行为记录"},
        {"day": "第 3 天", "goal": "轻量兴趣画像", "actions": "围绕目标赛道浏览内容，记录高频问题和潜在关键词。", "limit": "每账号最多 1 条非推广评论", "observe": "相关帖子质量、评论区真实度", "output": "目标帖子与关键词清单"},
        {"day": "第 4 天", "goal": "价值评论准备", "actions": "为 3 类目标帖子写价值型评论框架，全部进入人工审核。", "limit": "不复制同一模板", "observe": "话术是否像硬广、是否过度承诺", "output": "人审评论框架"},
        {"day": "第 5 天", "goal": "小量价值评论", "actions": "只在高度相关帖子下发布已审核价值评论。", "limit": "每健康账号 0-1 条", "observe": "评论是否展示、是否被隐藏、是否有回复", "output": "评论发布记录"},
        {"day": "第 6 天", "goal": "互动信号观察", "actions": "记录回复、点赞、主页访问和负面反馈，不主动私信。", "limit": "禁止批量跟进", "observe": "回复质量、潜在线索类型", "output": "互动信号表"},
        {"day": "第 7 天", "goal": "中期复盘", "actions": "暂停异常账号，保留有效帖子来源，淘汰弱话术。", "limit": "不增加动作量", "observe": "账号稳定性、回复率、风险事件", "output": "第 7 天复盘表"},
        {"day": "第 8 天", "goal": "高意向评论区识别", "actions": "寻找出现价格、链接、教程、工具、安全等问题的评论区。", "limit": "每账号 1-2 条评论", "observe": "需求明确度、帖子相关性", "output": "高意向信号清单"},
        {"day": "第 9 天", "goal": "话术微调", "actions": "把有效评论改成 2-3 个不同表达，保持价值优先。", "limit": "不跨账号复制同一表达", "observe": "重复度、自然度", "output": "评论变体清单"},
        {"day": "第 10 天", "goal": "轻量获客验证", "actions": "对明确相关帖子继续小量评论，记录回复与线索质量。", "limit": "每健康账号 1-2 条", "observe": "回复率、被隐藏率、负面反馈", "output": "轻量获客记录"},
        {"day": "第 11 天", "goal": "有限跟进判断", "actions": "只对主动互动或明确询问用户做人工回复，不做批量私信。", "limit": "禁止批量 DM", "observe": "用户是否明确请求更多信息", "output": "跟进边界记录"},
        {"day": "第 12 天", "goal": "风险压力检查", "actions": "检查代理、账号动作失败率、评论删除、隐藏、异常提醒。", "limit": "异常账号暂停 24-48 小时", "observe": "风险事件数量和连续性", "output": "风险检查表"},
        {"day": "第 13 天", "goal": "复盘资料准备", "actions": "汇总账号、评论、回复、线索、风险事件和有效帖子来源。", "limit": "不新增高风险动作", "observe": "数据完整性", "output": "最终复盘材料"},
        {"day": "第 14 天", "goal": "最终复盘与下一阶段决策", "actions": "判断继续保守验证、优化话术、暂停账号或小幅扩量。", "limit": "放量必须人工批准", "observe": "账号存活、合格线索、风险事件", "output": "第 14 天决策表"},
    ]


def render_deep_daily_table(brief: dict) -> str:
    lines = ["| 日期 | 目标 | 具体动作 | 上限 | 观察指标 | 当日产出 |", "|---|---|---|---|---|---|"]
    for row in deep_daily_rows_for_sop(brief):
        lines.append(f"| {row['day']} | {row['goal']} | {row['actions']} | {row['limit']} | {row['observe']} | {row['output']} |")
    return "\n".join(lines)


def render_deep_execution_checklist(brief: dict, brand_config: dict, lang: str | None = "zh-CN") -> str:
    brand = public_brand(brand_config)
    content = f"""# {brand} 深度 SOP 执行检查表

## 1. 账号检查
| 检查项 | 标准 | 记录 |
|---|---|---|
| 账号年龄 | 新号、半熟号、老号必须分层 | |
| 资料完整度 | 头像、简介、链接、基础内容完整 | |
| 登录状态 | 无异常验证、无频繁掉线 | |
| 历史活跃 | 有正常浏览、点赞、发布或互动记录 | |

## 2. 环境检查
| 检查项 | 标准 | 记录 |
|---|---|---|
| 代理绑定 | 默认一账号一代理 | |
| 重复代理 | 不允许重复绑定未评估的账号 | |
| VPS/设备 | 登录环境稳定，避免频繁切换 | |
| 操作窗口 | 明确每日执行时段和暂停时间 | |

## 3. 素材与话术检查
| 检查项 | 标准 | 记录 |
|---|---|---|
| 目标帖子来源 | 与产品/课程强相关 | |
| 评论框架 | 价值优先，不硬推 | |
| 禁止动作 | 批量私信、高频评论、复制模板均禁止 | |
| 人工审核 | 每条可外发内容必须有人审 | |

## 4. 执行前确认
- 风险结论如果是 `revise`，只能作为文档和保守验证使用，不能放量。
- 任何账号出现验证、限流、负面反馈，先暂停再复盘。
- 执行人员每天必须填写每日记录和风险事件。
"""
    return redact_public_text(content, brand_config)


def render_deep_review_rubric(brief: dict, brand_config: dict, lang: str | None = "zh-CN") -> str:
    brand = public_brand(brand_config)
    content = f"""# {brand} 深度 SOP 复盘评分表

## 1. 评分维度
| 维度 | 0 分 | 1 分 | 2 分 | 得分 |
|---|---|---|---|---|
| 账号安全 | 多个账号异常或未记录 | 有少量异常但有记录 | 账号稳定且记录完整 | |
| 环境稳定 | 代理/VPS 不明 | 部分明确 | 全部明确且无重复风险 | |
| 动作合规 | 有高频或批量动作 | 基本保守但记录不足 | 完全按上限执行 | |
| 内容质量 | 明显模板化或硬广 | 有价值但不够贴合 | 贴合场景且人审通过 | |
| 线索质量 | 无相关互动 | 有回复但意向弱 | 有明确需求或主动询问 | |
| 复盘完整度 | 无数据 | 数据不完整 | 每日记录完整 | |

## 2. 第 7 天中期复盘
- 是否有账号异常:
- 哪类帖子或内容最相关:
- 哪些评论/内容应暂停:
- 哪些字段仍然未知:
- 是否允许进入第 8-14 天轻量验证:

## 3. 第 14 天最终复盘
- 账号存活率:
- 评论/内容成功率:
- 回复率:
- 合格线索数:
- 风险事件:
- 下一阶段建议: 继续保守验证 / 优化话术 / 暂停项目 / 小幅扩量

## 4. 放量条件
只有当账号环境明确、风险事件可控、回复质量稳定、人工审核机制存在时，才允许讨论下一阶段放量。放量不是默认结果，而是复盘后的人工决策。
"""
    return redact_public_text(content, brand_config)


def render_deep_sop_markdown(
    brief: dict,
    evidence_pack: dict,
    brand_config: dict,
    lang: str | None = "zh-CN",
    visuals: str | None = "mermaid",
    data_dir: Path | None = None,
) -> str:
    brand = public_brand(brand_config)
    profile = sop_profile_for_brief(brief, brand_config, lang)
    visual_sections = render_visual_sections(brief, lang, visuals)
    media_sections = ""
    if (visuals or "").lower() in {"media", "all"} and data_dir is not None:
        media_sections = render_media_sections(brief, data_dir, brand_config, lang)
    daily_table = render_deep_daily_table(brief)
    evidence_rows = evidence_strategy_rows(evidence_pack, brand_config, limit=10)
    checklist = render_deep_execution_checklist(brief, brand_config, lang)
    rubric = render_deep_review_rubric(brief, brand_config, lang)
    keywords = ", ".join(brief.get("resources", {}).get("keywords", [])) or "待定义"
    content = f"""---
type: sop
sop_depth: deep
sop_id: {profile["sop_id"]}
status: deep_execution_manual
public_brand: {brand}
scenario: {profile["scenario"]}
platforms: [{", ".join(brief.get("platforms", []))}]
duration_days: {brief.get('duration_days', 14)}
risk_level: {brief.get('risk_tolerance', 'conservative')}
---

# {profile["title"]} 深度执行手册

## 0. 使用说明
这份文档是执行手册，不是自动化放量指令。它的用途是把营销需求转成可检查、可执行、可复盘的保守验证流程。任何真实账号动作都必须经过人工确认，并且必须以账号安全、平台合规和品牌安全为前提。

本手册适合团队内部执行、学员训练和项目复盘。它不适合直接复制成批量动作，也不适合在账号环境、代理资源、素材质量和人工审核人员都未知的情况下执行。

{visual_sections}
{media_sections}

## 1. 项目背景与目标拆解
- 对外品牌: {brand}
- 平台: {", ".join(brief.get("platforms", []))}
- 产品/课程: {brief.get('product_or_offer', 'unknown')}
- 账号数量: {brief.get('account_count', 'unknown')}
- 账号阶段: {brief.get('account_stage', 'unknown')}
- 执行周期: {brief.get('duration_days', 14)} 天
- 风险偏好: {brief.get('risk_tolerance', 'conservative')}
- 关键词: {keywords}

项目目标不是在 14 天内追求最大动作量，而是验证三个问题：账号是否稳定、目标评论区或内容方向是否有真实意向、轻量互动是否能带来可复盘的线索。只要其中任一项数据不足，下一阶段都应继续保守验证，而不是直接放量。

## 2. 适用对象与不适用场景
适用对象:
- 新账号或账号成熟度未知的冷启动项目。
- 需要建立评论区轻获客、内容矩阵或轻量互动 SOP 的团队。
- 需要把内部知识库转成培训材料、执行手册和复盘模板的场景。

不适用场景:
- 需要立即大规模私信、刷评论、刷互动的项目。
- 没有代理/账号/素材检查记录的项目。
- 无人负责人工审核、无人记录风险事件的项目。
- 希望把自动化工具当成无监督增长机器的项目。

## 3. 执行前检查清单
### 账号与环境
- 记录账号年龄、资料完整度、登录状态、历史活跃和最近异常。
- 确认代理绑定，默认一账号一代理，不把多个高风险账号放在同一代理上。
- 记录 VPS 或设备环境，避免短时间频繁切换登录环境。
- 给账号分组: 新号、半熟号、老号、异常观察组。

### 素材与人员
- 明确产品卖点、目标用户、禁用表达和人工审核负责人。
- 准备价值型评论框架，不准备批量复制模板。
- 准备每日记录表、风险事件表和第 7/14 天复盘表。
- 所有外发评论、内容、CTA 都必须先经过人工检查。

## 4. 账号分层策略
| 账号层级 | 判断方式 | 允许动作 | 禁止动作 | 复盘重点 |
|---|---|---|---|---|
| 新号 | 新注册、历史活跃少、资料刚完善 | 浏览、观看、轻点赞、少量价值评论 | 批量评论、批量私信、重复模板 | 是否触发验证、动作失败、评论隐藏 |
| 半熟号 | 有一定历史活跃，近期稳定 | 小量评论、内容测试、轻量互动 | 高频动作、跨账号复制话术 | 回复质量、账号稳定、负面反馈 |
| 老号 | 长期稳定、有真实内容或互动 | 可做更完整的内容验证 | 未复盘前仍不放量 | 是否能承接线索、是否适合扩量 |
| 异常组 | 有验证、限流、代理异常、负面反馈 | 观察、暂停、修复资料 | 所有外联动作 | 异常原因和恢复条件 |

## 5. 14 天逐日执行表
{daily_table}

## 6. 评论区轻获客话术框架
本系统不生成垃圾评论，也不鼓励复制模板。这里只提供人审结构:

| 场景 | 结构 | 示例方向 | 人审标准 |
|---|---|---|---|
| 用户问工具 | 先确认问题，再给判断维度 | “如果你主要卡在 X，可以先看 Y 指标。” | 不直接硬推，不夸张承诺 |
| 用户问价格 | 先解释适用对象，再引导比较 | “价格要看账号规模和目标，不建议只看单价。” | 不虚构价格，不诱导成交 |
| 用户问教程 | 先给步骤框架，再邀请进一步交流 | “可以先按 账号-环境-内容-复盘 四步拆。” | 不批量私信，只响应明确需求 |
| 用户表达痛点 | 先共情，再给一个低风险建议 | “先把动作量降下来，确认代理和账号分组。” | 不制造焦虑，不承诺结果 |

## 7. 高意向信号识别表
| 信号类型 | 关键词/行为 | 意向判断 | 动作建议 |
|---|---|---|---|
| 价格信号 | price、cost、多少钱、贵不贵 | 有预算或比较意图 | 记录，不直接报价承诺 |
| 教程信号 | how、教程、怎么做、流程 | 需要方法 | 回复框架型建议 |
| 工具信号 | tool、software、automation、工具 | 正在找方案 | 给选择维度，不硬推 |
| 安全信号 | safe、ban、封号、代理 | 风险意识强 | 强调保守验证和账号安全 |
| 链接信号 | link、demo、案例 | 可能进入线索阶段 | 只在明确请求后有限跟进 |

## 8. 风险分级与暂停机制
| 风险级别 | 表现 | 处理 |
|---|---|---|
| 低 | 个别评论无回复、互动少 | 继续观察，优化话术 |
| 中 | 评论被隐藏、动作失败、回复质量低 | 降低动作量，暂停异常账号 |
| 高 | 验证码、登录异常、代理失效、负面反馈集中 | 立即暂停 24-48 小时并复盘 |
| 阻断 | 批量私信、高频评论、重复模板被识别 | 停止执行，重新设计 SOP |

## 9. 异常处理 SOP
### 验证码或登录验证
立即暂停该账号所有外联动作，记录发生时间、代理、设备、最近动作。恢复前只允许检查资料和环境，不允许继续评论或私信。

### 动作限制或限流
停止该账号当天动作，把它放入异常观察组。复盘是否动作过密、话术重复、帖子相关性不足或代理不稳定。

### 代理失效或重复绑定
暂停相关账号，确认是否存在多个账号共享同一代理。代理问题未解决前，不允许进入第 8-14 天轻量获客阶段。

### 负面反馈或评论被隐藏
检查评论是否像广告、是否重复、是否与帖子不相关。出现连续负面反馈时，先改话术框架，再恢复低频测试。

### 回复率异常低
不要直接增加评论量。先检查目标帖子选择、评论价值、产品匹配度和用户意图，再决定是否继续。

## 10. 人工审核标准
每条评论或跟进内容必须满足:
- 与目标帖子和用户问题相关。
- 不夸张承诺，不虚构案例，不制造焦虑。
- 不出现批量复制痕迹。
- 不绕过平台规则，不诱导违规行为。
- 能解释为什么这条内容对用户有价值。

审核人必须给出三种结果之一：通过、修改后通过、拒绝。拒绝内容要记录原因，作为下一轮话术优化依据。

## 11. 每日记录模板
| 日期 | 账号组 | 动作数 | 回复 | 线索 | 风险事件 | 调整 |
|---|---|---:|---:|---:|---|---|
| | 新号组 | | | | | |
| | 半熟号组 | | | | | |
| | 老号组 | | | | | |

## 12. 第 7 天中期复盘
第 7 天不做放量决策，只判断是否允许进入第 8-14 天轻量验证。复盘问题:
- 哪些账号稳定，哪些账号需要暂停？
- 哪些目标帖子或内容方向最相关？
- 哪些评论框架有回复，哪些像广告？
- 代理和环境是否还有未知字段？
- 是否出现任何需要阻断的风险？

## 13. 第 14 天最终复盘
第 14 天输出下一阶段建议:
- 继续保守验证: 数据不足但账号安全。
- 优化话术: 有互动但线索质量弱。
- 暂停项目: 风险过高或账号异常集中。
- 小幅扩量: 账号稳定、回复质量可接受、人工审核机制完整。

## 14. 证据转译区
| 公开依据 ID | 类型 | 可信度 | 转译成执行策略 |
|---|---|---|---|
{evidence_rows}

## 15. 下一阶段放量条件
只有满足以下条件，才允许讨论下一阶段:
- 账号环境和代理资源已明确。
- 14 天内没有连续高风险事件。
- 价值型评论或内容方向有稳定回复。
- 人工审核流程可以持续执行。
- 每日记录和复盘评分完整。

如果任一条件不满足，下一阶段不是放量，而是继续补充资料、降低动作量或重新设计目标场景。

## 16. 执行检查表
{checklist}

## 17. 复盘评分表
{rubric}
"""
    return redact_public_text(content, brand_config)


def render_sop_markdown(
    brief: dict,
    evidence_pack: dict,
    brand_config: dict,
    lang: str | None = "zh-CN",
    visuals: str | None = "none",
    data_dir: Path | None = None,
    depth: str | None = "brief",
) -> str:
    brand = public_brand(brand_config)
    lang = normalize_lang(lang)
    if normalize_depth(depth) == "course" and is_zh_lang(lang):
        return render_public_course_sop(
            brief,
            evidence_pack,
            brand_config,
            lang=lang,
            visuals=visuals or "mermaid",
            data_dir=data_dir,
            depth="course",
        )
    if normalize_depth(depth) == "deep" and is_zh_lang(lang):
        return render_deep_sop_markdown(brief, evidence_pack, brand_config, lang=lang, visuals=visuals or "mermaid", data_dir=data_dir)
    profile = sop_profile_for_brief(brief, brand_config, lang)
    evidence_ids = [item.get("basis_id") for item in evidence_pack.get("items", [])[:8]]
    evidence_lines = "\n".join(
        f"| {item.get('basis_id')} | {item.get('claim_type')} | {item.get('confidence')} | {item.get('claim')} |"
        for item in evidence_pack.get("items", [])[:8]
    )
    phase_lines = "\n".join(
        f"| {row['days']} | {row['goal']} | {row['actions']} | {row['limit']} |"
        for row in phase_rows_for_sop(brief, lang)
    )
    rules_lines = "\n".join(f"- {rule}" for rule in profile["rules"])
    keywords = ", ".join(brief.get("resources", {}).get("keywords", [])) or bilingual_label("待定义", "to be defined", lang)
    visual_sections = render_visual_sections(brief, lang, visuals)
    media_sections = ""
    if (visuals or "").lower() in {"media", "all"} and data_dir is not None:
        media_sections = render_media_sections(brief, data_dir, brand_config, lang)
    if is_zh_lang(lang):
        content = f"""---
type: sop
sop_id: {profile["sop_id"]}
status: draft_for_review
public_brand: {brand}
scenario: {profile["scenario"]}
platforms: [{", ".join(brief.get("platforms", []))}]
duration_days: {brief.get('duration_days', 14)}
risk_level: {brief.get('risk_tolerance', 'conservative')}
evidence: [{", ".join(evidence_ids)}]
---

# {profile["title"]}

{visual_sections}
{media_sections}

## 1. 任务简报
- 对外品牌: {brand}
- 产品/课程: {brief.get('product_or_offer', 'unknown')}
- 账号数量: {brief.get('account_count', 'unknown')}
- 账号阶段: {brief.get('account_stage', 'unknown')}
- 风险偏好: {brief.get('risk_tolerance', 'conservative')}
- 关键词: {keywords}

## 2. 内部依据映射
| 依据 ID | 类型 | 可信度 | 公开摘要 |
|---|---|---|---|
{evidence_lines}

## 3. 账号与环境清单
- 执行前必须记录账号年龄、登录状态、资料完整度和历史活跃情况。
- 执行前必须记录代理和 VPS 状态。
- 未知字段不允许作为放量依据，只能进入保守验证。

## 4. 代理与分组计划
- 默认采用一账号一代理。
- 执行前检查并避免重复代理绑定。
- 按账号年龄、代理、VPS、风险等级和项目目的分组。

## 5. 14 天执行节奏
| 阶段 | 目标 | 动作 | 限制 |
|---|---|---|---|
{phase_lines}

## 6. {profile["section6"]}
{rules_lines}

## 7. {profile["section7"]}
- 前 14 天禁止批量私信。
- 只有当用户明确互动或主动询问时，才允许有限跟进。
- 是否进入私信放量阶段，必须放到第 14 天复盘后决定。

## 8. 暂停条件
- 登录验证、验证码、动作限制或评论失败率异常。
- 代理失效或重复代理绑定。
- 出现负面反馈、评论被隐藏、重复删除或疑似垃圾互动。
- 任一账号超过当日计划，次日降级为观察状态。

## 9. 每日记录
| 日期 | 活跃账号 | 评论/内容数 | 回复 | 线索 | 风险事件 | 调整 |
|---|---:|---:|---:|---:|---|---|

## 10. 第 14 天复盘
- 保持活跃的账号:
- 暂停的账号:
- 最有效的来源/选题:
- 最有效的人审模板:
- 合格线索:
- 风险事件:
- 下一阶段决策:
"""
        return redact_public_text(content, brand_config)
    content = f"""---
type: sop
sop_id: {profile["sop_id"]}
status: draft_for_review
public_brand: {brand}
scenario: {profile["scenario"]}
platforms: [{", ".join(brief.get("platforms", []))}]
duration_days: {brief.get('duration_days', 14)}
risk_level: {brief.get('risk_tolerance', 'conservative')}
evidence: [{", ".join(evidence_ids)}]
---

# {profile["title"]}

{visual_sections}
{media_sections}

## 1. Task Brief
- Public brand: {brand}
- Offer: {brief.get('product_or_offer', 'unknown')}
- Account count: {brief.get('account_count', 'unknown')}
- Account stage: {brief.get('account_stage', 'unknown')}
- Risk tolerance: {brief.get('risk_tolerance', 'conservative')}
- Keywords: {keywords}

## 2. Evidence Map
| Basis ID | Claim type | Confidence | Claim |
|---|---|---|---|
{evidence_lines}

## 3. Account And Environment Inventory
- Account age, login status, profile completeness, and historical activity must be recorded before execution.
- Proxy and VPS status must be recorded before execution.
- Unknown fields remain blockers for scale-up decisions.

## 4. Proxy And Grouping Plan
- Use one account per proxy as the default safest setup.
- Disable duplicate proxy binding before any outreach workflow.
- Group accounts by account age, proxy, VPS, risk level, and campaign purpose.

## 5. 14-Day Execution Rhythm
| Stage | Goal | Actions | Limit |
|---|---|---|---|
{phase_lines}

## 6. {profile["section6"]}
{rules_lines}

## 7. {profile["section7"]}
- Mass DM is forbidden in this 14-day SOP.
- Limited DM is allowed only after the user has interacted or clearly requested more information.
- Move any DM scale-up decision to the Day 14 review.

## 8. Pause Conditions
- Login verification, captcha, action block, or repeated comment failure.
- Duplicate proxy binding or proxy failure.
- Negative feedback, hidden comments, repeated deletions, or spam-like responses.
- Any account exceeding the daily plan is downgraded to observation the next day.

## 9. Daily Log
| Date | Active accounts | Comments sent | Replies | Leads | Risk events | Adjustment |
|---|---:|---:|---:|---:|---|---|

## 10. Day 14 Review
- Accounts kept active:
- Accounts paused:
- Best comment sources:
- Best reviewed templates:
- Qualified leads:
- Risk events:
- Decision for next phase:
"""
    return redact_public_text(content, brand_config)


def run_sop(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    brief = load_json_file(args.brief)
    evidence_pack = load_json_file(args.evidence)
    if not evidence_pack.get("items"):
        print("No evidence items found. Generate an EvidencePack before creating a SOP.", file=sys.stderr)
        return 1
    sop_layer = normalize_sop_layer(getattr(args, "sop_layer", "standard"))
    if sop_layer == "dual":
        pack = build_dual_sop_pack(
            brief,
            evidence_pack,
            brand_config,
            lang=getattr(args, "lang", "zh-CN"),
            visuals=getattr(args, "visuals", "none"),
            data_dir=Path(args.data_dir),
            depth=getattr(args, "depth", "brief"),
        )
        if args.format == "json":
            write_json_or_print(pack, args.out, dry_run=args.dry_run)
        elif args.out:
            if not args.dry_run:
                write_named_files(Path(args.out), pack, brand_config)
                print(f"Wrote dual SOP pack: {args.out}")
            else:
                print("\n".join(pack))
        else:
            print("\n\n--- PublicCourseSOP.md ---\n\n")
            print(pack["PublicCourseSOP.md"])
            print("\n\n--- InternalOpsSOP.md ---\n\n")
            print(pack["InternalOpsSOP.md"])
            print("\n\n--- BoundaryBrief.md ---\n\n")
            print(pack["BoundaryBrief.md"])
            print("\n\n--- ExecutionLog.md ---\n\n")
            print(pack["ExecutionLog.md"])
        return 0
    if sop_layer == "public":
        content = render_public_course_sop(
            brief,
            evidence_pack,
            brand_config,
            lang=getattr(args, "lang", "zh-CN"),
            visuals=getattr(args, "visuals", "none"),
            data_dir=Path(args.data_dir),
            depth=getattr(args, "depth", "brief"),
        )
    elif sop_layer == "internal":
        content = render_internal_ops_sop(
            brief,
            evidence_pack,
            brand_config,
            lang=getattr(args, "lang", "zh-CN"),
        )
    else:
        content = render_sop_markdown(
            brief,
            evidence_pack,
            brand_config,
            lang=getattr(args, "lang", "zh-CN"),
            visuals=getattr(args, "visuals", "none"),
            data_dir=Path(args.data_dir),
            depth=getattr(args, "depth", "brief"),
        )
    if args.format == "json":
        profile = sop_profile_for_brief(brief, brand_config, getattr(args, "lang", "zh-CN"))
        data = {
            "sop_id": profile["sop_id"],
            "public_brand": public_brand(brand_config),
            "sop_layer": sop_layer,
            "markdown": content,
        }
        write_json_or_print(data, args.out, dry_run=args.dry_run)
    else:
        write_or_print(content, args.out, dry_run=args.dry_run)
    return 0


def audit_decision_for_inputs(brief: dict, evidence_pack: dict, sop_text: str) -> tuple[str, list[str], list[str]]:
    blockers: list[str] = []
    required_changes: list[str] = []
    forbidden = set(brief.get("forbidden_actions", []))
    allowed = set(brief.get("allowed_actions", []))
    resources = brief.get("resources", {})
    account_stage = str(brief.get("account_stage", "unknown")).lower()

    if not evidence_pack.get("items"):
        blockers.append("EvidencePack is empty.")
        required_changes.append("Generate source-backed evidence before SOP approval.")
    if resources.get("proxies", "unknown") == "unknown":
        blockers.append("Proxy inventory is unknown.")
        required_changes.append("Record proxy count and one-account-one-proxy binding status.")
    if account_stage in {"new", "unknown"}:
        blockers.append("Account maturity is new or unknown.")
        required_changes.append("Keep the SOP in conservative warm-up and light validation mode.")
    if "mass_dm" in allowed or "mass_dm" not in forbidden:
        blockers.append("Mass DM is not explicitly forbidden in the task policy.")
        required_changes.append("Forbid mass DM in the first 14 days.")
    if "high_frequency_comment" in allowed:
        blockers.append("High-frequency commenting is allowed.")
        required_changes.append("Limit comments to conservative daily validation ranges.")

    decision = "pass"
    if any("Mass DM" in item or "High-frequency" in item for item in blockers):
        decision = "block"
    elif blockers:
        decision = "revise"
    return decision, blockers, required_changes


def risk_audit_id_for_brief(brief: dict) -> str:
    return f"RISK-AUDIT-{slugify(str(brief.get('task_id', 'task')), 'task').upper()}"


def render_risk_audit_markdown(
    brief: dict,
    evidence_pack: dict,
    sop_text: str,
    brand_config: dict,
    lang: str | None = "zh-CN",
) -> str:
    decision, blockers, required_changes = audit_decision_for_inputs(brief, evidence_pack, sop_text)
    brand = public_brand(brand_config)
    lang = normalize_lang(lang)
    blocker_lines = "\n".join(f"- {translate_known_issue(item, lang)}" for item in blockers) or f"- {bilingual_label('无', 'None', lang)}"
    change_lines = "\n".join(f"- {translate_known_issue(item, lang)}" for item in required_changes) or f"- {bilingual_label('无', 'None', lang)}"
    if is_zh_lang(lang):
        content = f"""---
type: risk_audit
audit_id: {risk_audit_id_for_brief(brief)}
public_brand: {brand}
decision: {decision}
overall_risk: {"high" if decision == "block" else "medium" if decision == "revise" else "low"}
human_review_required: true
---

# {brand} 风险审核

## 审核结论
{localized_decision(decision, lang)}

## 阻断/修订原因
{blocker_lines}

## 必须补充
{change_lines}

## 暂停条件
- 登录验证
- 验证码
- 动作限制
- 评论或发布失败率异常
- 重复代理绑定
- 代理失效
- 负面反馈或疑似垃圾互动

## 人工复核
执行前必须由人工复核。本审核只确认文档质量与风险边界，不代表自动执行任何平台动作。
"""
        return redact_public_text(content, brand_config)
    content = f"""---
type: risk_audit
audit_id: {risk_audit_id_for_brief(brief)}
public_brand: {brand}
decision: {decision}
overall_risk: {"high" if decision == "block" else "medium" if decision == "revise" else "low"}
human_review_required: true
---

# {brand} Risk Audit

## Decision
{decision}

## Blockers
{blocker_lines}

## Required Changes
{change_lines}

## Pause Conditions
- Login verification
- Captcha
- Action block
- Comment failure spike
- Duplicate proxy binding
- Proxy failure
- Negative or spam-like feedback

## Human Review
Human review is required before execution. This audit approves documentation quality only; it does not execute platform actions.
"""
    return redact_public_text(content, brand_config)


def run_risk_audit(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    brief = load_json_file(args.brief)
    evidence_pack = load_json_file(args.evidence)
    sop_text = Path(args.sop).read_text(encoding="utf-8") if args.sop else ""
    content = render_risk_audit_markdown(brief, evidence_pack, sop_text, brand_config, getattr(args, "lang", "zh-CN"))
    if args.format == "json":
        decision, blockers, required_changes = audit_decision_for_inputs(brief, evidence_pack, sop_text)
        write_json_or_print(
            {
                "audit_id": risk_audit_id_for_brief(brief),
                "public_brand": public_brand(brand_config),
                "decision": decision,
                "blockers": blockers,
                "required_changes": required_changes,
                "human_review_required": True,
            },
            args.out,
            dry_run=args.dry_run,
        )
    else:
        write_or_print(content, args.out, dry_run=args.dry_run)
    return 0


def extract_risk_decision(risk_text: str) -> str:
    match = re.search(r"decision:\s*(pass|revise|block)", risk_text, flags=re.I)
    if match:
        return match.group(1).lower()
    for value in ["block", "revise", "pass"]:
        if re.search(rf"^## Decision\s+{value}\b", risk_text, flags=re.I | re.M):
            return value
    return "unknown"


def extract_markdown_section(text: str, heading_prefix: str) -> str:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading_prefix)}.*?$([\s\S]*?)(?=^##\s+|\Z)",
        flags=re.M,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def extract_first_heading(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+?)\s*$", text, flags=re.M)
    return match.group(1).strip() if match else fallback


def markdown_from_json(title: str, data: dict, brand_config: dict) -> str:
    return redact_public_text(
        f"# {title}\n\n```json\n{json.dumps(data, ensure_ascii=False, indent=2)}\n```\n",
        brand_config,
    )


def build_project_package_files(
    brief: dict,
    evidence_pack: dict,
    sop_text: str,
    risk_text: str,
    brand_config: dict,
    run_id: str,
    lang: str | None = "zh-CN",
    depth: str | None = "brief",
    sop_layer: str | None = "standard",
    dual_sop_pack: dict[str, str] | None = None,
    project_id: str | None = None,
) -> dict[str, str]:
    decision = extract_risk_decision(risk_text)
    layer = normalize_sop_layer(sop_layer)
    manifest_project_id = project_id or str(brief.get("task_id") or "aivamax-project")
    if is_zh_lang(lang):
        files = {
            "00_Brief.md": markdown_from_json(f"{public_brand(brand_config)} 任务简报", brief, brand_config),
            "01_Evidence-Pack.md": render_evidence_pack_markdown(evidence_pack),
            "02_Risk-Review.md": redact_public_text(risk_text, brand_config),
            "03_14-Day-SOP.md": redact_public_text(sop_text, brand_config),
            "04_Daily-Log.md": "# 每日记录\n\n| 日期 | 活跃账号 | 评论/内容数 | 回复 | 线索 | 风险事件 | 调整 |\n|---|---:|---:|---:|---:|---|---|\n",
            "05_Review.md": "# 项目复盘\n\n## 结果\n\n## 经验\n\n## 下一轮迭代\n\n",
            f"Runs/{run_id}.md": f"# 智能体运行记录\n\n- 任务: {brief.get('task_id')}\n- 证据包: {evidence_pack.get('evidence_pack_id')}\n- 风险结论: {localized_decision(decision, lang)}\n- 对外品牌: {public_brand(brand_config)}\n",
        }
        if normalize_depth(depth) in {"deep", "course"} and layer != "dual":
            files["06_Execution-Checklist.md"] = render_deep_execution_checklist(brief, brand_config, lang)
            files["07_Review-Rubric.md"] = render_deep_review_rubric(brief, brand_config, lang)
        if layer == "dual":
            pack = dual_sop_pack or build_dual_sop_pack(brief, evidence_pack, brand_config, lang=lang, depth=depth)
            files.update(build_dual_project_files(
                pack,
                execution_checklist=render_deep_execution_checklist(brief, brand_config, lang),
                review_rubric=render_deep_review_rubric(brief, brand_config, lang),
                experiment_notes=render_experiment_notes_template(brief, brand_config, lang),
                project_id=manifest_project_id,
                run_id=run_id,
            ))
        return files
    files = {
        "00_Brief.md": markdown_from_json(f"{public_brand(brand_config)} Brief", brief, brand_config),
        "01_Evidence-Pack.md": render_evidence_pack_markdown(evidence_pack),
        "02_Risk-Review.md": redact_public_text(risk_text, brand_config),
        "03_14-Day-SOP.md": redact_public_text(sop_text, brand_config),
        "04_Daily-Log.md": "# Daily Log\n\n| Date | Active accounts | Comments sent | Replies | Leads | Risk events | Adjustment |\n|---|---:|---:|---:|---:|---|---|\n",
        "05_Review.md": "# Review\n\n## Results\n\n## Lessons\n\n## Next Iteration\n\n",
        f"Runs/{run_id}.md": f"# Agent Run\n\n- Task: {brief.get('task_id')}\n- Evidence pack: {evidence_pack.get('evidence_pack_id')}\n- Risk decision: {decision}\n- Public brand: {public_brand(brand_config)}\n",
    }
    if layer == "dual":
        pack = dual_sop_pack or build_dual_sop_pack(brief, evidence_pack, brand_config, lang=lang, depth=depth)
        files.update(build_dual_project_files(
            pack,
            execution_checklist=render_deep_execution_checklist(brief, brand_config, lang),
            review_rubric=render_deep_review_rubric(brief, brand_config, lang),
            experiment_notes=render_experiment_notes_template(brief, brand_config, lang),
            project_id=manifest_project_id,
            run_id=run_id,
        ))
    return files


def write_named_files(out_dir: Path, files: dict[str, str], brand_config: dict, force: bool = True) -> tuple[list[Path], list[Path]]:
    written: list[Path] = []
    skipped: list[Path] = []
    for name, content in files.items():
        path = out_dir / name
        if path.exists() and not force:
            skipped.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(redact_public_text(content, brand_config), encoding="utf-8")
        written.append(path)
    return written, skipped


def run_project(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    brief = load_json_file(args.brief)
    evidence_pack = load_json_file(args.evidence)
    sop_text = Path(args.sop).read_text(encoding="utf-8")
    risk_text = Path(args.risk).read_text(encoding="utf-8")
    decision = extract_risk_decision(risk_text)
    if decision == "unknown":
        print("Risk audit decision was not found. Run risk-audit before project.", file=sys.stderr)
        return 1

    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    project_id = args.project_id or f"{dt.datetime.now().date().isoformat()}_IG_Comment_LeadGen_14D"
    out_dir = Path(args.out) if args.out else matrix_root / "50_Projects" / project_id
    run_id = f"RUN-{dt.datetime.now(dt.UTC).strftime('%Y%m%d%H%M%S')}"
    sop_layer = normalize_sop_layer(getattr(args, "sop_layer", "standard"))
    dual_pack = None
    if sop_layer == "dual":
        dual_pack = build_dual_sop_pack(
            brief,
            evidence_pack,
            brand_config,
            lang=getattr(args, "lang", "zh-CN"),
            visuals="none",
            data_dir=data_dir,
            depth=getattr(args, "depth", "brief"),
        )
        sop_text = dual_pack["PublicCourseSOP.md"]
    files = build_project_package_files(
        brief,
        evidence_pack,
        sop_text,
        risk_text,
        brand_config,
        run_id,
        getattr(args, "lang", "zh-CN"),
        getattr(args, "depth", "brief"),
        sop_layer=sop_layer,
        dual_sop_pack=dual_pack,
        project_id=project_id,
    )
    if args.dry_run:
        print("\n".join(str(out_dir / name) for name in files))
        return 0
    write_named_files(out_dir, files, brand_config)
    print(f"Wrote AIvaMax project: {out_dir}")
    if decision == "block":
        print("Risk audit decision is block; this project is documentation-only and not approved for execution.")
    return 0


def read_project_file(project_dir: Path, filename: str) -> str:
    path = project_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"Missing project file: {path}")
    return path.read_text(encoding="utf-8", errors="ignore")


def resolve_existing_cli_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate
    root_candidate = ROOT / path
    if root_candidate.exists():
        return root_candidate
    return root_candidate


def build_course_module_files_from_texts(
    project_name: str,
    brief: str,
    evidence: str,
    risk: str,
    sop: str,
    module_id: str,
    brand_config: dict,
    lang: str | None = "zh-CN",
    visuals: str | None = "none",
    depth: str | None = "brief",
) -> dict[str, str]:
    brand = public_brand(brand_config)
    lang = normalize_lang(lang)
    rhythm = extract_markdown_section(sop, "5.")
    comment_rules = extract_markdown_section(sop, "6.")
    dm_boundary = extract_markdown_section(sop, "7.")
    pause_conditions = extract_markdown_section(sop, "8.")
    decision = extract_risk_decision(risk)
    module_title = extract_first_heading(sop, f"{brand} Account Safety And Lead-Generation SOP")
    if normalize_depth(depth) == "course" and is_zh_lang(lang):
        platform_match = re.search(r"^platform:\s*(.+)$", sop, flags=re.M)
        platform_name = platform_match.group(1).strip() if platform_match else "Instagram"
        files = render_course_grade_module_files(
            brand=brand,
            module_title=module_title,
            project_name=project_name,
            module_id=module_id,
            decision_label=localized_decision(decision, lang),
            platform_name=platform_name,
        )
        return {name: redact_public_text(content, brand_config) for name, content in files.items()}
    visual_note = ""
    if (visuals or "none").lower() in {"mermaid", "all"}:
        visual_note = f"\n## {bilingual_label('图文讲解建议', 'Visual Teaching Notes', lang)}\n\n- 先讲多智能体流程图，再讲 14 天执行节奏图。\n- 风险审核图用于解释为什么 `revise` 不是失败，而是进入补充信息阶段。\n- 内容矩阵或账号安全检查图用于课后作业。\n"
    deep_note = ""
    if normalize_depth(depth) in {"deep", "course"}:
        deep_note = """
## 深度执行手册讲解重点
- 先让学员识别适用与不适用场景，避免把 SOP 当成放量脚本。
- 重点训练执行前检查表、账号分层、每日记录和第 7/14 天复盘。
- 异常处理 SOP 要作为课堂案例演练，而不是附录略过。
- 证据转译区要让学员看到：公开证据 ID 如何变成具体执行边界。
"""
    if is_zh_lang(lang):
        files = {
            "00_Module-Overview.md": f"""---
type: course_module
public_brand: {brand}
module_id: {module_id}
source_project: {project_name}
status: draft
---

# {module_title}

## 课程定位
本模块教会学员如何把一个营销需求转成有证据、有风险边界、可复盘的 {brand} SOP。

## 学习目标
- 理解为什么账号安全优先于动作规模。
- 能读懂 TaskBrief，并识别缺失的执行条件。
- 能使用公开 EvidencePack，但不暴露内部来源信息。
- 能讲清楚 14 天保守验证节奏。
- 能判断 RiskAudit 的通过、修订或阻断含义。

## 来源项目
- 项目文件夹: {project_name}
- 风险结论: {localized_decision(decision, lang)}

## 必备材料
- TaskBrief
- EvidencePack
- SOPDraft
- RiskAudit
- 每日记录与复盘模板
{visual_note}
{deep_note}
""",
            "01_Lesson-Plan.md": f"""---
type: lesson_plan
public_brand: {brand}
module_id: {module_id}
status: draft
---

# 教案

## 第 1 课：矩阵工作流
讲解 TaskBrief -> EvidencePack -> SOPDraft -> RiskAudit -> CampaignMemory -> BrandAudit。

## 第 2 课：账号安全优先
用项目简报识别账号数量、账号阶段、代理状态、风险偏好和禁止动作。

## 第 3 课：14 天验证节奏
{rhythm or "以 SOP 中的 14 天执行节奏作为课程主线。"}

## 第 4 课：规则与跟进边界
### 操作规则
{comment_rules or "讲解 SOP 中的操作规则。"}

### 跟进边界
{dm_boundary or "讲解 SOP 中的跟进边界。"}

## 第 5 课：风险审核
风险结论: {localized_decision(decision, lang)}

告诉学员：`revise` 不是失败，而是需要补齐代理、账号成熟度、素材、人审负责人等关键输入后再执行。

## 第 6 课：深度执行复盘
围绕执行前检查表、异常处理 SOP、第 7 天中期复盘、第 14 天最终复盘进行小组演练。
""",
            "02_Workbook.md": f"""---
type: workbook
public_brand: {brand}
module_id: {module_id}
status: draft
---

# 学员练习册

## 练习 1：补全 TaskBrief
| 字段 | 学员填写 |
|---|---|
| 平台 | |
| 账号数量 | |
| 账号阶段 | |
| 代理资源 | |
| 产品/课程 | |
| 风险偏好 | |
| 禁止动作 | |

## 练习 2：证据分类
选 3 个公开证据 ID，判断它们如何影响 SOP：

| 证据 ID | 结论 | 事实或假设 | 对 SOP 的影响 |
|---|---|---|---|

## 练习 3：暂停条件
{pause_conditions or "列出账号、代理、内容、动作和反馈相关的暂停条件。"}

## 练习 4：第 14 天决策
| 指标 | 结果 | 决策影响 |
|---|---|---|
| 活跃账号 | | |
| 暂停账号 | | |
| 评论/内容数 | | |
| 回复数 | | |
| 合格线索 | | |
| 风险事件 | | |
""",
            "03_Instructor-Guide.md": f"""---
type: instructor_guide
public_brand: {brand}
module_id: {module_id}
status: draft
---

# 讲师指南

## 授课提醒
- 课程重点是系统化决策，不是教人找捷径。
- 公开证据 ID 可以用于教学，内部来源信息不能用于公开材料。
- 要让学员解释新号或未知账号为什么必须保守执行。
- RiskAudit 是必经闸口，不是可有可无的建议。

## 讨论问题
- 这个 TaskBrief 还缺什么信息？
- 哪个缺失字段会造成最大执行风险？
- 如果真实项目中出现风险，应该先触发哪个暂停条件？
- 进入私信或放量前必须复核什么？

## 品牌规则
授课时不得提及内部来源品牌、内部 URL、原始路径或 note_path。
""",
            "04_Assessment.md": f"""---
type: assessment
public_brand: {brand}
module_id: {module_id}
status: draft
---

# 考核

## 简答题
1. 为什么本 SOP 采用 14 天验证节奏，而不是立即放量？
2. `revise` 风险结论代表什么？
3. 为什么第一阶段禁止批量私信和高频动作？
4. 提升动作量之前必须知道哪些信息？
5. 为什么课程材料必须通过 BrandAudit？

## 实操任务
用同样流程，为一个新平台写出一页 {brand} SOP 大纲：

TaskBrief -> EvidencePack -> SOPDraft -> RiskAudit -> CampaignMemory -> BrandAudit。

## 通过标准
- 使用 {brand} 对外语言。
- 不暴露内部来源信息。
- 包含证据 ID。
- 包含暂停条件。
- 包含复盘步骤。
""",
        }
        return {name: redact_public_text(content, brand_config) for name, content in files.items()}
    files = {
        "00_Module-Overview.md": f"""---
type: course_module
public_brand: {brand}
module_id: {module_id}
source_project: {project_name}
status: draft
---

# {module_title}

## Positioning
This module teaches how to turn an account-safety and lead-generation request into a human-reviewed {brand} SOP.

## Learning Outcomes
- Explain why account safety comes before outreach volume.
- Read a TaskBrief and identify missing operational inputs.
- Use a public EvidencePack without exposing private source metadata.
- Walk through the 14-day conservative validation rhythm.
- Decide whether the RiskAudit result means pass, revise, or block.

## Source Project
- Project folder: {project_name}
- Risk decision: {decision}

## Required Materials
- TaskBrief
- EvidencePack
- SOPDraft
- RiskAudit
- Daily log and review template
""",
        "01_Lesson-Plan.md": f"""---
type: lesson_plan
public_brand: {brand}
module_id: {module_id}
status: draft
---

# Lesson Plan

## Lesson 1: Matrix Workflow
Teach the flow: TaskBrief -> EvidencePack -> SOPDraft -> RiskAudit -> CampaignMemory -> BrandAudit.

## Lesson 2: Account Safety First
Use the project brief to identify account count, account stage, proxy status, risk tolerance, and forbidden actions.

## Lesson 3: 14-Day Validation Rhythm
{rhythm or "Use the SOP 14-day execution rhythm as the teaching spine."}

## Lesson 4: Lead Rules And DM Boundaries
### Operating Rules
{comment_rules or "Review comment rules from the SOP."}

### Follow-Up Boundary
{dm_boundary or "Review DM boundaries from the SOP."}

## Lesson 5: Risk Review
Risk decision: {decision}

Teach that `revise` means the learner must fill missing operational inputs before execution.

## Instructor Close
End with a learner exercise: convert one marketing request into a TaskBrief and list the risk fields that must be known before execution.
""",
        "02_Workbook.md": f"""---
type: workbook
public_brand: {brand}
module_id: {module_id}
status: draft
---

# Workbook

## Exercise 1: TaskBrief Fill-In
| Field | Learner answer |
|---|---|
| Platform | |
| Account count | |
| Account stage | |
| Proxy inventory | |
| Offer | |
| Risk tolerance | |
| Forbidden actions | |

## Exercise 2: Evidence Classification
Pick three public evidence IDs and classify them:

| Evidence ID | Claim | Fact or assumption | How it affects the SOP |
|---|---|---|---|

## Exercise 3: Pause Conditions
{pause_conditions or "List account, proxy, content, action, and feedback pause conditions."}

## Exercise 4: Day 14 Decision
| Metric | Result | Decision impact |
|---|---|---|
| Accounts active | | |
| Accounts paused | | |
| Comments sent | | |
| Replies received | | |
| Qualified leads | | |
| Risk events | | |
""",
        "03_Instructor-Guide.md": f"""---
type: instructor_guide
public_brand: {brand}
module_id: {module_id}
status: draft
---

# Instructor Guide

## Teaching Notes
- Keep the lesson focused on systems thinking, not shortcuts.
- Emphasize that public evidence IDs are acceptable in training; private source details are not.
- Make learners explain why new or unknown accounts require conservative limits.
- Treat RiskAudit as a required gate, not as optional commentary.

## Discussion Prompts
- What information is missing from this TaskBrief?
- Which missing field creates the biggest execution risk?
- Which pause condition would you trigger first in a real campaign?
- What should be reviewed before deciding whether to enter a DM phase?

## Brand Rule
Do not mention private source brands, private source URLs, raw paths, or note paths while teaching.
""",
        "04_Assessment.md": f"""---
type: assessment
public_brand: {brand}
module_id: {module_id}
status: draft
---

# Assessment

## Short Answer
1. Why does this SOP use a 14-day validation rhythm instead of immediate scale-up?
2. What does a `revise` RiskAudit decision mean?
3. Why are mass DM and high-frequency comments forbidden in the first phase?
4. What must be known before increasing comment volume?
5. Why must course material pass BrandAudit?

## Practical Task
Create a one-page {brand} SOP outline for a new platform using the same flow:

TaskBrief -> EvidencePack -> SOPDraft -> RiskAudit -> CampaignMemory -> BrandAudit.

## Pass Criteria
- Uses {brand} public language.
- Does not expose private source details.
- Includes evidence IDs.
- Includes pause conditions.
- Includes a review step.
""",
    }
    return {name: redact_public_text(content, brand_config) for name, content in files.items()}


def build_course_module_files(
    project_dir: Path,
    module_id: str,
    brand_config: dict,
    lang: str | None = "zh-CN",
    visuals: str | None = "none",
    depth: str | None = "brief",
) -> dict[str, str]:
    return build_course_module_files_from_texts(
        project_name=project_dir.name,
        brief=read_project_file(project_dir, "00_Brief.md"),
        evidence=read_project_file(project_dir, "01_Evidence-Pack.md"),
        risk=read_project_file(project_dir, "02_Risk-Review.md"),
        sop=read_course_sop(project_dir),
        module_id=module_id,
        brand_config=brand_config,
        lang=lang,
        visuals=visuals,
        depth=depth,
    )


def run_course(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    project_dir = resolve_existing_cli_path(args.project)
    if not project_dir.exists():
        print(f"Project folder not found: {project_dir}", file=sys.stderr)
        return 1
    course_name = args.course_name or "AIvaMax账号安全与获客SOP课"
    module_id = slugify(args.module_id or project_dir.name, fallback="course-module")
    out_dir = Path(args.out) if args.out else matrix_root / "70_Courses" / course_name / module_id
    files = build_course_module_files(
        project_dir,
        module_id,
        brand_config,
        lang=getattr(args, "lang", "zh-CN"),
        visuals=getattr(args, "visuals", "none"),
        depth=getattr(args, "depth", "brief"),
    )
    written: list[Path] = []
    skipped: list[Path] = []
    for rel_path, content in files.items():
        path = out_dir / rel_path
        if path.exists() and not args.force:
            skipped.append(path)
            continue
        if not args.dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        written.append(path)
    if args.json:
        print(json.dumps({
            "course_dir": str(out_dir),
            "written": [str(path) for path in written],
            "skipped": [str(path) for path in skipped],
            "dry_run": args.dry_run,
        }, ensure_ascii=False, indent=2))
    else:
        action = "Would write" if args.dry_run else "Wrote"
        for path in written:
            print(f"{action}: {path}")
        for path in skipped:
            print(f"Skipped existing: {path}")
        print(f"AIvaMax course module: {out_dir}")
    return 0


def matrix_agent_flow() -> list[dict]:
    return [dict(item) for item in MATRIX_AGENT_FLOW]


def unique_directory_path(path: Path) -> Path:
    if not path.exists():
        return path
    for idx in range(2, 1000):
        candidate = path.with_name(f"{path.name}-{idx:02d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create a unique output directory for {path}")


def public_output_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def scan_many_brand_violations(paths: list[Path], brand_config: dict) -> list[dict]:
    violations: list[dict] = []
    for path in paths:
        violations.extend(scan_brand_violations(path, brand_config))
    return violations


def build_agent_run_record(
    run_id: str,
    request_goal: str,
    brief: dict,
    evidence_pack: dict,
    risk_decision: str,
    outputs: dict[str, str],
    checked_paths: list[Path],
    violation_count: int,
    brand_config: dict,
    lang: str | None = "zh-CN",
    visuals: str | None = "none",
    depth: str | None = "brief",
    sop_layer: str | None = "standard",
    artifact_violation_count: int = 0,
) -> dict:
    flow = []
    for idx, item in enumerate(matrix_agent_flow(), 1):
        flow.append({
            "order": idx,
            "agent": item["agent"],
            "tool": item["tool"],
            "responsibility": item["responsibility"],
            "status": "completed",
        })
    return {
        "type": "aivamax_matrix_agent_run",
        "run_id": run_id,
        "public_brand": public_brand(brand_config),
        "language": normalize_lang(lang),
        "visuals": visuals or "none",
        "depth": normalize_depth(depth),
        "sop_layer": normalize_sop_layer(sop_layer),
        "created_at": now_iso(),
        "request": {
            "goal": redact_public_text(request_goal, brand_config),
            "platforms": brief.get("platforms", []),
            "offer": redact_public_text(brief.get("product_or_offer", "unknown"), brand_config),
            "duration_days": brief.get("duration_days"),
        },
        "task_id": brief.get("task_id"),
        "evidence_pack_id": evidence_pack.get("evidence_pack_id"),
        "risk_decision": risk_decision,
        "agent_flow": flow,
        "outputs": outputs,
        "brand_audit": {
            "passed": violation_count == 0,
            "violation_count": violation_count,
            "checked_paths": [public_output_path(path) for path in checked_paths],
        },
        "artifact_audit": {
            "passed": artifact_violation_count == 0,
            "violation_count": artifact_violation_count,
        },
    }


def render_agent_run_markdown(record: dict, brand_config: dict, lang: str | None = "zh-CN") -> str:
    lang = normalize_lang(lang or record.get("language"))
    flow_lines = "\n".join(
        f"| {item.get('order')} | {item.get('agent')} | {item.get('tool')} | {item.get('status')} |"
        for item in record.get("agent_flow", [])
    )
    output_lines = "\n".join(
        f"- {name}: `{path}`"
        for name, path in record.get("outputs", {}).items()
    )
    audit = record.get("brand_audit", {})
    artifact_audit = record.get("artifact_audit", {})
    if is_zh_lang(lang):
        content = f"""---
type: agent_run
run_id: {record.get('run_id')}
public_brand: {record.get('public_brand')}
status: completed
---

# {record.get('public_brand')} 矩阵智能体运行记录

## 需求
- 目标: {record.get('request', {}).get('goal')}
- 平台: {", ".join(record.get('request', {}).get('platforms', []))}
- 产品/课程: {record.get('request', {}).get('offer')}
- 周期: {record.get('request', {}).get('duration_days')} 天
- 语言: {record.get('language')}
- 可视化: {record.get('visuals')}
- 深度: {record.get('depth')}
- SOP 层级: {record.get('sop_layer', 'standard')}

## 多智能体链路
| 顺序 | 智能体 | 工具 | 状态 |
|---:|---|---|---|
{flow_lines}

## 决策
- 风险结论: {localized_decision(record.get('risk_decision'), lang)}
- 品牌审计通过: {audit.get('passed')}
- 品牌审计违规数: {audit.get('violation_count')}
- 产物隔离审计通过: {artifact_audit.get('passed')}
- 产物隔离违规数: {artifact_audit.get('violation_count')}

## 输出
{output_lines}
"""
        return redact_public_text(content, brand_config)
    content = f"""---
type: agent_run
run_id: {record.get('run_id')}
public_brand: {record.get('public_brand')}
status: completed
---

# {record.get('public_brand')} Matrix Agent Run

## Request
- Goal: {record.get('request', {}).get('goal')}
- Platforms: {", ".join(record.get('request', {}).get('platforms', []))}
- Offer: {record.get('request', {}).get('offer')}
- Duration: {record.get('request', {}).get('duration_days')} days
- SOP layer: {record.get('sop_layer', 'standard')}

## Multi-Agent Flow
| Order | Agent | Tool | Status |
|---:|---|---|---|
{flow_lines}

## Decision
- Risk decision: {record.get('risk_decision')}
- Brand audit passed: {audit.get('passed')}
- Brand audit violation count: {audit.get('violation_count')}
- Artifact audit passed: {artifact_audit.get('passed')}
- Artifact audit violation count: {artifact_audit.get('violation_count')}

## Outputs
{output_lines}
"""
    return redact_public_text(content, brand_config)


def run_run_matrix(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    lang = normalize_lang(getattr(args, "lang", "zh-CN"))
    visuals = getattr(args, "visuals", "mermaid")
    depth = normalize_depth(getattr(args, "depth", "brief"))
    sop_layer = normalize_sop_layer(getattr(args, "sop_layer", "standard"))

    brief_args = argparse.Namespace(**vars(args))
    if not brief_args.task_id:
        brief_args.task_id = slugify(f"{args.platform}-{args.goal}", fallback="aivamax-task", max_len=32)
    brief = build_task_brief(brief_args, brand_config)
    records = load_source_records(data_dir, getattr(args, "corpus", "web"))
    evidence_pack = build_evidence_pack(brief, records, args.top, brand_config, public_mode=True)
    if not evidence_pack.get("items"):
        print("No evidence items found. Try broader keywords or resync the source adapter.", file=sys.stderr)
        return 1

    base_sop_text = render_sop_markdown(brief, evidence_pack, brand_config, lang=lang, visuals=visuals, data_dir=data_dir, depth=depth)
    dual_pack: dict[str, str] | None = None
    if sop_layer == "dual":
        dual_pack = build_dual_sop_pack(brief, evidence_pack, brand_config, lang=lang, visuals=visuals, data_dir=data_dir, depth=depth)
        sop_text = dual_pack["PublicCourseSOP.md"]
    elif sop_layer == "public":
        sop_text = render_public_course_sop(brief, evidence_pack, brand_config, lang=lang, visuals=visuals, data_dir=data_dir, depth=depth)
    elif sop_layer == "internal":
        sop_text = render_internal_ops_sop(brief, evidence_pack, brand_config, lang=lang)
    else:
        sop_text = base_sop_text
    risk_text = render_risk_audit_markdown(brief, evidence_pack, sop_text, brand_config, lang=lang)
    risk_decision = extract_risk_decision(risk_text)

    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M%S")
    task_slug = slugify(str(brief["task_id"]), fallback="task", max_len=32)
    run_id_base = args.run_id or f"RUN-{stamp}-{task_slug}"
    run_dir = data_dir / "matrix" / "agent_runs" / run_id_base
    if run_dir.exists() and not args.force:
        if args.run_id:
            print(f"Run folder already exists: {run_dir}. Use --force or choose another --run-id.", file=sys.stderr)
            return 1
        run_dir = unique_directory_path(run_dir)
    run_id = run_dir.name

    project_id = args.project_id or f"{dt.datetime.now().date().isoformat()}_{task_slug}"
    project_dir = matrix_root / "50_Projects" / project_id
    if project_dir.exists() and not args.force:
        project_dir = unique_directory_path(project_dir)

    course_name = args.course_name or "AIvaMax账号安全与获客SOP课"
    module_id = slugify(args.module_id or task_slug, fallback="course-module", max_len=32)
    course_dir = matrix_root / "70_Courses" / course_name / module_id
    if course_dir.exists() and not args.force:
        course_dir = unique_directory_path(course_dir)

    project_files = build_project_package_files(
        brief,
        evidence_pack,
        sop_text,
        risk_text,
        brand_config,
        run_id,
        lang=lang,
        depth=depth,
        sop_layer=sop_layer,
        dual_sop_pack=dual_pack,
        project_id=project_dir.name,
    )
    course_sop_source = project_files["public/PublicCourseSOP.md"] if sop_layer == "dual" else project_files["03_14-Day-SOP.md"]
    if sop_layer == "internal":
        course_sop_source = render_public_course_sop(brief, evidence_pack, brand_config, lang=lang, visuals=visuals, data_dir=data_dir, depth=depth)
    course_files = build_course_module_files_from_texts(
        project_name=project_dir.name,
        brief=project_files["00_Brief.md"],
        evidence=project_files["01_Evidence-Pack.md"],
        risk=project_files["02_Risk-Review.md"],
        sop=course_sop_source,
        module_id=course_dir.name,
        brand_config=brand_config,
        lang=lang,
        visuals=visuals,
        depth=depth,
    )
    visual_playbook_dir = matrix_root / "40_Playbooks" / "Visuals"
    visual_files: dict[str, str] = {}
    if visuals in {"mermaid", "all"}:
        visual_files[f"{task_slug}-visuals.md"] = f"""---
type: visual_playbook
public_brand: {public_brand(brand_config)}
task_id: {brief.get('task_id')}
---

# {public_brand(brand_config)} {bilingual_label('图文流程包', 'Visual Workflow Pack', lang)}

{render_visual_sections(brief, lang, "mermaid")}
"""
    platform = platform_profile((brief.get("platforms") or ["instagram"])[0])
    platform_playbook_dir = matrix_root / "40_Playbooks" / "Platforms" / platform["folder"]
    boundary_dir = matrix_root / "20_Risks" / "Platform_Boundaries"
    platform_files = {"Platform-Playbook.md": render_platform_playbook(platform["display"], brand_config, lang=lang)}
    boundary_files = {f"{platform['folder']}-BoundaryBrief.md": render_boundary_brief(platform["display"], brand_config, lang=lang)}
    run_files = {
        "00_TaskBrief.json": json.dumps(brief, ensure_ascii=False, indent=2),
        "01_EvidencePack.json": json.dumps(evidence_pack, ensure_ascii=False, indent=2),
        "01_EvidencePack.md": render_evidence_pack_markdown(evidence_pack),
        "02_SOP.md": sop_text,
        "03_RiskAudit.md": risk_text,
    }
    if dual_pack:
        run_files.update({
            "02_PublicCourseSOP.md": dual_pack["PublicCourseSOP.md"],
            "02_InternalOpsSOP.md": dual_pack["InternalOpsSOP.md"],
            "02_BoundaryBrief.md": dual_pack["BoundaryBrief.md"],
            "02_ExecutionLog.md": dual_pack["ExecutionLog.md"],
        })

    output_paths = {
        "run_dir": public_output_path(run_dir),
        "task_brief": public_output_path(run_dir / "00_TaskBrief.json"),
        "evidence_pack": public_output_path(run_dir / "01_EvidencePack.json"),
        "sop": public_output_path(run_dir / "02_SOP.md"),
        "risk_audit": public_output_path(run_dir / "03_RiskAudit.md"),
        "project_dir": public_output_path(project_dir),
        "course_dir": public_output_path(course_dir),
    }
    if depth in {"deep", "course"}:
        if sop_layer == "dual":
            output_paths["execution_checklist"] = public_output_path(project_dir / "public" / "ExecutionChecklist.md")
            output_paths["review_rubric"] = public_output_path(project_dir / "public" / "ReviewRubric.md")
        else:
            output_paths["execution_checklist"] = public_output_path(project_dir / "06_Execution-Checklist.md")
            output_paths["review_rubric"] = public_output_path(project_dir / "07_Review-Rubric.md")
    if sop_layer == "dual":
        output_paths["public_course_sop"] = public_output_path(project_dir / "public" / "PublicCourseSOP.md")
        output_paths["internal_ops_sop"] = public_output_path(project_dir / "internal" / "InternalOpsSOP.md")
        output_paths["boundary_brief"] = public_output_path(project_dir / "public" / "BoundaryBrief.md")
        output_paths["execution_log"] = public_output_path(project_dir / "internal" / "ExecutionLog.md")
        output_paths["experiment_notes"] = public_output_path(project_dir / "internal" / "ExperimentNotes.md")
        output_paths["artifact_manifest"] = public_output_path(project_dir / "manifest.json")
    if visual_files:
        output_paths["visual_playbook"] = public_output_path(visual_playbook_dir / next(iter(visual_files)))
    output_paths["platform_playbook"] = public_output_path(platform_playbook_dir / "Platform-Playbook.md")
    output_paths["platform_boundary_brief"] = public_output_path(boundary_dir / f"{platform['folder']}-BoundaryBrief.md")

    if args.dry_run:
        print(json.dumps({
            "run_id": run_id,
            "risk_decision": risk_decision,
            "language": lang,
            "visuals": visuals,
            "depth": depth,
            "sop_layer": sop_layer,
            "outputs": output_paths,
            "agent_flow": matrix_agent_flow(),
        }, ensure_ascii=False, indent=2))
        return 0

    write_named_files(run_dir, run_files, brand_config, force=args.force)
    write_named_files(project_dir, project_files, brand_config, force=args.force)
    write_named_files(course_dir, course_files, brand_config, force=args.force)
    write_named_files(platform_playbook_dir, platform_files, brand_config, force=True)
    write_named_files(boundary_dir, boundary_files, brand_config, force=True)
    if visual_files:
        write_named_files(visual_playbook_dir, visual_files, brand_config, force=True)

    audit_paths = [run_dir, project_dir, course_dir, platform_playbook_dir / "Platform-Playbook.md", boundary_dir / f"{platform['folder']}-BoundaryBrief.md"]
    if visual_files:
        audit_paths.append(visual_playbook_dir / next(iter(visual_files)))
    violations = scan_many_brand_violations(audit_paths, brand_config)
    artifact_violations = scan_artifact_violations(matrix_root)
    quality_result = None
    if depth == "course":
        quality_result = scan_course_quality(
            project_dir,
            course_dir,
            forbidden_terms=brand_config.get("forbidden_public_terms", []),
        )
    record = build_agent_run_record(
        run_id=run_id,
        request_goal=args.goal,
        brief=brief,
        evidence_pack=evidence_pack,
        risk_decision=risk_decision,
        outputs=output_paths,
        checked_paths=audit_paths,
        violation_count=len(violations),
        brand_config=brand_config,
        lang=lang,
        visuals=visuals,
        depth=depth,
        sop_layer=sop_layer,
        artifact_violation_count=len(artifact_violations),
    )
    record_files = {
        "04_AgentRun.json": json.dumps(record, ensure_ascii=False, indent=2),
        "04_AgentRun.md": render_agent_run_markdown(record, brand_config, lang=lang),
    }
    write_named_files(run_dir, record_files, brand_config, force=True)
    review_dir = matrix_root / "60_Reviews" / "Agent Runs"
    write_named_files(review_dir, {f"{run_id}.md": record_files["04_AgentRun.md"]}, brand_config, force=True)
    violations.extend(scan_many_brand_violations([run_dir / "04_AgentRun.json", run_dir / "04_AgentRun.md", review_dir / f"{run_id}.md"], brand_config))

    if args.json:
        print(json.dumps({
            "run_id": run_id,
            "risk_decision": risk_decision,
            "sop_layer": sop_layer,
            "brand_audit_passed": not violations,
            "violation_count": len(violations),
            "artifact_audit_passed": not artifact_violations,
            "artifact_violation_count": len(artifact_violations),
            "quality_audit_passed": None if quality_result is None else quality_result.get("passed"),
            "quality_score": None if quality_result is None else quality_result.get("score"),
            "outputs": output_paths,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"AIvaMax matrix run: {run_id}")
        print(f"Risk decision: {risk_decision}")
        print(f"Brand audit: {'passed' if not violations else 'failed'}")
        print(f"Artifact audit: {'passed' if not artifact_violations else 'failed'}")
        if quality_result is not None:
            print(f"Quality audit: {'passed' if quality_result.get('passed') else 'failed'} ({quality_result.get('score')})")
        for name, path in output_paths.items():
            print(f"{name}: {path}")
    quality_failed = quality_result is not None and not quality_result.get("passed")
    return 1 if violations or artifact_violations or quality_failed else 0


def find_agent_run_records(data_dir: Path) -> list[Path]:
    root = data_dir / "matrix" / "agent_runs"
    if not root.exists():
        return []
    records = list(root.glob("RUN-*/04_AgentRun.json"))
    records.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return records


def run_agent_run(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    records = find_agent_run_records(data_dir)
    if args.id:
        matches = [path for path in records if path.parent.name == args.id or args.id in path.parent.name]
        if not matches:
            print(f"Agent run not found: {args.id}", file=sys.stderr)
            return 1
        record_path = matches[0]
        if args.json:
            print(record_path.read_text(encoding="utf-8"))
        else:
            md_path = record_path.with_suffix(".md")
            print(md_path.read_text(encoding="utf-8") if md_path.exists() else record_path.read_text(encoding="utf-8"))
        return 0
    selected = records[: args.limit]
    if args.json:
        data = [json.loads(path.read_text(encoding="utf-8")) for path in selected]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if not selected:
            print("No AIvaMax matrix agent runs found.")
            return 0
        for path in selected:
            record = json.loads(path.read_text(encoding="utf-8"))
            print(f"{record.get('run_id')} | risk={record.get('risk_decision')} | audit={record.get('brand_audit', {}).get('passed')}")
    return 0


def ensure_media_dirs(data_dir: Path) -> Path:
    root = data_dir / "media"
    (root / "inbox").mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(parents=True, exist_ok=True)
    index = root / "media_index.json"
    if not index.exists():
        index.write_text(json.dumps({"items": []}, ensure_ascii=False, indent=2), encoding="utf-8")
    return root


def load_media_index(data_dir: Path) -> dict:
    root = ensure_media_dirs(data_dir)
    index = root / "media_index.json"
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"items": []}
    if "items" not in data or not isinstance(data["items"], list):
        data["items"] = []
    return data


def save_media_index(data_dir: Path, data: dict) -> None:
    root = ensure_media_dirs(data_dir)
    (root / "media_index.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def unique_file_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for idx in range(2, 1000):
        candidate = path.with_name(f"{stem}-{idx:02d}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not create a unique file path for {path}")


def build_media_entry(
    src: Path,
    asset_path: str,
    module: str,
    step: str,
    platform: str,
    caption: str,
    alt: str,
    audit_status: str,
    brand_config: dict,
) -> dict:
    safe_caption = redact_public_text(caption or src.stem, brand_config)
    safe_alt = redact_public_text(alt or safe_caption, brand_config)
    media_id = f"MEDIA-{sha1_text(asset_path)[:12].upper()}"
    return {
        "media_id": media_id,
        "asset_path": asset_path.replace("\\", "/"),
        "module": slugify(module or "general", fallback="general"),
        "step": slugify(step or "general", fallback="general"),
        "platform": slugify(platform or "general", fallback="general"),
        "caption": safe_caption,
        "alt": safe_alt,
        "audit_status": audit_status or "pending",
        "created_at": now_iso(),
        "original_name": redact_public_text(src.name, brand_config),
    }


def matching_media_entries(items: list[dict], brief: dict, approved_only: bool = True) -> list[dict]:
    platforms = {slugify(str(item), fallback="platform") for item in brief.get("platforms", [])}
    scenario = slugify(str(brief.get("scenario", "")), fallback="")
    template = slugify(str(brief.get("template", "")), fallback="")
    matches: list[dict] = []
    for item in items:
        if approved_only and item.get("audit_status") != "approved":
            continue
        item_platform = slugify(str(item.get("platform", "")), fallback="")
        item_module = slugify(str(item.get("module", "")), fallback="")
        if item_platform and item_platform in platforms:
            matches.append(item)
        elif item_module and (item_module in scenario or item_module in template):
            matches.append(item)
    return matches


def scan_media_metadata_violations(items: list[dict], brand_config: dict, index_path: str = "<media_index>") -> list[dict]:
    terms = brand_config.get("forbidden_public_terms", [])
    violations: list[dict] = []
    for item in items:
        for key in ["media_id", "asset_path", "module", "step", "platform", "caption", "alt", "original_name"]:
            value = str(item.get(key, ""))
            for term in terms:
                if re.search(re.escape(term), value, flags=re.I):
                    violations.append({"path": index_path, "term": term, "line": 0, "text": f"{item.get('media_id')} {key}: {value[:180]}"})
        if item.get("audit_status") != "approved":
            violations.append({
                "path": index_path,
                "term": "audit_status",
                "line": 0,
                "text": f"{item.get('media_id')} is {item.get('audit_status', 'pending')}",
            })
    return violations


def run_media_import(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    root = ensure_media_dirs(data_dir)
    src = resolve_existing_cli_path(args.path)
    if not src.exists() or not src.is_file():
        print(f"Media file not found: {src}", file=sys.stderr)
        return 1
    safe_stem = slugify(redact_public_text(src.stem, brand_config), fallback="media", max_len=64)
    dst = unique_file_path(root / "assets" / f"{safe_stem}{src.suffix.lower()}")
    if not args.dry_run:
        shutil.copyfile(src, dst)
    asset_path = public_output_path(dst)
    entry = build_media_entry(
        src=src,
        asset_path=asset_path,
        module=args.module,
        step=args.step,
        platform=args.platform,
        caption=args.caption,
        alt=args.alt,
        audit_status=args.audit_status,
        brand_config=brand_config,
    )
    if not args.dry_run:
        data = load_media_index(data_dir)
        data["items"].append(entry)
        save_media_index(data_dir, data)
    if args.json:
        print(json.dumps(entry, ensure_ascii=False, indent=2))
    else:
        action = "Would import" if args.dry_run else "Imported"
        print(f"{action}: {entry['asset_path']} ({entry['audit_status']})")
    return 0


def run_media_list(args: argparse.Namespace) -> int:
    data = load_media_index(Path(args.data_dir))
    items = data.get("items", [])
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        if not items:
            print("No media assets found.")
            return 0
        for item in items:
            print(f"{item.get('media_id')} | {item.get('audit_status')} | {item.get('platform')} | {item.get('module')} | {item.get('caption')}")
    return 0


def scan_media_violations(path: Path, brand_config: dict, data_dir: Path | None = None) -> list[dict]:
    terms = brand_config.get("forbidden_public_terms", [])
    violations: list[dict] = []
    if not path.exists():
        return [{"path": str(path), "term": "<missing path>", "line": 0, "text": "Path does not exist"}]
    files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
    for file_path in files:
        path_text = public_output_path(file_path)
        for term in terms:
            if re.search(re.escape(term), file_path.name, flags=re.I) or re.search(re.escape(term), path_text, flags=re.I):
                violations.append({"path": path_text, "term": term, "line": 0, "text": "Forbidden term in media filename/path"})
        if file_path.suffix.lower() in {".md", ".json", ".txt"}:
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception as exc:  # noqa: BLE001
                violations.append({"path": path_text, "term": "<read error>", "line": 0, "text": str(exc)})
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                for term in terms:
                    if re.search(re.escape(term), line, flags=re.I):
                        violations.append({"path": path_text, "term": term, "line": line_no, "text": line.strip()[:240]})
    index_path = (data_dir or DEFAULT_DATA_DIR) / "media" / "media_index.json"
    if index_path.exists():
        data = json.loads(index_path.read_text(encoding="utf-8"))
        violations.extend(scan_media_metadata_violations(data.get("items", []), brand_config, str(index_path)))
    return violations


def run_media_audit(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    default_root = ensure_media_dirs(data_dir)
    root = Path(args.path) if args.path else default_root
    if not root.is_absolute():
        root = Path.cwd() / root
        if not root.exists():
            root = default_root
    violations = scan_media_violations(root, brand_config, data_dir=data_dir)
    if args.json:
        print(json.dumps({"passed": not violations, "violations": violations}, ensure_ascii=False, indent=2))
    elif violations:
        print("Media audit failed:")
        for item in violations[:50]:
            print(f"- {item['path']}:{item['line']} [{item['term']}] {item['text']}")
        if len(violations) > 50:
            print(f"... {len(violations) - 50} more")
    else:
        print("Media audit passed.")
    return 1 if violations else 0


def run_media_plan(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    platform_keys = platform_keys_for_request(args.platform)
    out_root = Path(args.out) if args.out else matrix_root / "40_Playbooks" / "Media_Plans"
    items = []
    for key in platform_keys:
        profile = platform_profile(key)
        content = redact_public_text(render_media_plan_markdown(brand=public_brand(brand_config), platform=profile), brand_config)
        target = out_root / f"{profile['folder']}-Media-Plan.md"
        items.append({"platform": profile["display"], "path": public_output_path(target), "markdown": content})
        if not args.json and not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    if args.json:
        write_json_or_print({"public_brand": public_brand(brand_config), "items": items}, args.out if args.out and args.out.endswith(".json") else None, dry_run=args.dry_run)
    elif args.dry_run:
        print("\n".join(item["path"] for item in items))
    else:
        print(f"Wrote media plans: {len(items)}")
    return 0


def run_case_plan(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    platform_keys = platform_keys_for_request(args.platform)
    out_root = Path(args.out) if args.out else matrix_root / "40_Playbooks" / "Case_Plans"
    items = []
    for key in platform_keys:
        profile = platform_profile(key)
        content = redact_public_text(render_case_plan_markdown(brand=public_brand(brand_config), platform=profile), brand_config)
        target = out_root / f"{profile['folder']}-Case-Plan.md"
        items.append({"platform": profile["display"], "path": public_output_path(target), "markdown": content})
        if not args.json and not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    if args.json:
        write_json_or_print({"public_brand": public_brand(brand_config), "items": items}, args.out if args.out and args.out.endswith(".json") else None, dry_run=args.dry_run)
    elif args.dry_run:
        print("\n".join(item["path"] for item in items))
    else:
        print(f"Wrote case plans: {len(items)}")
    return 0


def run_case_audit(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    path = resolve_existing_cli_path(args.path) if args.path else matrix_root / "40_Playbooks" / "Case_Plans"
    result = scan_case_plan(path, forbidden_terms=brand_config.get("forbidden_public_terms", []))
    brand_violations = scan_brand_violations(path, brand_config) if path.exists() else []
    result["brand_audit"] = {"passed": not brand_violations, "violation_count": len(brand_violations)}
    result["passed"] = bool(result.get("passed")) and not brand_violations
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Case audit: {'passed' if result['passed'] else 'failed'}")
        print(f"Case violations: {len(result.get('violations', []))}")
        print(f"Case warnings: {len(result.get('warnings', []))}")
        print(f"Brand violations: {len(brand_violations)}")
        for item in result.get("violations", [])[:20]:
            print(f"- {item['path']} [{item['term']}] {item['text']}")
    return 0 if result["passed"] else 1


def render_visual_card(card_type: str, lang: str | None, brand_config: dict) -> str:
    brand = public_brand(brand_config)
    card = (card_type or "agent-flow").lower()
    title_map = {
        "risk-map": bilingual_label("风险审核卡", "Risk Map Card", lang),
        "14-day-plan": bilingual_label("14 天执行节奏卡", "14-Day Plan Card", lang),
        "agent-flow": bilingual_label("多智能体流程卡", "Agent Flow Card", lang),
        "content-matrix": bilingual_label("内容矩阵卡", "Content Matrix Card", lang),
        "account-safety": bilingual_label("账号安全检查卡", "Account Safety Card", lang),
    }
    sample_brief = {
        "platforms": ["instagram"],
        "scenario": "content_matrix_reels" if card == "content-matrix" else "account_safety_comment_leadgen",
        "template": "instagram-reels-content-matrix-14d" if card == "content-matrix" else "instagram-comment-leadgen-14d",
    }
    if card == "risk-map":
        diagram = mermaid_risk_map(lang)
    elif card == "14-day-plan":
        diagram = mermaid_timeline(sample_brief, lang)
    elif card == "content-matrix":
        diagram = mermaid_structure_map(sample_brief, lang)
    elif card == "account-safety":
        diagram = mermaid_structure_map(sample_brief, lang)
    else:
        diagram = mermaid_agent_flow(lang)
    title = title_map.get(card, title_map["agent-flow"])
    content = f"""---
type: visual_card
public_brand: {brand}
card_type: {card}
---

# {brand} {title}

<div class="aivamax-card">
<strong>{brand}</strong><br/>
{title}
</div>

{diagram}
"""
    return redact_public_text(content, brand_config)


def run_visual_card(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    lang = normalize_lang(args.lang)
    content = render_visual_card(args.type, lang, brand_config)
    out = Path(args.out) if args.out else matrix_root / "40_Playbooks" / "Cards" / f"{slugify(args.type, 'card')}-{lang}.md"
    if args.dry_run:
        print(content)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"Wrote visual card: {out}")
    return 0


def scan_brand_violations(path: Path, brand_config: dict) -> list[dict]:
    terms = brand_config.get("forbidden_public_terms", [])
    violations: list[dict] = []
    if not path.exists():
        return [{"path": str(path), "term": "<missing path>", "line": 0, "text": "Path does not exist"}]
    files = [path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()]
    for file_path in files:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            violations.append({"path": str(file_path), "term": "<read error>", "line": 0, "text": str(exc)})
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            for term in terms:
                if re.search(re.escape(term), line, flags=re.I):
                    violations.append({
                        "path": str(file_path),
                        "term": term,
                        "line": line_no,
                        "text": line.strip()[:240],
                    })
    return violations


def run_brand_audit(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    violations = scan_brand_violations(Path(args.path), brand_config)
    if args.json:
        print(json.dumps({"passed": not violations, "violations": violations}, ensure_ascii=False, indent=2))
    elif violations:
        print("Brand audit failed:")
        for item in violations[:50]:
            print(f"- {item['path']}:{item['line']} [{item['term']}] {item['text']}")
        if len(violations) > 50:
            print(f"... {len(violations) - 50} more")
    else:
        print("Brand audit passed.")
    return 1 if violations else 0


def run_artifact_audit(args: argparse.Namespace) -> int:
    root = Path(args.path) if args.path else Path(args.data_dir) / "obsidian" / "AIvaMax_Matrix"
    violations = scan_artifact_violations(root)
    if args.json:
        print(json.dumps({"passed": not violations, "violations": violations}, ensure_ascii=False, indent=2))
    elif violations:
        print("Artifact audit failed:")
        for item in violations[:50]:
            print(f"- {item['path']}:{item['line']} [{item['term']}] {item['text']}")
        if len(violations) > 50:
            print(f"... {len(violations) - 50} more")
    else:
        print("Artifact audit passed.")
    return 1 if violations else 0


def _latest_project_dir(matrix_root: Path) -> Path | None:
    root = matrix_root / "50_Projects"
    if not root.exists():
        return None
    candidates = [path for path in root.iterdir() if path.is_dir()]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def _latest_course_module_dir(matrix_root: Path) -> Path | None:
    root = matrix_root / "70_Courses"
    if not root.exists():
        return None
    candidates = [path.parent for path in root.rglob("00_Module-Overview.md") if path.is_file()]
    return max(candidates, key=lambda path: path.stat().st_mtime, default=None)


def _course_module_dir(matrix_root: Path, course_name: str, module_id: str) -> Path:
    return matrix_root / "70_Courses" / course_name / module_id


def _read_existing_files(root: Path, names: list[str]) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in names:
        path = root / name
        if path.exists() and path.is_file():
            files[name] = path.read_text(encoding="utf-8", errors="ignore")
    return files


def run_course_release(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    project_dir = resolve_existing_cli_path(args.project)
    course_dir = resolve_existing_cli_path(args.course)
    if not project_dir.exists() or not course_dir.exists():
        print("Project or course folder not found.", file=sys.stderr)
        return 1
    course_name = args.course_name or course_dir.parent.name
    module_id = course_dir.name
    case_plan_path = matrix_root / "40_Playbooks" / "Case_Plans" / "Instagram-Case-Plan.md"
    media_plan_path = matrix_root / "40_Playbooks" / "Media_Plans" / "Instagram-Media-Plan.md"
    basic_quality = scan_course_quality(
        project_dir,
        course_dir,
        forbidden_terms=brand_config.get("forbidden_public_terms", []),
    )
    release_files = render_course_release_files(
        brand=public_brand(brand_config),
        course_name=course_name,
        module_id=module_id,
        project_path=public_output_path(project_dir),
        course_path=public_output_path(course_dir),
        quality_result=basic_quality,
        media_plan_path=public_output_path(media_plan_path),
        case_plan_path=public_output_path(case_plan_path),
    )
    release_files = {name: redact_public_text(content, brand_config) for name, content in release_files.items()}
    course_root = course_dir.parent
    if args.dry_run:
        targets = [public_output_path(course_root / name) for name in release_files]
        if args.json:
            print(json.dumps({"course_root": public_output_path(course_root), "would_write": targets, "dry_run": True}, ensure_ascii=False, indent=2))
        else:
            print("\n".join(targets))
        return 0
    write_named_files(course_root, release_files, brand_config, force=args.force)
    strict_quality = scan_course_quality(
        project_dir,
        course_dir,
        forbidden_terms=brand_config.get("forbidden_public_terms", []),
        strict="course-release",
        require_public_export=False,
    )
    if args.json:
        print(json.dumps({
            "course_root": public_output_path(course_root),
            "release_files": [public_output_path(course_root / name) for name in release_files],
            "quality": strict_quality,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Course release files: {course_root}")
        print(f"Strict quality audit: {'passed' if strict_quality.get('passed') else 'failed'} ({strict_quality.get('score')})")
    return 0 if strict_quality.get("passed") else 1


def run_dashboard_refresh(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    project_dir = resolve_existing_cli_path(args.project) if args.project else _latest_project_dir(matrix_root)
    course_dir = resolve_existing_cli_path(args.course) if args.course else _latest_course_module_dir(matrix_root)
    quality_result = None
    if project_dir and course_dir and project_dir.exists() and course_dir.exists():
        quality_result = scan_course_quality(
            project_dir,
            course_dir,
            forbidden_terms=brand_config.get("forbidden_public_terms", []),
            strict="course-release",
        )
    course_name = args.course_name or (course_dir.parent.name if course_dir else "AIvaMax账号安全与获客SOP课")
    content = render_course_dashboard(
        brand=public_brand(brand_config),
        course_name=course_name,
        latest_project=public_output_path(project_dir) if project_dir else None,
        latest_course=public_output_path(course_dir) if course_dir else None,
        public_export=public_output_path(public_export_dir_for_course(course_dir)) if course_dir else None,
        quality_result=quality_result,
    )
    content = redact_public_text(content, brand_config)
    out = Path(args.out) if args.out else matrix_root / "00_Dashboards" / "Course Release Dashboard.md"
    if args.dry_run:
        print(content)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.force:
        out = unique_file_path(out)
    out.write_text(content, encoding="utf-8")
    if args.json:
        print(json.dumps({
            "dashboard": public_output_path(out),
            "project": public_output_path(project_dir) if project_dir else None,
            "course": public_output_path(course_dir) if course_dir else None,
            "quality": quality_result,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Dashboard refreshed: {out}")
    return 0


def run_course_export(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    course_dir = resolve_existing_cli_path(args.course_dir) if args.course_dir else _course_module_dir(matrix_root, args.course, args.module)
    if not course_dir.exists():
        print(f"Course module not found: {course_dir}", file=sys.stderr)
        return 1
    course_name = args.course or course_dir.parent.name
    module_id = args.module or course_dir.name
    course_files = _read_existing_files(course_dir, [
        "00_Module-Overview.md",
        "01_Lesson-Plan.md",
        "02_Workbook.md",
        "03_Instructor-Guide.md",
        "04_Assessment.md",
        "05_Case-Lab.md",
    ])
    release_files = _read_existing_files(course_dir.parent, [
        "_Course-Index.md",
        "_Release-Checklist.md",
        "_Instructor-Runbook.md",
        "_Student-Workbook.md",
        "_Case-Library.md",
    ])
    include_html = args.format in {"html", "all"}
    files = render_course_export_files(
        brand=public_brand(brand_config),
        course_name=course_name,
        module_id=module_id,
        course_files=course_files,
        release_files=release_files,
        include_html=include_html,
    )
    files = {name: redact_public_text(content, brand_config) for name, content in files.items()}
    out_dir = Path(args.out) if args.out else public_export_dir_for_course(course_dir)
    if args.dry_run:
        result = {"course_dir": public_output_path(course_dir), "out_dir": public_output_path(out_dir), "would_write": list(files)}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else "\n".join(str(out_dir / name) for name in files))
        return 0
    write_named_files(out_dir, files, brand_config, force=args.force)
    violations = scan_brand_violations(out_dir, brand_config)
    if args.json:
        print(json.dumps({
            "course_dir": public_output_path(course_dir),
            "out_dir": public_output_path(out_dir),
            "files": [public_output_path(out_dir / name) for name in files],
            "brand_audit_passed": not violations,
            "violation_count": len(violations),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Course export: {out_dir}")
        print(f"Brand audit: {'passed' if not violations else 'failed'}")
    return 0 if not violations else 1


def run_release_demo(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    course_dir = resolve_existing_cli_path(args.course_dir) if args.course_dir else _course_module_dir(matrix_root, args.course, args.module)
    if not course_dir.exists():
        print(f"Course module not found: {course_dir}", file=sys.stderr)
        return 1
    course_name = args.course or course_dir.parent.name
    module_id = args.module or course_dir.name
    include_html = args.format in {"html", "all"}
    files = render_release_demo_files(
        brand=public_brand(brand_config),
        course_name=course_name,
        module_id=module_id,
        include_html=include_html,
    )
    files = {name: redact_public_text(content, brand_config) for name, content in files.items()}
    out_dir = Path(args.out) if args.out else public_export_dir_for_course(course_dir)
    if args.dry_run:
        result = {"course_dir": public_output_path(course_dir), "out_dir": public_output_path(out_dir), "would_write": list(files)}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else "\n".join(str(out_dir / name) for name in files))
        return 0
    write_named_files(out_dir, files, brand_config, force=args.force)
    violations = scan_brand_violations(out_dir, brand_config)
    if args.json:
        print(json.dumps({
            "course_dir": public_output_path(course_dir),
            "out_dir": public_output_path(out_dir),
            "files": [public_output_path(out_dir / name) for name in files],
            "brand_audit_passed": not violations,
            "violation_count": len(violations),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Release demo pack: {out_dir}")
        print(f"Brand audit: {'passed' if not violations else 'failed'}")
    return 0 if not violations else 1


def run_sales_pack(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    course_dir = resolve_existing_cli_path(args.course_dir) if args.course_dir else _course_module_dir(matrix_root, args.course, args.module)
    if not course_dir.exists():
        print(f"Course module not found: {course_dir}", file=sys.stderr)
        return 1
    course_name = args.course or course_dir.parent.name
    module_id = args.module or course_dir.name
    export_dir = public_export_dir_for_course(course_dir)
    export_files = _read_existing_files(export_dir, [
        "AIvaMax_Student_Manual.md",
        "AIvaMax_Instructor_Manual.md",
        "AIvaMax_Case_Workbook.md",
        "AIvaMax_Course_Demo.md",
    ])
    include_html = args.format in {"html", "all"}
    files = render_sales_pack_files(
        brand=public_brand(brand_config),
        course_name=course_name,
        module_id=module_id,
        export_files=export_files,
        include_html=include_html,
    )
    files = {name: redact_public_text(content, brand_config) for name, content in files.items()}
    out_dir = Path(args.out) if args.out else export_dir / "sales_pack"
    if args.dry_run:
        result = {"course_dir": public_output_path(course_dir), "out_dir": public_output_path(out_dir), "would_write": list(files)}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else "\n".join(str(out_dir / name) for name in files))
        return 0
    write_named_files(out_dir, files, brand_config, force=args.force)
    violations = scan_brand_violations(out_dir, brand_config)
    if args.json:
        print(json.dumps({
            "course_dir": public_output_path(course_dir),
            "out_dir": public_output_path(out_dir),
            "files": [public_output_path(out_dir / name) for name in files],
            "brand_audit_passed": not violations,
            "violation_count": len(violations),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Sales pack: {out_dir}")
        print(f"Brand audit: {'passed' if not violations else 'failed'}")
    return 0 if not violations else 1


def run_preview_pack(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    course_dir = resolve_existing_cli_path(args.course_dir) if args.course_dir else _course_module_dir(matrix_root, args.course, args.module)
    if not course_dir.exists():
        print(f"Course module not found: {course_dir}", file=sys.stderr)
        return 1
    course_name = args.course or course_dir.parent.name
    module_id = args.module or course_dir.name
    include_html = args.format in {"html", "all"}
    files = render_preview_pack_files(
        brand=public_brand(brand_config),
        course_name=course_name,
        module_id=module_id,
        include_html=include_html,
    )
    files = {name: redact_public_text(content, brand_config) for name, content in files.items()}
    out_dir = Path(args.out) if args.out else public_export_dir_for_course(course_dir) / "preview_pack"
    if args.dry_run:
        result = {"course_dir": public_output_path(course_dir), "out_dir": public_output_path(out_dir), "would_write": list(files)}
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else "\n".join(str(out_dir / name) for name in files))
        return 0
    write_named_files(out_dir, files, brand_config, force=args.force)
    violations = scan_brand_violations(out_dir, brand_config)
    if args.json:
        print(json.dumps({
            "course_dir": public_output_path(course_dir),
            "out_dir": public_output_path(out_dir),
            "files": [public_output_path(out_dir / name) for name in files],
            "brand_audit_passed": not violations,
            "violation_count": len(violations),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"Preview pack: {out_dir}")
        print(f"Brand audit: {'passed' if not violations else 'failed'}")
    return 0 if not violations else 1


def run_quality_audit(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    project_dir = resolve_existing_cli_path(args.project)
    course_dir = resolve_existing_cli_path(args.course)
    result = scan_course_quality(
        project_dir,
        course_dir,
        forbidden_terms=brand_config.get("forbidden_public_terms", []),
        strict=getattr(args, "strict", "basic"),
    )
    brand_violations = scan_many_brand_violations([project_dir, course_dir], brand_config)
    matrix_root = Path(args.data_dir) / "obsidian" / "AIvaMax_Matrix"
    artifact_violations = scan_artifact_violations(matrix_root) if matrix_root.exists() else []
    result["brand_audit"] = {"passed": not brand_violations, "violation_count": len(brand_violations)}
    result["artifact_audit"] = {"passed": not artifact_violations, "violation_count": len(artifact_violations)}
    passed = bool(result.get("passed")) and not brand_violations and not artifact_violations
    result["passed"] = passed
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Quality audit: {'passed' if passed else 'failed'}")
        print(f"Score: {result.get('score')}")
        print(f"Content violations: {len(result.get('violations', []))}")
        print(f"Brand violations: {len(brand_violations)}")
        print(f"Artifact violations: {len(artifact_violations)}")
        for item in result.get("violations", [])[:20]:
            print(f"- {item['path']} [{item['term']}] {item['text']}")
    return 0 if passed else 1


def run_show(args: argparse.Namespace) -> int:
    records = load_records(Path(args.data_dir))
    needle = args.id_or_url.lower()
    matches = [
        r for r in records
        if needle in r.get("id", "").lower()
        or needle in r.get("url", "").lower()
        or needle in r.get("title", "").lower()
    ]
    if not matches:
        print("No matching record.")
        return 1
    record = matches[0]
    print(f"# {record['title']}")
    print(f"URL: {record['url']}")
    print(f"Category: {record['category']}")
    print(f"Note: {Path(args.data_dir) / record['note_path']}")
    print()
    print((record.get("text") or record.get("summary") or "")[: args.chars])
    return 0


def run_stats(args: argparse.Namespace) -> int:
    records = load_records(Path(args.data_dir))
    counts = Counter(r.get("category", "unknown") for r in records)
    print(f"Pages: {len(records)}")
    for category, count in sorted(counts.items()):
        print(f"- {category}: {count}")
    manifest = Path(args.data_dir) / "manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        print(f"Generated: {data.get('generated_at')}")
        print(f"Errors: {len(data.get('errors', []))}")
    return 0


def run_platform_playbook(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    platform_keys = platform_keys_for_request(args.platform)
    if len(platform_keys) > 1:
        items = []
        out_root = Path(args.out) if args.out else matrix_root / "40_Playbooks" / "Platforms"
        for key in platform_keys:
            profile = platform_profile(key)
            content = render_platform_playbook(key, brand_config, getattr(args, "lang", "zh-CN"))
            target = out_root / profile["folder"] / "Platform-Playbook.md"
            items.append({"platform": profile["display"], "folder": profile["folder"], "path": public_output_path(target), "markdown": content})
            if not args.json and not args.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        if args.json:
            write_json_or_print({"public_brand": public_brand(brand_config), "items": items}, args.out if args.out and args.out.endswith(".json") else None, dry_run=args.dry_run)
        elif args.dry_run:
            print("\n".join(item["path"] for item in items))
        else:
            print(f"Wrote platform playbooks: {len(items)}")
        return 0
    profile = platform_profile(platform_keys[0])
    content = render_platform_playbook(platform_keys[0], brand_config, getattr(args, "lang", "zh-CN"))
    if args.json:
        data = {
            "public_brand": public_brand(brand_config),
            "platform": profile["display"],
            "folder": profile["folder"],
            "markdown": content,
        }
        write_json_or_print(data, args.out, dry_run=args.dry_run)
        return 0
    out = Path(args.out) if args.out else matrix_root / "40_Playbooks" / "Platforms" / profile["folder"] / "Platform-Playbook.md"
    write_or_print(content, str(out), dry_run=args.dry_run)
    return 0


def run_boundary_brief(args: argparse.Namespace) -> int:
    brand_config = load_brand_config(Path(args.brand_config))
    data_dir = Path(args.data_dir)
    matrix_root = ensure_aivamax_matrix_dirs(data_dir)
    platform_keys = platform_keys_for_request(args.platform)
    if len(platform_keys) > 1:
        items = []
        out_root = Path(args.out) if args.out else matrix_root / "20_Risks" / "Platform_Boundaries"
        for key in platform_keys:
            profile = platform_profile(key)
            content = render_boundary_brief(key, brand_config, getattr(args, "lang", "zh-CN"))
            target = out_root / f"{profile['folder']}-BoundaryBrief.md"
            items.append({"platform": profile["display"], "path": public_output_path(target), "markdown": content})
            if not args.json and not args.dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
        if args.json:
            write_json_or_print({"public_brand": public_brand(brand_config), "items": items}, args.out if args.out and args.out.endswith(".json") else None, dry_run=args.dry_run)
        elif args.dry_run:
            print("\n".join(item["path"] for item in items))
        else:
            print(f"Wrote boundary briefs: {len(items)}")
        return 0
    profile = platform_profile(platform_keys[0])
    content = render_boundary_brief(platform_keys[0], brand_config, getattr(args, "lang", "zh-CN"))
    if args.json:
        data = {
            "public_brand": public_brand(brand_config),
            "platform": profile["display"],
            "boundary_matrix": BOUNDARY_MATRIX,
            "markdown": content,
        }
        write_json_or_print(data, args.out, dry_run=args.dry_run)
        return 0
    out = Path(args.out) if args.out else matrix_root / "20_Risks" / "Platform_Boundaries" / f"{profile['folder']}-BoundaryBrief.md"
    write_or_print(content, str(out), dry_run=args.dry_run)
    return 0


def run_reindex(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    ensure_dirs(data_dir)
    old_records = load_records(data_dir)
    new_records: list[PageRecord] = []
    errors: list[dict] = []
    for old in old_records:
        raw_path = data_dir / old.get("raw_path", "")
        if not raw_path.exists():
            errors.append({"url": old.get("url"), "error": f"missing raw file: {raw_path}"})
            continue
        try:
            html = raw_path.read_text(encoding="utf-8", errors="ignore")
            record = save_record(data_dir, old["url"], int(old.get("status_code", 200)), html)
            new_records.append(record)
        except Exception as exc:  # noqa: BLE001
            errors.append({"url": old.get("url"), "error": str(exc)})
    write_index(data_dir, new_records, errors)
    print(f"Reindexed: {len(new_records)} pages, {len(errors)} errors")
    return 0 if new_records else 1


def obsidian_filename(record: dict) -> str:
    return f"{slugify(record.get('category', 'page'), max_len=30)}-{slugify(record.get('title', 'page'), max_len=70)}-{record.get('id', '')}.md"


def run_export_obsidian(args: argparse.Namespace) -> int:
    data_dir = Path(args.data_dir)
    records = load_records(data_dir)
    out_dir = Path(args.out or data_dir / "obsidian" / "JarveePro")
    pages_dir = out_dir / "Pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    by_category: dict[str, list[dict]] = {}
    for record in records:
        by_category.setdefault(record.get("category", "unknown"), []).append(record)
        src = data_dir / record["note_path"]
        dst = pages_dir / obsidian_filename(record)
        if src.exists():
            shutil.copyfile(src, dst)

    moc_lines = [
        "---",
        "tags: [jarveepro, moc]",
        "---",
        "",
        "# JarveePro Knowledge Base MOC",
        "",
        "This note is generated by `jarveepro_cli.py export-obsidian`.",
        "",
        "## Quick Commands",
        "",
        "```bash",
        "python jarveepro_cli.py sync",
        "python jarveepro_cli.py search \"instagram follow\" --top 8",
        "python jarveepro_cli.py task \"build an Instagram warm-up workflow\" --top 8",
        "python jarveepro_cli.py teach \"proxies and account safety\" --top 8",
        "```",
        "",
        "## Categories",
        "",
    ]
    for category in sorted(by_category):
        cat_file = f"JarveePro - {category}.md"
        moc_lines.append(f"- [[{cat_file[:-3]}]] ({len(by_category[category])})")
        cat_lines = [
            "---",
            f"tags: [jarveepro, jarveepro/{category}]",
            "---",
            "",
            f"# JarveePro - {category}",
            "",
        ]
        for record in sorted(by_category[category], key=lambda r: r.get("title", "")):
            filename = obsidian_filename(record)
            cat_lines.append(f"- [[Pages/{filename[:-3]}|{record.get('title')}]] - [source]({record.get('url')})")
        (out_dir / cat_file).write_text("\n".join(cat_lines) + "\n", encoding="utf-8")

    moc_lines.extend([
        "",
        "## Suggested Agent Loop",
        "",
        "1. Sync the site.",
        "2. Search or generate a task plan.",
        "3. Review cited source notes.",
        "4. Save the final SOP back into your own project notes.",
        "",
    ])
    (out_dir / "JarveePro Knowledge Base MOC.md").write_text("\n".join(moc_lines), encoding="utf-8")
    print(f"Exported Obsidian notes: {out_dir}")
    return 0


def run_doctor(args: argparse.Namespace) -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Root: {ROOT}")
    print(f"Config exists: {Path(args.config).exists()} ({args.config})")
    print(f"Data dir: {Path(args.data_dir)}")
    try:
        import bs4  # noqa: F401
        print("beautifulsoup4: ok")
    except ImportError:
        print("beautifulsoup4: missing")
    try:
        import requests as _requests  # noqa: F401
        print("requests: ok")
    except ImportError:
        print("requests: missing")
    index = Path(args.data_dir) / "index.jsonl"
    print(f"Index exists: {index.exists()} ({index})")
    return 0


def run_watch(args: argparse.Namespace) -> int:
    print(f"Watching with interval={args.interval}s. Press Ctrl+C to stop.")
    try:
        while True:
            run_sync(args)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped.")
        return 0


def run_console(args: argparse.Namespace) -> int:
    from aivamax_console import serve_console

    try:
        serve_console(
            host=args.host,
            port=args.port,
            data_dir=Path(args.data_dir),
            brand_config_path=Path(args.brand_config),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def run_mcp_server(args: argparse.Namespace) -> int:
    from aivamax_mcp_server import serve_mcp, serve_stdio

    try:
        if args.stdio:
            serve_stdio(
                data_dir=Path(args.data_dir),
                brand_config_path=Path(args.brand_config),
            )
        else:
            serve_mcp(
                host=args.host,
                port=args.port,
                data_dir=Path(args.data_dir),
                brand_config_path=Path(args.brand_config),
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


def run_skill_export(args: argparse.Namespace) -> int:
    from aivamax_services import skill_export

    result = skill_export(
        role=args.role,
        out_dir=args.out,
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        caller_role=args.caller_role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Skill export: {'passed' if result.get('ok') else 'failed'}")
        print(result.get("result", {}).get("path", ""))
    return 0 if result.get("ok") else 1


def run_role_audit(args: argparse.Namespace) -> int:
    from aivamax_services import role_audit

    result = role_audit(
        role=args.role,
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        print(f"Role audit: {'passed' if result.get('ok') else 'failed'}")
        print(f"Role: {payload.get('role')}")
        print(f"Permissions: {', '.join(payload.get('permissions', []))}")
        if payload.get("forbidden_permissions"):
            print(f"Forbidden permissions: {', '.join(payload.get('forbidden_permissions', []))}")
        if payload.get("blocked_term_hits"):
            print(f"Blocked term hits: {', '.join(payload.get('blocked_term_hits', []))}")
    return 0 if result.get("ok") else 1


def run_release_gate(args: argparse.Namespace) -> int:
    from aivamax_services import release_gate

    result = release_gate(
        course=args.course,
        module=args.module,
        project=args.project,
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        print(f"Release gate: {'passed' if result.get('ok') else 'failed'}")
        print(f"Project: {payload.get('project')}")
        print(f"Course: {payload.get('course')}")
        for name, audit in payload.get("audits", {}).items():
            print(f"- {name}: {'passed' if audit.get('passed') else 'failed'}")
    return 0 if result.get("ok") else 1


def run_course_factory_release_status(args: argparse.Namespace) -> int:
    from aivamax_services import course_factory_release_status

    result = course_factory_release_status(
        course=args.course,
        course_dir=args.course_dir,
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        report = payload.get("report", {})
        print(f"Course factory release status: {payload.get('readiness')}")
        print(f"Ready to release: {payload.get('ready_to_release')}")
        print(f"Course: {payload.get('course', {}).get('name')}")
        print(f"Client packs: {payload.get('client_packs', {}).get('deliverable_count')}/{payload.get('client_packs', {}).get('pack_count')} deliverable")
        if report.get("markdown"):
            print(f"Report: {report['markdown'].get('path')}")
    return 0 if result.get("ok") else 1


def run_final_release_bundle(args: argparse.Namespace) -> int:
    from aivamax_services import final_release_bundle

    result = final_release_bundle(
        {
            "course": args.course,
            "course_dir": args.course_dir,
            "require_ready": args.require_ready,
        },
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        files = payload.get("files", {})
        print(f"Final release bundle: {'ready' if result.get('ok') else 'failed'}")
        print(f"Ready to release: {payload.get('ready_to_release')}")
        print(f"Included files: {payload.get('included_file_count')}")
        if files.get("archive"):
            print(f"Archive: {files['archive'].get('path')}")
        if files.get("checklist"):
            print(f"Checklist: {files['checklist'].get('path')}")
    return 0 if result.get("ok") else 1


def run_release_signoff_record(args: argparse.Namespace) -> int:
    from aivamax_services import release_signoff_record

    result = release_signoff_record(
        {
            "decision": args.decision,
            "signer": args.signer,
            "version": args.version,
            "notes": args.notes,
            "require_ready": args.require_ready,
        },
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        bundle = payload.get("bundle", {})
        record = payload.get("record", {})
        print(f"Release record: {payload.get('decision')}")
        print(f"Release ID: {payload.get('release_id')}")
        print(f"Bundle SHA256: {bundle.get('sha256')}")
        if record.get("markdown"):
            print(f"Record: {record['markdown'].get('path')}")
    return 0 if result.get("ok") else 1


def run_material_review(args: argparse.Namespace) -> int:
    from aivamax_services import material_review

    result = material_review(
        path=args.path,
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        print(f"Material review: {payload.get('review_status')}")
        print(f"Media: {'passed' if payload.get('media', {}).get('passed') else 'review'}")
        print(f"Case: {'passed' if payload.get('case', {}).get('passed') else 'review'}")
    return 0 if result.get("ok") else 1


def run_runtime_status(args: argparse.Namespace) -> int:
    from aivamax_services import runtime_status

    result = runtime_status(
        limit=args.limit,
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        print(f"Runtime: {payload.get('runtime_status')} | runs={payload.get('run_count')}")
        latest = payload.get("latest_run") or {}
        if latest:
            print(f"Latest: {latest.get('run_id')} | steps={latest.get('completed_steps')}/{latest.get('total_steps')} | risk={latest.get('risk_decision')}")
        for action in payload.get("next_actions", [])[:5]:
            print(f"- P{action.get('priority')} {action.get('title')}: {action.get('command')}")
    return 0 if result.get("ok") else 1


def run_mcp_config_export(args: argparse.Namespace) -> int:
    from aivamax_services import mcp_config_export

    result = mcp_config_export(
        host=args.host,
        out_dir=args.out,
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        print(f"MCP config export: {payload.get('config_root')}")
        for item in payload.get("files", []):
            print(f"- {item.get('host')}: {item.get('path')}")
    return 0 if result.get("ok") else 1


def run_host_smoke_test(args: argparse.Namespace) -> int:
    from aivamax_services import host_smoke_test

    result = host_smoke_test(
        host=args.host,
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        checks = payload.get("checks", {})
        print(f"Host smoke test: {'passed' if result.get('ok') else 'failed'}")
        print(f"Transport: {payload.get('transport')} | tools={checks.get('tool_count')} | responses={checks.get('actual_responses')}/{checks.get('expected_responses')}")
    return 0 if result.get("ok") else 1


def run_host_integration_status(args: argparse.Namespace) -> int:
    from aivamax_services import host_integration_status

    result = host_integration_status(
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        payload = result.get("result", {})
        print(f"Host integration root: {payload.get('config_root')}")
        for item in payload.get("configs", []):
            print(f"- {item.get('host')}: {'ready' if item.get('exists') else 'missing'} | {item.get('path')}")
    return 0 if result.get("ok") else 1


def run_student_coach_preview(args: argparse.Namespace) -> int:
    from aivamax_services import student_coach_preview

    result = student_coach_preview(
        question=args.question,
        course=args.course,
        module=args.module,
        data_dir=Path(args.data_dir),
        brand_config_path=Path(args.brand_config),
        role=args.role,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("result", {}).get("markdown", ""))
    return 0 if result.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aivamax",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
            AIvaMax Matrix CLI with private source adapters.

            Typical flow:
              python jarveepro_cli.py sync-source jarveepro --reuse-raw
              python jarveepro_cli.py brief --template instagram-comment-leadgen-14d --platform instagram --accounts 30
              python jarveepro_cli.py evidence --brief data/matrix/briefs/example.json
              python jarveepro_cli.py sop --brief data/matrix/briefs/example.json --evidence data/matrix/evidence/example.json
              python jarveepro_cli.py run-matrix --goal "Instagram 新账号 14 天冷启动和评论区轻获客" --platform instagram --offer "AI 工具课" --accounts 30 --lang zh-CN --visuals mermaid --depth course --sop-layer dual
              python jarveepro_cli.py platform-playbook --platform all --lang zh-CN
              python jarveepro_cli.py boundary-brief --platform all --lang zh-CN
              python jarveepro_cli.py media-plan --platform instagram
              python jarveepro_cli.py case-plan --platform instagram
              python jarveepro_cli.py init-matrix
              python jarveepro_cli.py course --project data/obsidian/AIvaMax_Matrix/50_Projects/example
              python jarveepro_cli.py course-release --project data/obsidian/AIvaMax_Matrix/50_Projects/example --course data/obsidian/AIvaMax_Matrix/70_Courses/example/module
              python jarveepro_cli.py course-export --course "AIvaMax账号安全与获客SOP课" --module instagram-module --format html
              python jarveepro_cli.py release-demo --course "AIvaMax账号安全与获客SOP课" --module instagram-module --format html
              python jarveepro_cli.py sales-pack --course "AIvaMax账号安全与获客SOP课" --module instagram-module --format html
              python jarveepro_cli.py preview-pack --course "AIvaMax账号安全与获客SOP课" --module instagram-module --format html
              python jarveepro_cli.py quality-audit --strict course-release --project data/obsidian/AIvaMax_Matrix/50_Projects/example --course data/obsidian/AIvaMax_Matrix/70_Courses/example/module
              python jarveepro_cli.py dashboard-refresh
              python jarveepro_cli.py console --host 127.0.0.1 --port 8765
              python jarveepro_cli.py visual-card --type risk-map --lang zh-CN
              python jarveepro_cli.py brand-audit --path data/obsidian/AIvaMax_Matrix
              python jarveepro_cli.py artifact-audit --path data/obsidian/AIvaMax_Matrix
            """
        ),
    )
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--brand-config", default=str(DEFAULT_BRAND_CONFIG))

    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Crawl and refresh the local knowledge base.")
    sync.add_argument("--max-pages", type=int, default=300)
    sync.add_argument("--max-depth", type=int, default=5)
    sync.add_argument("--delay", type=float, default=0.4)
    sync.add_argument("--timeout", type=int, default=25)
    sync.add_argument("--reuse-raw", action="store_true", help="Use saved raw HTML for already indexed URLs.")
    sync.add_argument("--export-obsidian", action="store_true", help="Refresh Obsidian export after sync.")
    sync.set_defaults(func=run_sync)

    sync_source = sub.add_parser("sync-source", help="Crawl and refresh a private source adapter.")
    sync_source.add_argument("source", choices=[DEFAULT_SOURCE])
    sync_source.add_argument("--max-pages", type=int, default=300)
    sync_source.add_argument("--max-depth", type=int, default=5)
    sync_source.add_argument("--delay", type=float, default=0.4)
    sync_source.add_argument("--timeout", type=int, default=25)
    sync_source.add_argument("--reuse-raw", action="store_true", help="Use saved raw HTML for already indexed URLs.")
    sync_source.add_argument("--export-obsidian", action="store_true", help="Refresh internal Obsidian source export after sync.")
    sync_source.set_defaults(func=run_sync_source)

    vendor_index = sub.add_parser("index-vendor-source", help="Index JarveePro vendor source documents without touching the web crawl index.")
    vendor_index.add_argument("--source", choices=[DEFAULT_SOURCE], default=DEFAULT_SOURCE)
    vendor_index.add_argument("--path", help="Override the Vendor_Source_Docs folder.")
    vendor_index.add_argument("--json", action="store_true")
    vendor_index.set_defaults(func=run_index_vendor_source)

    watch = sub.add_parser("watch", help="Continuously resync on an interval.")
    watch.add_argument("--max-pages", type=int, default=300)
    watch.add_argument("--max-depth", type=int, default=5)
    watch.add_argument("--delay", type=float, default=0.4)
    watch.add_argument("--timeout", type=int, default=25)
    watch.add_argument("--interval", type=int, default=3600)
    watch.add_argument("--reuse-raw", action="store_true", help="Use saved raw HTML for already indexed URLs.")
    watch.add_argument("--export-obsidian", action="store_true", help="Refresh Obsidian export after every sync.")
    watch.set_defaults(func=run_watch)

    console = sub.add_parser("console", help="Serve the local AIvaMax Agent OS web console.")
    console.add_argument("--host", default="127.0.0.1")
    console.add_argument("--port", type=int, default=8765)
    console.set_defaults(func=run_console)

    mcp_server = sub.add_parser("mcp-server", help="Serve the local AIvaMax MCP-style safe tool server.")
    mcp_server.add_argument("--host", default="127.0.0.1")
    mcp_server.add_argument("--port", type=int, default=8770)
    mcp_server.add_argument("--stdio", action="store_true", help="Serve stdio JSON-RPC MCP tools for agent hosts.")
    mcp_server.set_defaults(func=run_mcp_server)

    skill_export = sub.add_parser("skill-export", help="Export an AIvaMax role Skill package.")
    skill_export.add_argument("--role", required=True, choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    skill_export.add_argument("--caller-role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    skill_export.add_argument("--out")
    skill_export.add_argument("--json", action="store_true")
    skill_export.set_defaults(func=run_skill_export)

    role_audit = sub.add_parser("role-audit", help="Audit an AIvaMax role permission boundary.")
    role_audit.add_argument("--role", required=True, choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    role_audit.add_argument("--json", action="store_true")
    role_audit.set_defaults(func=run_role_audit)

    release_gate = sub.add_parser("release-gate", help="Run the AIvaMax public release gate.")
    release_gate.add_argument("--course")
    release_gate.add_argument("--module")
    release_gate.add_argument("--project")
    release_gate.add_argument("--role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    release_gate.add_argument("--json", action="store_true")
    release_gate.set_defaults(func=run_release_gate)

    course_factory_release_status_parser = sub.add_parser("course-factory-release-status", help="Generate the AIvaMax course-factory release status dashboard report.")
    course_factory_release_status_parser.add_argument("--course")
    course_factory_release_status_parser.add_argument("--course-dir")
    course_factory_release_status_parser.add_argument("--role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    course_factory_release_status_parser.add_argument("--json", action="store_true")
    course_factory_release_status_parser.set_defaults(func=run_course_factory_release_status)

    final_release_bundle_parser = sub.add_parser("final-release-bundle", help="Assemble the final AIvaMax release bundle ZIP, manifest, and signoff checklist.")
    final_release_bundle_parser.add_argument("--course")
    final_release_bundle_parser.add_argument("--course-dir")
    final_release_bundle_parser.add_argument("--role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    final_release_bundle_parser.add_argument("--require-ready", action=argparse.BooleanOptionalAction, default=True)
    final_release_bundle_parser.add_argument("--json", action="store_true")
    final_release_bundle_parser.set_defaults(func=run_final_release_bundle)

    release_signoff_record_parser = sub.add_parser("release-signoff-record", help="Write a release signoff record with bundle hash, decision, signer, and release gates.")
    release_signoff_record_parser.add_argument("--decision", default="pending_review", choices=["pending_review", "approved", "rejected"])
    release_signoff_record_parser.add_argument("--signer", default="owner_admin")
    release_signoff_record_parser.add_argument("--version", default="course-factory-v1")
    release_signoff_record_parser.add_argument("--notes", default="")
    release_signoff_record_parser.add_argument("--role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    release_signoff_record_parser.add_argument("--require-ready", action=argparse.BooleanOptionalAction, default=True)
    release_signoff_record_parser.add_argument("--json", action="store_true")
    release_signoff_record_parser.set_defaults(func=run_release_signoff_record)

    material_review = sub.add_parser("material-review", help="Review AIvaMax media and case material readiness.")
    material_review.add_argument("--path")
    material_review.add_argument("--role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    material_review.add_argument("--json", action="store_true")
    material_review.set_defaults(func=run_material_review)

    runtime_status_parser = sub.add_parser("runtime-status", help="Show AIvaMax Agent Runtime recent runs and next actions.")
    runtime_status_parser.add_argument("--limit", type=int, default=8)
    runtime_status_parser.add_argument("--role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    runtime_status_parser.add_argument("--json", action="store_true")
    runtime_status_parser.set_defaults(func=run_runtime_status)

    mcp_config_export_parser = sub.add_parser("mcp-config-export", help="Export MCP host config templates for external agent hosts.")
    mcp_config_export_parser.add_argument("--host", default="all", choices=["all", "claude-code", "work-buddy", "codex", "generic-agent"])
    mcp_config_export_parser.add_argument("--role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    mcp_config_export_parser.add_argument("--out")
    mcp_config_export_parser.add_argument("--json", action="store_true")
    mcp_config_export_parser.set_defaults(func=run_mcp_config_export)

    host_smoke_test_parser = sub.add_parser("host-smoke-test", help="Run a local stdio MCP smoke test for AIvaMax host integration.")
    host_smoke_test_parser.add_argument("--host", default="stdio", choices=["stdio", "local"])
    host_smoke_test_parser.add_argument("--role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    host_smoke_test_parser.add_argument("--json", action="store_true")
    host_smoke_test_parser.set_defaults(func=run_host_smoke_test)

    host_integration_status_parser = sub.add_parser("host-integration-status", help="Show MCP host config and Skill package readiness.")
    host_integration_status_parser.add_argument("--role", default="owner_admin", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    host_integration_status_parser.add_argument("--json", action="store_true")
    host_integration_status_parser.set_defaults(func=run_host_integration_status)

    student_coach_preview_parser = sub.add_parser("student-coach-preview", help="Preview the public-safe AIvaMax student coach response.")
    student_coach_preview_parser.add_argument("--question", required=True)
    student_coach_preview_parser.add_argument("--course")
    student_coach_preview_parser.add_argument("--module")
    student_coach_preview_parser.add_argument("--role", default="student_public", choices=["owner_admin", "team_operator", "instructor_private", "student_public"])
    student_coach_preview_parser.add_argument("--json", action="store_true")
    student_coach_preview_parser.set_defaults(func=run_student_coach_preview)

    search = sub.add_parser("search", help="Search the local index.")
    search.add_argument("query")
    search.add_argument("--top", type=int, default=8)
    search.add_argument("--corpus", default="web", choices=["web", "vendor", "all", "auto"])
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=run_search)

    search_source = sub.add_parser("search-source", help="Search a private source adapter.")
    search_source.add_argument("--source", choices=[DEFAULT_SOURCE], default=DEFAULT_SOURCE)
    search_source.add_argument("query")
    search_source.add_argument("--top", type=int, default=8)
    search_source.add_argument("--corpus", default="web", choices=["web", "vendor", "all", "auto"])
    search_source.add_argument("--json", action="store_true")
    search_source.set_defaults(func=run_search_source)

    init_matrix = sub.add_parser("init-matrix", help="Initialize AIvaMax Obsidian Matrix dashboards, templates, and course stubs.")
    init_matrix.add_argument("--force", action="store_true", help="Overwrite existing matrix template files.")
    init_matrix.add_argument("--dry-run", action="store_true")
    init_matrix.add_argument("--json", action="store_true")
    init_matrix.set_defaults(func=run_init_matrix)

    template_derive = sub.add_parser("template-derive", help="Derive an internal AIvaMax template draft from a vendor source document.")
    template_derive.add_argument("--source-doc", required=True)
    template_derive.add_argument("--template-id")
    template_derive.add_argument("--out")
    template_derive.add_argument("--force", action="store_true")
    template_derive.add_argument("--dry-run", action="store_true")
    template_derive.add_argument("--json", action="store_true")
    template_derive.set_defaults(func=run_template_derive)

    course_factory_build = sub.add_parser("course-factory-build", help="Build and thicken the AIvaMax 12-module course factory from its V2 teaching pack.")
    course_factory_build.add_argument("--course")
    course_factory_build.add_argument("--course-dir")
    course_factory_build.add_argument("--teaching-pack")
    course_factory_build.add_argument("--force", action="store_true")
    course_factory_build.add_argument("--dry-run", action="store_true")
    course_factory_build.add_argument("--json", action="store_true")
    course_factory_build.set_defaults(func=run_course_factory_build)

    course_factory_audit = sub.add_parser("course-factory-audit", help="Audit the AIvaMax course factory module structure, source trace, risk gates, and brand safety.")
    course_factory_audit.add_argument("--course")
    course_factory_audit.add_argument("--course-dir")
    course_factory_audit.add_argument("--json", action="store_true")
    course_factory_audit.set_defaults(func=run_course_factory_audit)

    client_pack_generate = sub.add_parser("client-pack-generate", help="Generate a client delivery pack from AIvaMax course factory templates.")
    client_pack_generate.add_argument("--client-code", default="")
    client_pack_generate.add_argument("--industry", required=True)
    client_pack_generate.add_argument("--product", required=True)
    client_pack_generate.add_argument("--market", default="United States")
    client_pack_generate.add_argument("--goal", default="lead_generation")
    client_pack_generate.add_argument("--days", type=int, default=30)
    client_pack_generate.add_argument("--out")
    client_pack_generate.add_argument("--force", action="store_true")
    client_pack_generate.add_argument("--dry-run", action="store_true")
    client_pack_generate.add_argument("--json", action="store_true")
    client_pack_generate.set_defaults(func=run_client_pack_generate)

    sales_preview_generate = sub.add_parser("sales-preview-generate", help="Generate a course-level public-safe sales preview pack.")
    sales_preview_generate.add_argument("--course")
    sales_preview_generate.add_argument("--course-dir")
    sales_preview_generate.add_argument("--format", default="html", choices=["md", "html", "all"])
    sales_preview_generate.add_argument("--out")
    sales_preview_generate.add_argument("--force", action="store_true")
    sales_preview_generate.add_argument("--dry-run", action="store_true")
    sales_preview_generate.add_argument("--json", action="store_true")
    sales_preview_generate.set_defaults(func=run_sales_preview_generate)

    course_factory_export_all = sub.add_parser("course-factory-export-all", help="Export all course factory modules into course-level public manuals.")
    course_factory_export_all.add_argument("--course")
    course_factory_export_all.add_argument("--course-dir")
    course_factory_export_all.add_argument("--format", default="html", choices=["md", "html", "all"])
    course_factory_export_all.add_argument("--out")
    course_factory_export_all.add_argument("--force", action="store_true")
    course_factory_export_all.add_argument("--dry-run", action="store_true")
    course_factory_export_all.add_argument("--skip-audit", action="store_true")
    course_factory_export_all.add_argument("--json", action="store_true")
    course_factory_export_all.set_defaults(func=run_course_factory_export_all)

    course_factory_run_all = sub.add_parser("course-factory-run-all", help="Run the full AIvaMax course factory production pipeline.")
    course_factory_run_all.add_argument("--course", default="AIvaMax社媒自动化增长系统课")
    course_factory_run_all.add_argument("--course-dir")
    course_factory_run_all.add_argument("--teaching-pack")
    course_factory_run_all.add_argument("--format", default="html", choices=["md", "html", "all"])
    course_factory_run_all.add_argument("--export-root")
    course_factory_run_all.add_argument("--client-root")
    course_factory_run_all.add_argument("--client-scenarios")
    course_factory_run_all.add_argument("--report-dir")
    course_factory_run_all.add_argument("--report-name")
    course_factory_run_all.add_argument("--build", action="store_true")
    course_factory_run_all.add_argument("--no-client-packs", action="store_true")
    course_factory_run_all.add_argument("--force", action="store_true")
    course_factory_run_all.add_argument("--dry-run", action="store_true")
    course_factory_run_all.add_argument("--skip-audit", action="store_true")
    course_factory_run_all.add_argument("--json", action="store_true")
    course_factory_run_all.set_defaults(func=run_course_factory_run_all)

    platform_playbook = sub.add_parser("platform-playbook", help="Create an AIvaMax platform-specific playbook.")
    platform_playbook.add_argument("--platform", default="instagram", choices=["instagram", "facebook", "tiktok", "linkedin", "x_twitter", "twitter", "x", "all"])
    platform_playbook.add_argument("--lang", default="zh-CN", choices=["zh-CN", "bilingual", "en"])
    platform_playbook.add_argument("--out")
    platform_playbook.add_argument("--dry-run", action="store_true")
    platform_playbook.add_argument("--json", action="store_true")
    platform_playbook.set_defaults(func=run_platform_playbook)

    boundary_brief = sub.add_parser("boundary-brief", help="Create an AIvaMax platform risk boundary brief.")
    boundary_brief.add_argument("--platform", default="instagram", choices=["instagram", "facebook", "tiktok", "linkedin", "x_twitter", "twitter", "x", "all"])
    boundary_brief.add_argument("--lang", default="zh-CN", choices=["zh-CN", "bilingual", "en"])
    boundary_brief.add_argument("--out")
    boundary_brief.add_argument("--dry-run", action="store_true")
    boundary_brief.add_argument("--json", action="store_true")
    boundary_brief.set_defaults(func=run_boundary_brief)

    run_matrix = sub.add_parser("run-matrix", help="Run the full AIvaMax Matrix flow from request to audited project and course assets.")
    run_matrix.add_argument("--goal", required=True, help="Natural-language marketing request or business goal.")
    run_matrix.add_argument("--template", default="instagram-comment-leadgen-14d")
    run_matrix.add_argument("--task-id")
    run_matrix.add_argument("--platform", default="instagram")
    run_matrix.add_argument("--accounts", type=int)
    run_matrix.add_argument("--stage", default="unknown")
    run_matrix.add_argument("--offer", default="unknown")
    run_matrix.add_argument("--days", type=int, default=14)
    run_matrix.add_argument("--risk", default="conservative", choices=["conservative", "balanced", "aggressive"])
    run_matrix.add_argument("--scenario", default="account_safety_comment_leadgen")
    run_matrix.add_argument("--proxies", default="unknown")
    run_matrix.add_argument("--vps", default="unknown")
    run_matrix.add_argument("--content-assets", default="unknown")
    run_matrix.add_argument("--keyword", action="append", default=[])
    run_matrix.add_argument("--top", type=int, default=8)
    run_matrix.add_argument("--corpus", default="web", choices=["web", "vendor", "all", "auto"])
    run_matrix.add_argument("--run-id")
    run_matrix.add_argument("--project-id")
    run_matrix.add_argument("--course-name")
    run_matrix.add_argument("--module-id")
    run_matrix.add_argument("--lang", default="zh-CN", choices=["zh-CN", "bilingual", "en"])
    run_matrix.add_argument("--visuals", default="mermaid", choices=["none", "mermaid", "media", "all"])
    run_matrix.add_argument("--depth", default="brief", choices=["brief", "deep", "course"])
    run_matrix.add_argument("--sop-layer", default="standard", choices=["standard", "public", "internal", "dual"])
    run_matrix.add_argument("--force", action="store_true")
    run_matrix.add_argument("--dry-run", action="store_true")
    run_matrix.add_argument("--json", action="store_true")
    run_matrix.set_defaults(func=run_run_matrix)

    brief = sub.add_parser("brief", help="Create an AIvaMax TaskBrief.")
    brief.add_argument("--template", default="instagram-comment-leadgen-14d")
    brief.add_argument("--task-id")
    brief.add_argument("--platform", default="instagram")
    brief.add_argument("--accounts", type=int)
    brief.add_argument("--stage", default="unknown")
    brief.add_argument("--offer", default="unknown")
    brief.add_argument("--days", type=int, default=14)
    brief.add_argument("--risk", default="conservative", choices=["conservative", "balanced", "aggressive"])
    brief.add_argument("--goal", default="lead_generation")
    brief.add_argument("--scenario", default="account_safety_comment_leadgen")
    brief.add_argument("--proxies", default="unknown")
    brief.add_argument("--vps", default="unknown")
    brief.add_argument("--content-assets", default="unknown")
    brief.add_argument("--keyword", action="append", default=[])
    brief.add_argument("--format", choices=["json", "markdown"], default="json")
    brief.add_argument("--out")
    brief.add_argument("--dry-run", action="store_true")
    brief.set_defaults(func=run_brief)

    evidence = sub.add_parser("evidence", help="Create a public AIvaMax EvidencePack from a TaskBrief.")
    evidence.add_argument("--brief", required=True)
    evidence.add_argument("--top", type=int, default=8)
    evidence.add_argument("--corpus", default="web", choices=["web", "vendor", "all", "auto"])
    evidence.add_argument("--format", choices=["json", "markdown"], default="json")
    evidence.add_argument("--out")
    evidence.add_argument("--dry-run", action="store_true")
    evidence.add_argument("--internal", action="store_true", help="Include private source metadata. Do not use for public outputs.")
    evidence.set_defaults(func=run_evidence)

    sop = sub.add_parser("sop", help="Compile an AIvaMax SOP draft from TaskBrief and EvidencePack.")
    sop.add_argument("--brief", required=True)
    sop.add_argument("--evidence", required=True)
    sop.add_argument("--format", choices=["markdown", "json"], default="markdown")
    sop.add_argument("--lang", default="zh-CN", choices=["zh-CN", "bilingual", "en"])
    sop.add_argument("--visuals", default="none", choices=["none", "mermaid", "media", "all"])
    sop.add_argument("--depth", default="brief", choices=["brief", "deep", "course"])
    sop.add_argument("--sop-layer", default="standard", choices=["standard", "public", "internal", "dual"])
    sop.add_argument("--out")
    sop.add_argument("--dry-run", action="store_true")
    sop.set_defaults(func=run_sop)

    risk = sub.add_parser("risk-audit", help="Audit an AIvaMax SOP draft for account and brand risk.")
    risk.add_argument("--brief", required=True)
    risk.add_argument("--evidence", required=True)
    risk.add_argument("--sop", required=True)
    risk.add_argument("--format", choices=["markdown", "json"], default="markdown")
    risk.add_argument("--lang", default="zh-CN", choices=["zh-CN", "bilingual", "en"])
    risk.add_argument("--out")
    risk.add_argument("--dry-run", action="store_true")
    risk.set_defaults(func=run_risk_audit)

    project = sub.add_parser("project", help="Create an AIvaMax Obsidian Matrix project package.")
    project.add_argument("--brief", required=True)
    project.add_argument("--evidence", required=True)
    project.add_argument("--sop", required=True)
    project.add_argument("--risk", required=True)
    project.add_argument("--project-id")
    project.add_argument("--lang", default="zh-CN", choices=["zh-CN", "bilingual", "en"])
    project.add_argument("--depth", default="brief", choices=["brief", "deep", "course"])
    project.add_argument("--sop-layer", default="standard", choices=["standard", "public", "internal", "dual"])
    project.add_argument("--out")
    project.add_argument("--dry-run", action="store_true")
    project.set_defaults(func=run_project)

    course = sub.add_parser("course", help="Create a public AIvaMax course module from an AIvaMax project package.")
    course.add_argument("--project", required=True, help="AIvaMax project folder containing 00_Brief.md, 02_Risk-Review.md, and 03_14-Day-SOP.md.")
    course.add_argument("--course-name", default="AIvaMax账号安全与获客SOP课")
    course.add_argument("--module-id")
    course.add_argument("--lang", default="zh-CN", choices=["zh-CN", "bilingual", "en"])
    course.add_argument("--visuals", default="none", choices=["none", "mermaid", "media", "all"])
    course.add_argument("--depth", default="brief", choices=["brief", "deep", "course"])
    course.add_argument("--out")
    course.add_argument("--force", action="store_true")
    course.add_argument("--dry-run", action="store_true")
    course.add_argument("--json", action="store_true")
    course.set_defaults(func=run_course)

    brand_audit = sub.add_parser("brand-audit", help="Check public outputs for leaked private source branding.")
    brand_audit.add_argument("--path", required=True)
    brand_audit.add_argument("--json", action="store_true")
    brand_audit.set_defaults(func=run_brand_audit)

    artifact_audit = sub.add_parser("artifact-audit", help="Check artifact visibility manifests and course/internal separation.")
    artifact_audit.add_argument("--path")
    artifact_audit.add_argument("--json", action="store_true")
    artifact_audit.set_defaults(func=run_artifact_audit)

    quality_audit = sub.add_parser("quality-audit", help="Audit course-level AIvaMax project and course deliverables.")
    quality_audit.add_argument("--project", required=True)
    quality_audit.add_argument("--course", required=True)
    quality_audit.add_argument("--lang", default="zh-CN", choices=["zh-CN", "bilingual", "en"])
    quality_audit.add_argument("--strict", default="basic", choices=["basic", "course-release"])
    quality_audit.add_argument("--json", action="store_true")
    quality_audit.set_defaults(func=run_quality_audit)

    media_import = sub.add_parser("media-import", help="Import a screenshot or media asset into the AIvaMax media library.")
    media_import.add_argument("--path", required=True)
    media_import.add_argument("--module", default="general")
    media_import.add_argument("--step", default="general")
    media_import.add_argument("--platform", default="general")
    media_import.add_argument("--caption", default="")
    media_import.add_argument("--alt", default="")
    media_import.add_argument("--audit-status", default="pending", choices=["pending", "approved", "blocked"])
    media_import.add_argument("--dry-run", action="store_true")
    media_import.add_argument("--json", action="store_true")
    media_import.set_defaults(func=run_media_import)

    media_list = sub.add_parser("media-list", help="List AIvaMax media library assets.")
    media_list.add_argument("--json", action="store_true")
    media_list.set_defaults(func=run_media_list)

    media_audit = sub.add_parser("media-audit", help="Audit media metadata and paths for private source leakage or pending approval.")
    media_audit.add_argument("--path")
    media_audit.add_argument("--json", action="store_true")
    media_audit.set_defaults(func=run_media_audit)

    media_plan = sub.add_parser("media-plan", help="Create screenshot, video, and case-material capture plans for AIvaMax courses.")
    media_plan.add_argument("--platform", default="instagram", choices=["instagram", "facebook", "tiktok", "linkedin", "x_twitter", "twitter", "x", "all"])
    media_plan.add_argument("--out")
    media_plan.add_argument("--dry-run", action="store_true")
    media_plan.add_argument("--json", action="store_true")
    media_plan.set_defaults(func=run_media_plan)

    case_plan = sub.add_parser("case-plan", help="Create AIvaMax public-safe case collection plans for course labs.")
    case_plan.add_argument("--platform", default="instagram", choices=["instagram", "facebook", "tiktok", "linkedin", "x_twitter", "twitter", "x", "all"])
    case_plan.add_argument("--out")
    case_plan.add_argument("--dry-run", action="store_true")
    case_plan.add_argument("--json", action="store_true")
    case_plan.set_defaults(func=run_case_plan)

    case_audit = sub.add_parser("case-audit", help="Audit case plans and case-library notes for redaction, review status, and blocked markers.")
    case_audit.add_argument("--path")
    case_audit.add_argument("--json", action="store_true")
    case_audit.set_defaults(func=run_case_audit)

    course_release = sub.add_parser("course-release", help="Generate Obsidian course productization files and run strict release quality audit.")
    course_release.add_argument("--project", required=True)
    course_release.add_argument("--course", required=True)
    course_release.add_argument("--course-name")
    course_release.add_argument("--force", action="store_true")
    course_release.add_argument("--dry-run", action="store_true")
    course_release.add_argument("--json", action="store_true")
    course_release.set_defaults(func=run_course_release)

    dashboard_refresh = sub.add_parser("dashboard-refresh", help="Refresh the AIvaMax Obsidian course delivery dashboard.")
    dashboard_refresh.add_argument("--project")
    dashboard_refresh.add_argument("--course")
    dashboard_refresh.add_argument("--course-name")
    dashboard_refresh.add_argument("--out")
    dashboard_refresh.add_argument("--force", action="store_true")
    dashboard_refresh.add_argument("--dry-run", action="store_true")
    dashboard_refresh.add_argument("--json", action="store_true")
    dashboard_refresh.set_defaults(func=run_dashboard_refresh)

    course_export = sub.add_parser("course-export", help="Export an AIvaMax course module into public Markdown and print-ready HTML manuals.")
    course_export.add_argument("--course", default="AIvaMax账号安全与获客SOP课")
    course_export.add_argument("--module", required=True)
    course_export.add_argument("--course-dir")
    course_export.add_argument("--format", default="html", choices=["md", "html", "all"])
    course_export.add_argument("--out")
    course_export.add_argument("--force", action="store_true")
    course_export.add_argument("--dry-run", action="store_true")
    course_export.add_argument("--json", action="store_true")
    course_export.set_defaults(func=run_course_export)

    release_demo = sub.add_parser("release-demo", help="Generate a public-safe course demo/sales intro pack.")
    release_demo.add_argument("--course", default="AIvaMax账号安全与获客SOP课")
    release_demo.add_argument("--module", required=True)
    release_demo.add_argument("--course-dir")
    release_demo.add_argument("--format", default="html", choices=["md", "html", "all"])
    release_demo.add_argument("--out")
    release_demo.add_argument("--force", action="store_true")
    release_demo.add_argument("--dry-run", action="store_true")
    release_demo.add_argument("--json", action="store_true")
    release_demo.set_defaults(func=run_release_demo)

    sales_pack = sub.add_parser("sales-pack", help="Generate a private-domain sales pack for the AIvaMax benchmark course.")
    sales_pack.add_argument("--course", default="AIvaMax账号安全与获客SOP课")
    sales_pack.add_argument("--module", required=True)
    sales_pack.add_argument("--course-dir")
    sales_pack.add_argument("--format", default="html", choices=["md", "html", "all"])
    sales_pack.add_argument("--out")
    sales_pack.add_argument("--force", action="store_true")
    sales_pack.add_argument("--dry-run", action="store_true")
    sales_pack.add_argument("--json", action="store_true")
    sales_pack.set_defaults(func=run_sales_pack)

    preview_pack = sub.add_parser("preview-pack", help="Generate a lightweight public-safe trial lesson pack.")
    preview_pack.add_argument("--course", default="AIvaMax账号安全与获客SOP课")
    preview_pack.add_argument("--module", required=True)
    preview_pack.add_argument("--course-dir")
    preview_pack.add_argument("--format", default="html", choices=["md", "html", "all"])
    preview_pack.add_argument("--out")
    preview_pack.add_argument("--force", action="store_true")
    preview_pack.add_argument("--dry-run", action="store_true")
    preview_pack.add_argument("--json", action="store_true")
    preview_pack.set_defaults(func=run_preview_pack)

    visual_card = sub.add_parser("visual-card", help="Create a reusable AIvaMax visual card as Markdown/HTML.")
    visual_card.add_argument("--type", default="agent-flow", choices=["risk-map", "14-day-plan", "agent-flow", "content-matrix", "account-safety"])
    visual_card.add_argument("--lang", default="zh-CN", choices=["zh-CN", "bilingual", "en"])
    visual_card.add_argument("--out")
    visual_card.add_argument("--dry-run", action="store_true")
    visual_card.set_defaults(func=run_visual_card)

    agent_run = sub.add_parser("agent-run", help="List or show AIvaMax Matrix agent run records.")
    agent_run.add_argument("--id", help="Run id or partial run id to show.")
    agent_run.add_argument("--limit", type=int, default=10)
    agent_run.add_argument("--json", action="store_true")
    agent_run.set_defaults(func=run_agent_run)

    task = sub.add_parser("task", help="Generate a task plan from retrieved sources.")
    task.add_argument("task")
    task.add_argument("--top", type=int, default=8)
    task.add_argument("--out")
    task.set_defaults(func=run_task)

    teach = sub.add_parser("teach", help="Generate a learning path from retrieved sources.")
    teach.add_argument("topic")
    teach.add_argument("--top", type=int, default=8)
    teach.add_argument("--out")
    teach.set_defaults(func=run_teach)

    show = sub.add_parser("show", help="Show one indexed page by id, URL, or title text.")
    show.add_argument("id_or_url")
    show.add_argument("--chars", type=int, default=3000)
    show.set_defaults(func=run_show)

    stats = sub.add_parser("stats", help="Show index statistics.")
    stats.set_defaults(func=run_stats)

    reindex = sub.add_parser("reindex", help="Rebuild notes and index from saved raw HTML.")
    reindex.set_defaults(func=run_reindex)

    export = sub.add_parser("export-obsidian", help="Export pages and MOC notes for Obsidian.")
    export.add_argument("--out")
    export.set_defaults(func=run_export_obsidian)

    doctor = sub.add_parser("doctor", help="Check local setup.")
    doctor.set_defaults(func=run_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
