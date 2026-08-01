#!/bin/sh
# =============================================================================
# Tor container entrypoint
# =============================================================================
# Renders torrc from the template, fixes volume ownership, publishes the public
# onion hostname to a shared volume, then execs tor.
#
# Two things are deliberate:
#   * Only the PUBLIC hostname is shared with the backend. The hidden-service
#     private key stays in this container's own volume.
#   * A missing control password is a hard failure, not a default. An
#     unauthenticated control port would let anything on the container network
#     reconfigure Tor, and silently starting one would be worse than not
#     starting at all.
# =============================================================================
set -eu

HS_DIR=/var/lib/tor/hidden_service
DATA_DIR=/var/lib/tor/data
SHARED_DIR=/var/lib/tor-shared
TORRC=/tmp/torrc

# ---------------------------------------------------------------------------
# Health check mode: the same signal the backend gates on.
# ---------------------------------------------------------------------------
if [ "${1:-}" = "healthcheck" ]; then
    # Ask Tor how far it has bootstrapped. Anything other than 100% means the
    # capability is not usable yet, so the container is not healthy yet.
    # A hostname that never appeared means the onion service is not published,
    # so the container is not healthy even if Tor itself bootstrapped fine.
    # Without this the publish failure is invisible: the backend just reports
    # no_onion_address with nothing pointing at the cause.
    if [ -f "${SHARED_DIR}/hostname.failed" ]; then
        echo "tor: hidden service hostname was never published" >&2
        exit 1
    fi
    # The marker above is only written after the publisher's 300s timeout, so on
    # its own it let a misconfigured HiddenServiceDir report HEALTHY for five
    # minutes: Tor bootstraps fine as a client, PROGRESS reaches 100, and the
    # pod goes Ready while the backend still has no onion address. Requiring the
    # published hostname makes readiness mean what it says from the first probe.
    # The probe budgets absorb the normal startup window (readiness 30s + 20x15s;
    # liveness does not even begin until 300s).
    if [ ! -s "${SHARED_DIR}/hostname" ]; then
        echo "tor: hidden service hostname is not published yet" >&2
        exit 1
    fi
    response=$(printf 'AUTHENTICATE "%s"\r\nGETINFO status/bootstrap-phase\r\nQUIT\r\n' \
        "${TOR_CONTROL_PASSWORD}" | nc 127.0.0.1 9051 2>/dev/null || true)
    echo "${response}" | grep -q "PROGRESS=100" || exit 1
    exit 0
fi

if [ -z "${TOR_CONTROL_PASSWORD:-}" ]; then
    echo "tor: TOR_CONTROL_PASSWORD is not set; refusing to start an unauthenticated control port" >&2
    exit 1
fi

if [ -z "${TOR_ONION_TARGET:-}" ]; then
    echo "tor: TOR_ONION_TARGET is not set (expected host:port of the onion ingress listener)" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Volume ownership and the privilege model, which differs by platform:
#
#   * docker-compose starts this as root, so we chown the volumes and let tor
#     drop to the `tor` user itself via the `User` directive.
#   * Kubernetes starts it as a non-root uid with fsGroup already owning the
#     volumes, so there is nothing to chown and no user to switch to. Emitting
#     `User tor` there would make tor fail at startup.
#
# Tor refuses to use a HiddenServiceDir that is group- or world-accessible, so
# the 0700 is set explicitly rather than inherited from the volume.
# ---------------------------------------------------------------------------
mkdir -p "${HS_DIR}" "${DATA_DIR}" "${SHARED_DIR}"
if [ "$(id -u)" = "0" ]; then
    chown -R tor:tor "${HS_DIR}" "${DATA_DIR}" "${SHARED_DIR}"
    user_directive="User tor"
else
    user_directive="# running as an unprivileged uid; no user switch needed"
fi
# Tor refuses a group- or world-accessible HiddenServiceDir, so 0700 is
# required, not cosmetic. In the normal path the mkdir above just created these
# as our own uid, so this succeeds. It can only fail when the volume already
# holds them owned by a DIFFERENT uid (a restored PVC, or a changed runAsUser):
# POSIX allows chmod only to the owner, and fsGroup adjusts group ownership,
# not the owner. Tor would then refuse to start anyway, so failing here is
# correct — but say why, because a bare chmod error explains nothing.
if ! chmod 0700 "${HS_DIR}" "${DATA_DIR}" 2>/dev/null; then
    echo "tor: cannot set 0700 on ${HS_DIR} / ${DATA_DIR}." >&2
    echo "tor: they exist owned by another uid (current uid $(id -u)); Tor" >&2
    echo "tor: requires 0700 on HiddenServiceDir. Fix the volume ownership" >&2
    echo "tor: (or keep runAsUser stable across deploys) and restart." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Render torrc.
