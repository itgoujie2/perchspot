#!/usr/bin/env python3
"""
Perchspot Stress Test Script

Ramps up concurrent requests against Perchspot to measure throughput,
latency, and error rates. Identifies bottlenecks (CPU, memory, rate limits).

Usage:
    # External (through nginx rate limits)
    python scripts/stress_test.py --target https://perchspot.com --email user@test.com --password xxx

    # Internal (bypass nginx, raw backend)
    python scripts/stress_test.py --target http://localhost:8000 --email user@test.com --password xxx

    # Skip heavy analysis phase
    python scripts/stress_test.py --target https://perchspot.com --email user@test.com --password xxx --skip-analysis

    # With cache cleanup (repeatable analysis runs)
    python scripts/stress_test.py --target http://localhost:8000 --email user@test.com --password xxx --admin-password xxx

Dependencies:
    pip install aiohttp
"""

import argparse
import asyncio
import json
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import quote

try:
    import aiohttp
except ImportError:
    print("Missing dependency: aiohttp")
    print("Install with:  pip install aiohttp")
    sys.exit(1)


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class PhaseResult:
    endpoint: str
    concurrency: int
    total_requests: int = 0
    successes: int = 0
    status_counts: dict = field(default_factory=dict)
    latencies: list = field(default_factory=list)
    duration_s: float = 0.0
    bottleneck: str = ""

    @property
    def error_count(self):
        return self.total_requests - self.successes

    @property
    def error_pct(self):
        return (self.error_count / self.total_requests * 100) if self.total_requests else 0

    @property
    def rps(self):
        return self.total_requests / self.duration_s if self.duration_s else 0

    def latency_p(self, pct):
        if not self.latencies:
            return 0
        sorted_l = sorted(self.latencies)
        idx = int(len(sorted_l) * pct / 100)
        return sorted_l[min(idx, len(sorted_l) - 1)]

    def fmt_ms(self, val):
        if val < 1:
            return f"{val*1000:.0f}ms"
        return f"{val:.1f}s"


# ── Helpers ──────────────────────────────────────────────────────────────────

def docker_stats_snapshot():
    """Capture memory from docker stats if available (works on EC2)."""
    try:
        out = subprocess.check_output(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}"],
            timeout=10, stderr=subprocess.DEVNULL
        ).decode().strip()
        return out
    except Exception:
        return None


async def authenticate(session: aiohttp.ClientSession, base_url: str,
                       email: str, password: str) -> str:
    """Login and return JWT token."""
    url = f"{base_url}/api/v1/auth/login"
    payload = {"email": email, "password": password}
    async with session.post(url, json=payload) as resp:
        if resp.status != 200:
            body = await resp.text()
            print(f"  Login failed ({resp.status}): {body}")
            sys.exit(1)
        data = await resp.json()
        return data["token"]


# ── Core request runners ─────────────────────────────────────────────────────

async def timed_request(session, method, url, headers=None, json_body=None,
                        timeout_s=30):
    """Execute a single request, return (status_code, latency_seconds)."""
    t0 = time.monotonic()
    try:
        async with session.request(
            method, url, headers=headers, json=json_body,
            timeout=aiohttp.ClientTimeout(total=timeout_s)
        ) as resp:
            await resp.read()
            return resp.status, time.monotonic() - t0
    except asyncio.TimeoutError:
        return 0, time.monotonic() - t0
    except Exception:
        return -1, time.monotonic() - t0


async def run_concurrency_level(session, method, url, concurrency, duration_s,
                                headers=None, json_body=None, timeout_s=30):
    """Fire requests at a given concurrency for a duration. Return PhaseResult."""
    result = PhaseResult(endpoint=url.split("/api")[-1] if "/api" in url else url.split("/")[-1],
                         concurrency=concurrency)
    stop = asyncio.Event()

    async def worker():
        while not stop.is_set():
            status, latency = await timed_request(
                session, method, url, headers=headers,
                json_body=json_body, timeout_s=timeout_s
            )
            result.total_requests += 1
            result.latencies.append(latency)
            result.status_counts[status] = result.status_counts.get(status, 0) + 1
            if 200 <= status < 300:
                result.successes += 1

    t0 = time.monotonic()
    tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
    await asyncio.sleep(duration_s)
    stop.set()
    await asyncio.gather(*tasks, return_exceptions=True)
    result.duration_s = time.monotonic() - t0

    return result


