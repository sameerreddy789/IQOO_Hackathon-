"""SCOUT — semantic repository discovery and community sentiment via Exa AI.

Two query modes per node:

    repo candidates   includeDomains = github.com, gitlab.com, bitbucket.org
    community signal  includeDomains = reddit.com, x.com, linkedin.com

Every response is cached to disk keyed by request body. That is not just a dev
convenience: it means a live demo can replay without the API, which is the
documented fallback in ONSITE_BUILD_PLAN.md if the key rate-limits mid-judging.

API contract per https://exa.ai/docs/reference/search-api-guide-for-coding-agents
- POST https://api.exa.ai/search
- Auth via `Authorization: Bearer <key>`
- text/highlights/summary MUST be nested under `contents`
- responses carry no documented relevance score, so it is derived from rank

Usage:
    python -m devcontext.scout --payload examples/sample_payload.json --out scouted.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dataclasses import replace

from .models import BrainPayload, Candidate, ScoutedNode, TrendSignal

EXA_ENDPOINT = "https://api.exa.ai/search"
REPO_DOMAINS = ["github.com", "gitlab.com", "bitbucket.org"]
COMMUNITY_DOMAINS = ["reddit.com", "x.com", "linkedin.com"]
DEFAULT_CACHE = Path(__file__).resolve().parents[1] / ".cache" / "exa"


class ExaError(RuntimeError):
    """Raised when Exa returns a non-retryable error."""


class MissingKeyError(ExaError):
    """Raised when no API key is configured."""


@dataclass
class ScoutStats:
    """Observability for a scouting run. Cost matters on a hackathon budget."""

    api_calls: int = 0
    cache_hits: int = 0
    results: int = 0
    cost_usd: float = 0.0
    errors: list[str] = field(default_factory=list)

    def render(self) -> str:
        return (
            f"api calls {self.api_calls} · cache hits {self.cache_hits} · "
            f"results {self.results} · cost ${self.cost_usd:.4f}"
            + (f" · errors {len(self.errors)}" if self.errors else "")
        )


def load_api_key() -> str | None:
    """Read EXA_API_KEY from the environment, falling back to a local .env file.

    The value is never logged or echoed anywhere in this module.
    """
    key = os.environ.get("EXA_API_KEY", "").strip()
    if key:
        return key

    for candidate in (
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ):
        if not candidate.is_file():
            continue
        try:
            for raw in candidate.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == "EXA_API_KEY":
                    return value.strip().strip("'\"") or None
        except OSError:
            continue
    return None


class ExaClient:
    """Minimal Exa /search client with disk caching and 429 backoff."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key if api_key is not None else load_api_key()
        self.cache_dir = cache_dir or DEFAULT_CACHE
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_retries = max_retries
        self.stats = ScoutStats()

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    def _cache_path(self, body: dict[str, Any]) -> Path:
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()[:20]
        return self.cache_dir / f"{digest}.json"

    def search(
        self,
        query: str,
        *,
        num_results: int = 6,
        include_domains: list[str] | None = None,
        search_type: str = "auto",
        max_highlight_chars: int = 420,
    ) -> dict[str, Any]:
        """Run one search. Returns the parsed Exa response body.

        `highlights` is used rather than full `text` because it returns far less
        payload for the same signal, which matters on a metered key.
        """
        body: dict[str, Any] = {
            "query": query,
            "type": search_type,
            "numResults": num_results,
            "contents": {
                "highlights": True,
                "text": {"maxCharacters": max_highlight_chars},
            },
        }
        if include_domains:
            body["includeDomains"] = include_domains

        cache_file = self._cache_path(body)
        if cache_file.is_file():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                self.stats.cache_hits += 1
                return cached
            except (OSError, json.JSONDecodeError):
                pass  # corrupt cache entry, fall through to a live call

        if not self._api_key:
            raise MissingKeyError(
                "EXA_API_KEY is not set. Add it to .env or the environment, "
                "or run with --offline to skip scouting."
            )

        payload = json.dumps(body).encode("utf-8")
        last_error = ""

        for attempt in range(1, self.max_retries + 1):
            request = urllib.request.Request(
                EXA_ENDPOINT,
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    parsed = json.loads(response.read().decode("utf-8"))
                self.stats.api_calls += 1
                cost = parsed.get("costDollars")
                if isinstance(cost, dict) and isinstance(cost.get("total"), (int, float)):
                    self.stats.cost_usd += float(cost["total"])
                try:
                    cache_file.write_text(
                        json.dumps(parsed, ensure_ascii=False), encoding="utf-8"
                    )
                except OSError:
                    pass  # cache write failure must not fail the run
                return parsed

            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:200]
                if exc.code == 401:
                    raise ExaError("Exa rejected the API key (401).") from exc
                if exc.code in (400, 422):
                    raise ExaError(f"Exa rejected the request ({exc.code}): {detail}") from exc
                if exc.code == 429:
                    wait = min(2 ** attempt, 8)
                    last_error = f"rate limited (429), retry in {wait}s"
                    time.sleep(wait)
                    continue
                last_error = f"HTTP {exc.code}: {detail}"
                time.sleep(min(2 ** attempt, 8))
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = f"network error: {exc}"
                time.sleep(min(2 ** attempt, 8))
            except json.JSONDecodeError as exc:
                raise ExaError(f"Exa returned malformed JSON: {exc}") from exc

        raise ExaError(f"Exa search failed after {self.max_retries} attempts: {last_error}")


