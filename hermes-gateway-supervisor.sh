#!/bin/sh
# Supervises multiple Hermes gateway processes inside one Fly Machine.
#
# The base image only exec's a single CMD (one gateway = one profile). This
# script instead launches one gateway per profile listed in
# $HERMES_GATEWAY_PROFILES (space-separated; "default" means the primary
# profile / plain `hermes gateway run` with no -p flag) and restarts any
# child that exits, so a crash in one profile's gateway (e.g. a WhatsApp
# bridge hiccup) doesn't take the others down and doesn't need a full
# Machine restart to recover.
#
# SIGTERM/SIGINT are forwarded to all children so `fly apps restart` /
# deploys still shut down cleanly.

set -u

PROFILES="${HERMES_GATEWAY_PROFILES:-default}"
RESTART_DELAY="${HERMES_GATEWAY_RESTART_DELAY:-5}"

child_pids=""

term_handler() {
    echo "[supervisor] received signal, forwarding to children: $child_pids"
    for pid in $child_pids; do
        kill -TERM "$pid" 2>/dev/null
    done
    wait
    exit 0
}
trap term_handler TERM INT

run_profile() {
    profile="$1"
    while true; do
        if [ "$profile" = "default" ]; then
            echo "[supervisor] starting gateway: default profile"
            /opt/hermes/.venv/bin/hermes gateway run
        else
            echo "[supervisor] starting gateway: profile=$profile"
            /opt/hermes/.venv/bin/hermes -p "$profile" gateway run
        fi
        code=$?
        echo "[supervisor] gateway (profile=$profile) exited with code $code, restarting in ${RESTART_DELAY}s"
        sleep "$RESTART_DELAY"
    done
}

for profile in $PROFILES; do
    run_profile "$profile" &
    child_pids="$child_pids $!"
done

echo "[supervisor] running profiles: $PROFILES (pids:$child_pids)"
wait