async def run_sse_request(session, url, timeout_s=120):
    """Consume an SSE stream until 'complete' or 'error' event. Return (status, latency)."""
    t0 = time.monotonic()
    try:
        async with session.get(
            url, timeout=aiohttp.ClientTimeout(total=timeout_s)
        ) as resp:
            if resp.status != 200:
                return resp.status, time.monotonic() - t0
            async for line in resp.content:
                text = line.decode("utf-8", errors="replace").strip()
                if text.startswith("event:"):
                    event_type = text[6:].strip()
                    if event_type in ("summary", "complete", "error"):
                        break
            return resp.status, time.monotonic() - t0
    except asyncio.TimeoutError:
        return 0, time.monotonic() - t0
    except Exception:
        return -1, time.monotonic() - t0


# ── Test phases ──────────────────────────────────────────────────────────────

async def phase_health(session, base_url):
    """Phase 1: Health endpoint — baseline throughput."""
    url = f"{base_url}/health"
    levels = [1, 10, 50, 100]
    duration = 30
    results = []

    print(f"\n{'='*60}")
    print(f"PHASE 1: Health Check  (GET /health)")
    print(f"  Concurrency ramp: {levels},  {duration}s per level")
    print(f"{'='*60}")

    for c in levels:
        print(f"\n  Concurrency={c} ...", end=" ", flush=True)
        r = await run_concurrency_level(session, "GET", url, c, duration)
        print(f"done — {r.rps:.1f} rps, p50={r.fmt_ms(r.latency_p(50))}, "
              f"p95={r.fmt_ms(r.latency_p(95))}, errors={r.error_pct:.1f}%")
        r.endpoint = "/health"
        results.append(r)

    return results


async def phase_auth(session, base_url, email, password):
    """Phase 2: Login endpoint — bcrypt CPU cost."""
    url = f"{base_url}/api/v1/auth/login"
    body = {"email": email, "password": password}
    levels = [1, 5, 10, 20]
    duration = 15
    results = []

    print(f"\n{'='*60}")
    print(f"PHASE 2: Auth Login  (POST /api/v1/auth/login)")
    print(f"  Concurrency ramp: {levels},  {duration}s per level")
    print(f"{'='*60}")

    for c in levels:
        print(f"\n  Concurrency={c} ...", end=" ", flush=True)
        r = await run_concurrency_level(
            session, "POST", url, c, duration, json_body=body
        )
        print(f"done — {r.rps:.1f} rps, p50={r.fmt_ms(r.latency_p(50))}, "
              f"p95={r.fmt_ms(r.latency_p(95))}, errors={r.error_pct:.1f}%")

        # Detect bottleneck
        if r.status_counts.get(429, 0) > 0:
            r.bottleneck = "Rate limit (429)"
        elif r.latency_p(95) > 1.0:
            r.bottleneck = "CPU (bcrypt)"

        r.endpoint = "/auth/login"
        results.append(r)

    return results


async def phase_presets(session, base_url, token):
    """Phase 3: Lightweight authenticated GET."""
    url = f"{base_url}/api/v1/payments/presets"
    headers = {"Authorization": f"Bearer {token}"}
    levels = [1, 10, 50]
    duration = 15
    results = []

    print(f"\n{'='*60}")
    print(f"PHASE 3: Presets  (GET /api/v1/payments/presets)")
    print(f"  Concurrency ramp: {levels},  {duration}s per level")
    print(f"{'='*60}")

    for c in levels:
        print(f"\n  Concurrency={c} ...", end=" ", flush=True)
        r = await run_concurrency_level(
            session, "GET", url, c, duration, headers=headers
        )
        print(f"done — {r.rps:.1f} rps, p50={r.fmt_ms(r.latency_p(50))}, "
              f"p95={r.fmt_ms(r.latency_p(95))}, errors={r.error_pct:.1f}%")

        if r.status_counts.get(429, 0) > 0:
            r.bottleneck = "Rate limit (429)"
        r.endpoint = "/presets"
        results.append(r)

    return results


def normalize_address(address: str) -> str:
    """Replicate backend's normalize_address to compute notes filenames."""
    normalized = address.lower()
    normalized = re.sub(r'\b([a-z]{2})(\d{5})\b', r'\1 \2', normalized)
    for abbrev, full in {
        r'\bpl\b': 'place', r'\bst\b': 'street', r'\bave\b': 'avenue',
        r'\bblvd\b': 'boulevard', r'\bdr\b': 'drive', r'\bln\b': 'lane',
        r'\brd\b': 'road', r'\bct\b': 'court',
    }.items():
        normalized = re.sub(abbrev, full, normalized)
    for full, abbrev in {
        r'\bnortheast\b': 'ne', r'\bnorthwest\b': 'nw',
        r'\bsoutheast\b': 'se', r'\bsouthwest\b': 'sw',
        r'\bnorth\b': 'n', r'\bsouth\b': 's',
        r'\beast\b': 'e', r'\bwest\b': 'w',
    }.items():
        normalized = re.sub(full, abbrev, normalized)
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', '_', normalized)
    normalized = re.sub(r'_+', '_', normalized).strip('_')
    return normalized