# --------------------------------------------------------------------------- #
# result shaping
# --------------------------------------------------------------------------- #

def _host_of(url: str) -> str:
    for host in REPO_DOMAINS + COMMUNITY_DOMAINS:
        if host in url:
            return host
    return ""


def _repo_name(url: str, fallback: str) -> str:
    """Derive `owner/repo` from a repository URL, else fall back to the title."""
    cleaned = url.split("?", 1)[0].rstrip("/")
    for host in REPO_DOMAINS:
        marker = host + "/"
        if marker in cleaned:
            tail = cleaned.split(marker, 1)[1]
            segments = [s for s in tail.split("/") if s]
            if len(segments) >= 2:
                return f"{segments[0]}/{segments[1]}"
            if segments:
                return segments[0]
    return (fallback or cleaned)[:80]


def _excerpt(result: dict[str, Any], limit: int = 420) -> str:
    highlights = result.get("highlights")
    if isinstance(highlights, list) and highlights:
        joined = " ".join(str(h).strip() for h in highlights if h)
        if joined:
            return joined[:limit].strip()
    for key in ("summary", "text"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())[:limit].strip()
    return ""


def _rank_score(index: int, total: int, reported: object) -> float:
    """Use Exa's score when present, else derive a descending score from rank.

    Exa does not document a score field on /search results, so rank is the
    honest signal. Kept explicit rather than silently defaulting to 0.0.
    """
    if isinstance(reported, (int, float)) and 0 < float(reported) <= 1:
        return round(float(reported), 4)
    if total <= 1:
        return 1.0
    return round(1.0 - (index / (total * 1.25)), 4)