#
# Set TOR_CONTROL_PASSWORD_HASH (output of `tor --hash-password` run
# elsewhere) to keep the plaintext off Tor's command line, where
# /proc/<pid>/cmdline exposes it for the duration of the call.
#
# Scope, stated honestly rather than overclaimed: TOR_CONTROL_PASSWORD is
# REQUIRED either way, because the health check above authenticates with it
# and AUTHENTICATE takes the plaintext, not the hash. So the secret is in this
# container's environment regardless, readable via /proc/<pid>/environ by the
# same processes that could read argv — everything here runs as the same
# unprivileged `tor` user. Using the hash removes one exposure of a secret
# that is still present; it does not remove the secret. Eliminating it
# entirely would mean cookie authentication, which cannot work for the
# Kubernetes backend pods that must authenticate across the network.
# tor has no stdin or environment option for --hash-password.
# ---------------------------------------------------------------------------
if [ -n "${TOR_CONTROL_PASSWORD_HASH:-}" ]; then
    hashed="${TOR_CONTROL_PASSWORD_HASH}"
else
    hashed=$(tor --hash-password "${TOR_CONTROL_PASSWORD}" 2>/dev/null | tail -n 1)
fi
if [ -z "${hashed}" ]; then
    echo "tor: failed to hash the control password" >&2
    exit 1
fi

sed -e "s|__HASHED_PASSWORD__|${hashed}|" \
    -e "s|__ONION_TARGET__|${TOR_ONION_TARGET}|" \
    -e "s|__USER_DIRECTIVE__|${user_directive}|" \
    /etc/tor/torrc.template > "${TORRC}"
if [ "$(id -u)" = "0" ]; then
    chown tor:tor "${TORRC}"
fi
chmod 0600 "${TORRC}"

# ---------------------------------------------------------------------------
# Publish the public hostname once Tor writes it, so the backend can learn the
# address it should expect in the Host header. Runs in the background because
# Tor creates the file during startup, after we exec it.
# ---------------------------------------------------------------------------
(
    # Clear any marker from a previous run before retrying.
    rm -f "${SHARED_DIR}/hostname.failed"
    # Drop the previous run's published address too. tor_shared is a PERSISTENT
    # volume, so if tor_data was recreated (new hidden-service key) this file
    # still holds the OLD address — and the healthcheck's -s test added last
    # round would pass on it, so the pod would go Ready while the backend
    # advertised an address Tor no longer serves. Removing it makes the window
    # before the new copy lands fail closed rather than fail WRONG.
    rm -f "${SHARED_DIR}/hostname"
    attempts=0
    while [ ! -s "${HS_DIR}/hostname" ]; do
        attempts=$((attempts + 1))
        if [ "${attempts}" -gt 300 ]; then
            echo "tor: hidden service hostname never appeared" >&2
            # exit only ends this subshell, so leave a marker the health check
            # inspects — otherwise the container stays "healthy" forever with
            # no onion address published.
            touch "${SHARED_DIR}/hostname.failed"
            exit 1
        fi
        sleep 1
    done
    # Atomic rename: the backend polls this file, and a partial read would
    # fail the address shape check and be discarded — correct, but noisy.
    #
    # Guarded as one unit, because `set -e` would otherwise abort the subshell
    # on a cp/mv/chmod failure BEFORE the marker was written — leaving the
    # container healthy with no hostname published, which is the exact
    # invisibility the marker exists to remove. The timeout path above was
    # covered; this path was not.
    if cp "${HS_DIR}/hostname" "${SHARED_DIR}/hostname.tmp" \
        && mv "${SHARED_DIR}/hostname.tmp" "${SHARED_DIR}/hostname" \
        && chmod 0644 "${SHARED_DIR}/hostname"; then
        echo "tor: onion service published"
    else
        echo "tor: failed to publish the onion hostname" >&2
        touch "${SHARED_DIR}/hostname.failed"
        exit 1
    fi
) &

# The image ends with `USER tor`, so this is already unprivileged: the uid check
# above took the non-root branch and torrc's `User` directive was rendered as a
# comment. Tor binds only high ports (SOCKS/control/the onion target), none of
# which need root.
exec tor -f "${TORRC}"