async def cleanup_test_reports(session, base_url, admin_password, addresses):
    """Delete cached reports for test addresses so next run isn't cached."""
    print(f"\n  Cleaning up {len(addresses)} cached test reports...")
    for addr in addresses:
        filename = normalize_address(addr)
        url = f"{base_url}/api/v1/admin/cached-reports/{quote(filename)}"
        try:
            async with session.delete(
                url, headers={"X-Admin-Password": admin_password}
            ) as resp:
                if resp.status == 200:
                    print(f"    Deleted: {filename}.md")
                elif resp.status == 404:
                    pass  # Not cached, nothing to clean
                else:
                    print(f"    Failed to delete {filename}: HTTP {resp.status}")
        except Exception as e:
            print(f"    Error deleting {filename}: {e}")


async def phase_analysis(session, base_url, token):
    """Phase 4: SSE analysis — memory ceiling, Chromium concurrency."""
    # Use distinct addresses so each request avoids the notes cache
    test_addresses = [
        "1600 Pennsylvania Ave NW Washington DC",
        "350 Fifth Avenue New York NY",
        "233 S Wacker Dr Chicago IL",
        "1 Infinite Loop Cupertino CA",
    ]
    levels = [1, 2, 3, 4]
    results = []

    print(f"\n{'='*60}")
    print(f"PHASE 4: Analysis Stream  (GET /api/v1/streaming/analyze/stream/...)")
    print(f"  Concurrency ramp: {levels},  wait for completion each level")
    print(f"  Addresses: {len(test_addresses)} distinct (no cache hits)")
    print(f"  WARNING: Each request costs credits!")
    print(f"{'='*60}")

    # Memory snapshot before
    mem_before = docker_stats_snapshot()
    if mem_before:
        print(f"\n  Docker stats BEFORE:")
        for line in mem_before.split("\n"):
            print(f"    {line}")

    for c in levels:
        print(f"\n  Concurrency={c} ...", end=" ", flush=True)
        t0 = time.monotonic()

        tasks = [
            asyncio.create_task(run_sse_request(
                session,
                f"{base_url}/api/v1/streaming/analyze/stream/{quote(test_addresses[i % len(test_addresses)])}?token={quote(token)}",
                timeout_s=300,
            ))
            for i in range(c)
        ]
        sse_results = await asyncio.gather(*tasks)
        elapsed = time.monotonic() - t0

        r = PhaseResult(endpoint="/analyze/stream", concurrency=c)
        r.duration_s = elapsed
        r.total_requests = c
        for status, latency in sse_results:
            r.latencies.append(latency)
            r.status_counts[status] = r.status_counts.get(status, 0) + 1
            if 200 <= status < 300:
                r.successes += 1

        if r.successes == c:
            r.bottleneck = "Memory (OK)"
        elif r.status_counts.get(503, 0) > 0:
            r.bottleneck = "503 (rejected)"
        elif r.status_counts.get(429, 0) > 0:
            r.bottleneck = "Rate limit (429)"
        elif r.status_counts.get(0, 0) > 0:
            r.bottleneck = "Timeout"
        else:
            r.bottleneck = f"Errors ({r.error_count})"

        rps_str = f"{r.rps:.2f}" if r.successes > 0 else "-"
        p50_str = r.fmt_ms(r.latency_p(50)) if r.latencies else "-"
        print(f"done — rps={rps_str}, p50={p50_str}, "
              f"errors={r.error_pct:.0f}%, bottleneck={r.bottleneck}")

        results.append(r)

        # Memory snapshot after each level
        mem_snap = docker_stats_snapshot()
        if mem_snap:
            print(f"  Docker stats AFTER concurrency={c}:")
            for line in mem_snap.split("\n"):
                print(f"    {line}")

        # If everything failed, no point testing higher concurrency
        if r.successes == 0:
            print(f"  All requests failed at concurrency={c}, stopping analysis phase.")
            break

    return results


# ── Summary ──────────────────────────────────────────────────────────────────

