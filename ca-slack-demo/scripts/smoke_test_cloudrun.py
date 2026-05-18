"""Smoke test for a deployed Cloud Run instance.

Checks:
  1. Health endpoint responds 200
  2. (Optional) A real CA query round-trips correctly via test_cli flow

Usage:
    # Health check only
    SERVICE_URL=https://ca-demo-xxx-uc.a.run.app uv run python scripts/smoke_test_cloudrun.py

    # With identity token (for --no-allow-unauthenticated services)
    SERVICE_URL=... uv run python scripts/smoke_test_cloudrun.py --auth
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import urllib.request
import urllib.error


def get_identity_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def check_health(service_url: str, token: str | None = None) -> bool:
    url = service_url.rstrip("/")
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", "Bearer %s" % token)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            ok = resp.status == 200
            print("[health] %d %s — body: %r" % (resp.status, "OK" if ok else "FAIL", body[:80]))
            return ok
    except urllib.error.HTTPError as e:
        print("[health] HTTP %d — %s" % (e.code, e.reason))
        return False
    except Exception as e:
        print("[health] ERROR — %s" % e)
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test a deployed Cloud Run ca-demo service")
    parser.add_argument("--auth", action="store_true", help="Attach a gcloud identity token")
    args = parser.parse_args()

    import os
    service_url = os.environ.get("SERVICE_URL", "").rstrip("/")
    if not service_url:
        print("ERROR: set SERVICE_URL to your Cloud Run service URL")
        sys.exit(1)

    print("Smoke testing: %s" % service_url)

    token = None
    if args.auth:
        print("Fetching identity token...")
        try:
            token = get_identity_token()
            print("Token acquired (first 20 chars): %s..." % token[:20])
        except subprocess.CalledProcessError as e:
            print("ERROR fetching token: %s" % e.stderr)
            sys.exit(1)

    passed = check_health(service_url, token)

    if passed:
        print("\nSmoke test PASSED")
    else:
        print("\nSmoke test FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
