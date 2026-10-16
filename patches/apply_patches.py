#!/usr/bin/env python3
"""Build-time patches applied to the hermes-agent source inside the Docker image
(run from Dockerfile.append against /opt/hermes).

Each patch replaces an exact anchor. If an anchor is missing (upstream changed or fixed the
code), the patch is SKIPPED with a warning instead of failing the deploy — check the workflow
log after every submodule bump.

Usage: python3 patches/apply_patches.py /opt/hermes   (or a local hermes-agent checkout)
"""
import pathlib
import sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "hermes-agent")

PATCHES = [
    {
        # Satellite-profile cron delivery (e.g. family WhatsApp reminders routed through the
        # default profile's WhatsApp via gateway.profile_routes) fails with
        # "platform 'whatsapp' not configured/enabled" once the satellite profile's adapter map
        # holds only a NON-messaging adapter (Platform.LOCAL session adapter, created for local /
        # cron agent sessions). The map is then truthy, so the SharedRouteAdapters fallback is
        # skipped. Treat a map with no messaging adapters as empty.
        "name": "cron-satellite-ignore-non-messaging-adapters",
        "file": "cron/scheduler_provider.py",
        "old": (
            "            tick_adapters = (profile_adapters or {}).get(profile_name) or {}\n"
            "            if not tick_adapters and adapters:\n"
        ),
        "new": (
            "            tick_adapters = (profile_adapters or {}).get(profile_name) or {}\n"
            "            # fly-hermes patch: LOCAL/api_server/webhook adapters cannot carry a messaging\n"
            "            # delivery; a map holding only those must still ride the routed primary.\n"
            "            _fh_messaging = [\n"
            "                p for p in tick_adapters\n"
            "                if str(getattr(p, 'value', p)).lower() not in ('local', 'api_server', 'webhook')\n"
            "            ]\n"
            "            if not _fh_messaging and adapters:\n"
        ),
    },
]


def main() -> int:
    applied = skipped = 0
    for patch in PATCHES:
        path = ROOT / patch["file"]
        text = path.read_text(encoding="utf-8")
        if patch["new"] in text:
            print(f"[patch] {patch['name']}: already applied")
            continue
        count = text.count(patch["old"])
        if count != 1:
            print(f"::warning::[patch] {patch['name']}: anchor found {count}x in {patch['file']} — SKIPPED "
                  "(upstream changed; re-check whether the bug is fixed)")
            skipped += 1
            continue
        path.write_text(text.replace(patch["old"], patch["new"]), encoding="utf-8")
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
        print(f"[patch] {patch['name']}: applied to {patch['file']}")
        applied += 1
    print(f"[patch] done: {applied} applied, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