def print_summary(all_results):
    """Print final summary table."""
    print(f"\n\n{'='*80}")
    print(f"{'STRESS TEST RESULTS':^80}")
    print(f"{'='*80}")

    header = f"{'Endpoint':<20} {'Conc':>5} {'RPS':>8} {'p50':>8} {'p95':>8} {'p99':>8} {'Errors':>8} {'Bottleneck':<22}"
    print(header)
    print("-" * 80)

    for r in all_results:
        rps_str = f"{r.rps:.1f}" if r.successes > 0 else "-"
        p50 = r.fmt_ms(r.latency_p(50)) if r.latencies else "-"
        p95 = r.fmt_ms(r.latency_p(95)) if r.latencies else "-"
        p99 = r.fmt_ms(r.latency_p(99)) if r.latencies else "-"
        err = f"{r.error_pct:.1f}%"
        bn = r.bottleneck or "None"

        print(f"{r.endpoint:<20} {r.concurrency:>5} {rps_str:>8} {p50:>8} {p95:>8} {p99:>8} {err:>8} {bn:<22}")

        # Print status code breakdown if there are errors
        if r.error_count > 0:
            codes = ", ".join(f"{k}:{v}" for k, v in sorted(r.status_counts.items()))
            print(f"{'':>20} {'':>5} status codes: {codes}")

    print("-" * 80)

    # Docker memory snapshot
    mem = docker_stats_snapshot()
    if mem:
        print(f"\nDocker stats (current):")
        for line in mem.split("\n"):
            print(f"  {line}")

    print()


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(
        description="Perchspot stress test — measure QPS and find bottlenecks"
    )
    parser.add_argument("--target", required=True,
                        help="Base URL (e.g. https://perchspot.com or http://localhost:8000)")
    parser.add_argument("--email", required=True,
                        help="Account email for authenticated endpoints")
    parser.add_argument("--password", required=True,
                        help="Account password")
    parser.add_argument("--skip-analysis", action="store_true",
                        help="Skip the heavy SSE analysis phase (saves credits)")
    parser.add_argument("--only-analysis", action="store_true",
                        help="Only run the analysis phase (skip health, auth, presets)")
    parser.add_argument("--admin-password", default=None,
                        help="Admin password to clean up cached test reports (enables repeatable runs)")
    args = parser.parse_args()

    base_url = args.target.rstrip("/")
    is_external = "localhost" not in base_url and "127.0.0.1" not in base_url

    print(f"\nPerchspot Stress Test")
    print(f"  Target:   {base_url}")
    print(f"  Mode:     {'External (nginx rate limits apply)' if is_external else 'Internal (raw backend)'}")
    analysis_mode = "Only analysis" if args.only_analysis else ("Skipped" if args.skip_analysis else "Enabled (costs credits!)")
    print(f"  Analysis: {analysis_mode}")

    if is_external:
        print(f"\n  NOTE: Nginx rate limits will throttle results:")
        print(f"    General API:  60 req/min, burst 20")
        print(f"    Auth:         10 req/min, burst 5")
        print(f"    Analysis:      5 req/min, burst 2")
        print(f"    Connections:  20 concurrent per IP")

    # Remind about docker stats
    print(f"\n  TIP: Run this in a separate terminal on EC2 for live memory monitoring:")
    print(f"    watch -n 2 'docker stats --no-stream --format \"table {{{{.Name}}}}\\t{{{{.MemUsage}}}}\\t{{{{.CPUPerc}}}}\"'")

    # Initial docker stats
    mem = docker_stats_snapshot()
    if mem:
        print(f"\n  Docker stats (baseline):")
        for line in mem.split("\n"):
            print(f"    {line}")

    # Create session with connection pooling
    connector = aiohttp.TCPConnector(limit=200, limit_per_host=200)
    async with aiohttp.ClientSession(connector=connector) as session:

        # Authenticate
        print(f"\n  Authenticating as {args.email} ...")
        token = await authenticate(session, base_url, args.email, args.password)
        print(f"  Authenticated OK (token: {token[:20]}...)")

        all_results = []

        if not args.only_analysis:
            # Phase 1: Health
            all_results.extend(await phase_health(session, base_url))

            # Phase 2: Auth
            all_results.extend(await phase_auth(session, base_url, args.email, args.password))

            # Phase 3: Presets
            all_results.extend(await phase_presets(session, base_url, token))

        # Phase 4: Analysis (optional)
        if not args.skip_analysis:
            # Test addresses used by phase_analysis
            test_addresses = [
                "1600 Pennsylvania Ave NW Washington DC",
                "350 Fifth Avenue New York NY",
                "233 S Wacker Dr Chicago IL",
                "1 Infinite Loop Cupertino CA",
            ]
            # Clean up cached reports before running so we get real Chromium runs
            if args.admin_password:
                await cleanup_test_reports(session, base_url, args.admin_password, test_addresses)
            all_results.extend(await phase_analysis(session, base_url, token))
            # Clean up after so cached test data doesn't pollute the system
            if args.admin_password:
                await cleanup_test_reports(session, base_url, args.admin_password, test_addresses)
        else:
            print(f"\n{'='*60}")
            print(f"PHASE 4: Analysis Stream — SKIPPED (--skip-analysis)")
            print(f"{'='*60}")

        # Final summary
        print_summary(all_results)


if __name__ == "__main__":
    asyncio.run(main())
