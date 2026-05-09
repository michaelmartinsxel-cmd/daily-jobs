#!/usr/bin/env python3
import os
import re
import sys
import html
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests
import yaml
from jinja2 import Environment, FileSystemLoader

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = REPO_ROOT / "public"

BRT = timezone(timedelta(hours=-3))


def load_config() -> dict:
    config_path = REPO_ROOT / "config.yml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── We Work Remotely ────────────────────────────────────────────────────────

WWR_RSS = "https://weworkremotely.com/remote-jobs.rss"


def fetch_wwr_rss(keywords: list[str]) -> list[dict]:
    log.info("Fetching We Work Remotely RSS...")
    try:
        feed = feedparser.parse(WWR_RSS)
    except Exception as exc:
        log.warning("WWR RSS failed: %s", exc)
        return []

    jobs = []
    kw_lower = [k.lower() for k in keywords]

    for entry in feed.entries:
        title = entry.get("title", "")
        summary = entry.get("summary", "")
        text = f"{title} {summary}".lower()

        if not any(kw in text for kw in kw_lower):
            continue

        region = ""
        if hasattr(entry, "tags"):
            for tag in entry.tags:
                region = tag.get("term", "")
                break

        jobs.append({
            "id": entry.get("id", entry.get("link", "")),
            "title": html.unescape(title),
            "company": entry.get("author", ""),
            "location": region or "Remote",
            "description": html.unescape(summary),
            "url": entry.get("link", ""),
            "source": "We Work Remotely",
            "posted_at": entry.get("published", ""),
        })

    log.info("WWR: %d jobs found", len(jobs))
    return jobs


# ── JSearch (RapidAPI) ──────────────────────────────────────────────────────

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"