def _to_candidates(response: dict[str, Any]) -> list[Candidate]:
    results = response.get("results")
    if not isinstance(results, list):
        return []
    total = len(results)
    candidates: list[Candidate] = []
    seen: set[str] = set()

    for index, result in enumerate(results):
        if not isinstance(result, dict):
            continue
        url = str(result.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        candidates.append(
            Candidate(
                name=_repo_name(url, str(result.get("title") or "")),
                url=url,
                summary=_excerpt(result),
                host=_host_of(url),
                published=str(result.get("publishedDate") or ""),
                score=_rank_score(index, total, result.get("score")),
                selected=False,
            )
        )
    return candidates


def _to_trends(response: dict[str, Any]) -> list[TrendSignal]:
    results = response.get("results")
    if not isinstance(results, list):
        return []
    signals: list[TrendSignal] = []
    seen: set[str] = set()

    for result in results:
        if not isinstance(result, dict):
            continue
        url = str(result.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        signals.append(
            TrendSignal(
                title=str(result.get("title") or "Untitled discussion")[:180],
                url=url,
                source=_host_of(url),
                excerpt=_excerpt(result),
                published=str(result.get("publishedDate") or ""),
            )
        )
    return signals


# --------------------------------------------------------------------------- #
# queries
# --------------------------------------------------------------------------- #

def repo_query(node: ScoutedNode) -> str:
    parts = [node.title, node.requirement]
    if node.search_hint:
        parts.append(node.search_hint)
    return (
        "well-maintained open source library or starter repository for: "
        + " ".join(p.strip() for p in parts if p.strip())
    )


def trend_query(node: ScoutedNode) -> str:
    topic = node.search_hint or node.title
    return (
        f"developer discussion about real-world problems, limitations and "
        f"maintenance complaints with {topic}"
    )


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #

def scout_payload(
    payload: BrainPayload,
    client: ExaClient | None = None,
    *,
    repos_per_node: int = 4,
    trends_per_node: int = 3,
    include_trends: bool = True,
    verbose: bool = True,
) -> ScoutStats:
    """Attach repo candidates and community signals to every node, in place."""
    client = client or ExaClient()

    if not client.enabled:
        message = "EXA_API_KEY not configured — scouting skipped, nodes left unenriched"
        client.stats.errors.append(message)
        if verbose:
            print(f"  ! {message}")
        return client.stats

    for node in payload.nodes:
        if verbose:
            print(f"  scouting {node.id} ({node.category})")

        try:
            response = client.search(
                repo_query(node),
                num_results=repos_per_node,
                include_domains=REPO_DOMAINS,
            )
            node.candidates = _to_candidates(response)
            if node.candidates:
                top = max(node.candidates, key=lambda c: c.score)
                node.candidates = [
                    replace(c, selected=(c.url == top.url)) for c in node.candidates
                ]
            client.stats.results += len(node.candidates)
            if verbose:
                print(f"    repos   : {len(node.candidates)}")
        except ExaError as exc:
            client.stats.errors.append(f"{node.id} repos: {exc}")
            if verbose:
                print(f"    repos   : failed ({exc})")

        if not include_trends:
            continue

        try:
            response = client.search(
                trend_query(node),
                num_results=trends_per_node,
                include_domains=COMMUNITY_DOMAINS,
            )
            node.trends = _to_trends(response)
            client.stats.results += len(node.trends)
            if verbose:
                print(f"    signals : {len(node.trends)}")
        except ExaError as exc:
            client.stats.errors.append(f"{node.id} trends: {exc}")
            if verbose:
                print(f"    signals : failed ({exc})")

    return client.stats


def main(argv: list[str] | None = None) -> int:
    from . import enable_utf8_stdout

    enable_utf8_stdout()
    parser = argparse.ArgumentParser(
        prog="devcontext.scout",
        description="Enrich a node graph with vetted repos and community signal via Exa.",
    )
    parser.add_argument("--payload", required=True, help="path to a payload or node graph JSON")
    parser.add_argument("--out", help="write the enriched payload here (default: stdout)")
    parser.add_argument("--repos", type=int, default=4, help="repo candidates per node")
    parser.add_argument("--trends", type=int, default=3, help="community signals per node")
    parser.add_argument("--no-trends", action="store_true", help="skip the community pass")
    args = parser.parse_args(argv)

    try:
        raw = json.loads(Path(args.payload).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: could not read payload: {exc}", file=sys.stderr)
        return 1

    payload = BrainPayload.from_dict(raw) if "nodes" in raw else None
    if payload is None:
        print("error: payload has no 'nodes' array", file=sys.stderr)
        return 1

    print(f"Scouting {len(payload.nodes)} nodes for: {payload.project_name}")
    client = ExaClient()
    if not client.enabled:
        print("\n  EXA_API_KEY not found.")
        print("  Set it in .env at the repo root:  EXA_API_KEY=your_key_here")
        print("  Get a key at https://dashboard.exa.ai/api-keys")

    stats = scout_payload(
        payload,
        client,
        repos_per_node=args.repos,
        trends_per_node=args.trends,
        include_trends=not args.no_trends,
    )

    print(f"\n{stats.render()}")
    for err in stats.errors[:6]:
        print(f"  ! {err}")

    serialized = json.dumps(payload.to_dict(), indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(serialized + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}")
    else:
        print()
        print(serialized)
    return 0 if not stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