def fetch_jsearch(keywords: list[str]) -> list[dict]:
    api_key = os.getenv("JSEARCH_API_KEY", "")
    if not api_key:
        log.info("JSEARCH_API_KEY not set, skipping JSearch.")
        return []

    log.info("Fetching JSearch...")
    jobs = []
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    for kw in keywords[:3]:  # limit to avoid rate cap
        try:
            resp = requests.get(
                JSEARCH_URL,
                headers=headers,
                params={"query": kw, "num_pages": "1", "remote_jobs_only": "true"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except Exception as exc:
            log.warning("JSearch error for '%s': %s", kw, exc)
            continue

        for item in data:
            jobs.append({
                "id": item.get("job_id", ""),
                "title": item.get("job_title", ""),
                "company": item.get("employer_name", ""),
                "location": item.get("job_city") or item.get("job_country") or "Remote",
                "description": item.get("job_description", ""),
                "url": item.get("job_apply_link", ""),
                "source": "JSearch",
                "posted_at": item.get("job_posted_at_datetime_utc", ""),
            })

    log.info("JSearch: %d jobs found", len(jobs))
    return jobs


# ── Adzuna ──────────────────────────────────────────────────────────────────

ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/gb/search/1"


def fetch_adzuna(keywords: list[str]) -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID", "")
    app_key = os.getenv("ADZUNA_APP_KEY", "")
    if not app_id or not app_key:
        log.info("ADZUNA_APP_ID/ADZUNA_APP_KEY not set, skipping Adzuna.")
        return []

    log.info("Fetching Adzuna...")
    jobs = []

    for kw in keywords[:3]:
        try:
            resp = requests.get(
                ADZUNA_URL,
                params={
                    "app_id": app_id,
                    "app_key": app_key,
                    "what": kw,
                    "content-type": "application/json",
                    "results_per_page": 10,
                },
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
        except Exception as exc:
            log.warning("Adzuna error for '%s': %s", kw, exc)
            continue

        for item in results:
            jobs.append({
                "id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "company": item.get("company", {}).get("display_name", ""),
                "location": item.get("location", {}).get("display_name", ""),
                "description": item.get("description", ""),
                "url": item.get("redirect_url", ""),
                "source": "Adzuna",
                "posted_at": item.get("created", ""),
            })

    log.info("Adzuna: %d jobs found", len(jobs))
    return jobs


# ── Dedup ────────────────────────────────────────────────────────────────────

def dedup(jobs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique = []
    for job in jobs:
        key = f"{job['title'].lower().strip()}|{job['company'].lower().strip()}"
        if key not in seen:
            seen.add(key)
            unique.append(job)
    return unique


# ── Experience filter ────────────────────────────────────────────────────────

def _years_from_text(text: str) -> int | None:
    """Extract the largest explicit year requirement mentioned in text."""
    matches = re.findall(r"(\d+)\+?\s*(?:years?|anos?)", text, re.IGNORECASE)
    if matches:
        return max(int(m) for m in matches)
    return None


def filter_by_experience(jobs: list[dict], config: dict) -> list[dict]:
    exp = config.get("experience", {})
    max_years: int = exp.get("max_years", 99)
    exclude: list[str] = [e.lower() for e in exp.get("exclude_levels", [])]
    include: list[str] = [i.lower() for i in exp.get("include_levels", [])]

    filtered = []
    for job in jobs:
        text = f"{job['title']} {job['description']}".lower()

        # hard exclude if a senior-level keyword is found
        if any(ex in text for ex in exclude):
            continue

        # check explicit year requirement
        required_years = _years_from_text(text)
        if required_years is not None and required_years > max_years:
            continue

        filtered.append(job)

    log.info("After experience filter: %d / %d jobs", len(filtered), len(jobs))
    return filtered


# ── Match calculation ────────────────────────────────────────────────────────

def calculate_match(job: dict, user_stack: list[str]) -> dict:
    text = f"{job['title']} {job['description']}".lower()
    stack_lower = [s.lower() for s in user_stack]

    found = [s for s in stack_lower if s in text]
    missing = [s for s in stack_lower if s not in text]

    pct = round(len(found) / len(stack_lower) * 100) if stack_lower else 0

    return {
        **job,
        "match_pct": pct,
        "skills_found": found,
        "skills_missing": missing,
    }


# ── Modality detection ───────────────────────────────────────────────────────

def detect_modality(job: dict, accepted: list[str]) -> str:
    text = f"{job['title']} {job['location']} {job['description']}".lower()
    accepted_lower = [m.lower() for m in accepted]
    for mod in accepted_lower:
        if mod in text:
            return mod.capitalize()
    return "Unknown"


# ── Render ───────────────────────────────────────────────────────────────────

def render_dashboard(jobs: list[dict], config: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(SCRIPTS_DIR)), autoescape=True)
    template = env.get_template("template.html")

    now_brt = datetime.now(BRT).strftime("%d/%m/%Y às %H:%M (BRT)")
    profile_name = config.get("profile", {}).get("name", "")
    modalities = config.get("search", {}).get("modalities", [])

    for job in jobs:
        job["modality"] = detect_modality(job, modalities)

    return template.render(
        jobs=jobs,
        profile_name=profile_name,
        updated_at=now_brt,
        total=len(jobs),
    )


# ── Deploy ───────────────────────────────────────────────────────────────────

def deploy(html_content: str) -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    out = PUBLIC_DIR / "index.html"
    out.write_text(html_content, encoding="utf-8")
    log.info("Dashboard saved to %s", out)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    config = load_config()
    keywords: list[str] = config.get("search", {}).get("keywords", [])
    user_stack: list[str] = config.get("profile", {}).get("stack", [])

    raw_jobs: list[dict] = []
    raw_jobs += fetch_wwr_rss(keywords)
    raw_jobs += fetch_jsearch(keywords)
    raw_jobs += fetch_adzuna(keywords)

    jobs = dedup(raw_jobs)
    jobs = filter_by_experience(jobs, config)
    jobs = [calculate_match(j, user_stack) for j in jobs]
    jobs.sort(key=lambda j: j["match_pct"], reverse=True)

    log.info("Total jobs after processing: %d", len(jobs))

    html_content = render_dashboard(jobs, config)
    deploy(html_content)


if __name__ == "__main__":
    main()
