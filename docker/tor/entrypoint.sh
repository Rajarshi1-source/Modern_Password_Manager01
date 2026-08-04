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
    # Tor's control protocol reads this as a QuotedString, where `\` and `"`
    # must be escaped (backslash FIRST, or the escapes we add get re-escaped).
    # Unescaped, a password containing `"` closes the string early and the
    # command is malformed, while `\b` is read as a literal `b` — so the
    # health check fails against a Tor that is bootstrapped and serving, the
    # pod never goes Ready, and the feature reports Unavailable while the
    # onion service works. `tor --hash-password` takes the plaintext on argv
    # and is unaffected, which is what makes the mismatch confusing.
    # A base64 secret (the documented `openssl rand -base64 32`) contains
    # neither character, so this changes nothing on the documented path.
    escaped_password=$(printf '%s' "${TOR_CONTROL_PASSWORD}" \
        | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g')
    response=$(printf 'AUTHENTICATE "%s"\r\nGETINFO status/bootstrap-phase\r\nQUIT\r\n' \
        "${escaped_password}" | nc 127.0.0.1 9051 2>/dev/null || true)
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
# Tor's HiddenServicePort target must be an IP address (or a unix socket) --
# it does not resolve hostnames itself, so writing the compose/k8s service
# name straight into torrc (backend-onion:8443 / backend-onion-service:8443)
# fails Tor's own config parser before it ever binds. Resolve it once here,
# with busybox nslookup (the base alpine image ships it; getent is not built
# into Alpine's busybox). This is not a security check -- unlike the
# request-path peer resolution in tor_service.py, a stale answer here just
# means a connection failure the onion self-check already surfaces as
# Unavailable -- so there is nothing to gain from re-resolving per connection.
# It does mean the resolved address must stay valid for the life of this
# container; restart it if the backend service's address changes underneath
# it.
# ---------------------------------------------------------------------------
onion_target_host="${TOR_ONION_TARGET%:*}"
onion_target_port="${TOR_ONION_TARGET##*:}"
case "${onion_target_host}" in
    \[*\]|*[!0-9.]*)
        # A bracketed IPv6 literal is already in the form HiddenServicePort
        # wants, so pass it straight through; anything else non-IPv4 is a name
        # to resolve. (nslookup would do a REVERSE lookup on an IP argument,
        # so literals must never reach the resolver.)
        case "${onion_target_host}" in
            \[*\]) resolved_host="${onion_target_host}" ;;
            *)
                nslookup_out=$(nslookup "${onion_target_host}" 2>/dev/null)
                # Take the address from the ANSWER section only. busybox
                # nslookup prints the resolver's own "Address:" line FIRST,
                # before any "Name:" line, so keying off "Name:" is what keeps
                # the DNS server's address from being mistaken for the answer
                # -- pointing the onion service at kube-dns would be far worse
                # than failing outright.
                #
                # Prefer IPv4: on a dual-stack cluster the answer may include
                # an AAAA record, and a bare IPv6 address is NOT valid here --
                # HiddenServicePort requires the bracketed [addr]:port form, so
                # an unbracketed one fails Tor's config parser and the
                # container never starts. Bracket it when it is all we have.
                #
                # `addr = $NF` below is not a bug: it has been raised and
                # re-verified as a false positive multiple times, on the claim
                # that busybox can print an answer line as
                # "Address 1: <ip> <hostname>" (numbered, trailing hostname),
                # which would make $NF the hostname instead of the address.
                # Fetched this image's ACTUAL busybox source (alpine:3.21,
                # busybox 1.37.0): FEATURE_NSLOOKUP_BIG is compiled in, and
                # that mode's answer-line printf is exactly
                # "Name:\t%s\nAddress: %s\n" -- never numbered, never a
                # trailing hostname. The numbered/hostname format only exists
                # under `#if !ENABLE_FEATURE_NSLOOKUP_BIG`, which this image
                # does not compile. If the base image or its busybox package
                # ever changes, re-verify against the ACTUAL compiled source
                # before "fixing" this.
                resolved_host=$(printf '%s\n' "${nslookup_out}" | awk '
                    /^Name:/ { in_answer = 1 }
                    in_answer && /^Address/ {
                        addr = $NF
                        if (addr ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/) { v4 = addr; exit }
                        if (v6 == "") v6 = addr
                    }
                    END { if (v4 != "") print v4; else if (v6 != "") print "[" v6 "]" }
                ')
                if [ -z "${resolved_host}" ]; then
                    echo "tor: could not resolve TOR_ONION_TARGET host '${onion_target_host}'" >&2
                    exit 1
                fi
                ;;
        esac
        ;;
    *)
        resolved_host="${onion_target_host}"
        ;;
esac
TOR_ONION_TARGET="${resolved_host}:${onion_target_port}"

# ---------------------------------------------------------------------------
# Volume ownership and the privilege model.
#
# The shipped image ends with `USER tor` (docker/tor/Dockerfile), so on both
# platforms this container starts already unprivileged: `id -u` is never 0
# here, chown is skipped, and torrc's `User` directive renders as a comment
# (Tor is already running as `tor`; the directive is for starting as root).
# The `id -u = 0` branch below is a FALLBACK, not a live path in this image --
# kept for a custom build that starts as root instead, where it chowns the
# volumes and lets Tor drop to `tor` itself via that directive.
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
# `tor --hash-password`'s own output can never contain these, so this only
# ever rejects an operator-supplied TOR_CONTROL_PASSWORD_HASH. `|` breaks the
# sed expression below (it is the delimiter); `&` and `\` are sed replacement
# metacharacters that would corrupt the substituted value instead of erroring
# -- silently producing a torrc nobody intended, from a typo in a Secret.
case "${hashed}" in
    *'|'*|*'&'*|*'\'*)
        echo "tor: TOR_CONTROL_PASSWORD_HASH contains a character (|, &, or \\) that would corrupt the generated torrc" >&2
        exit 1
        ;;
esac
# A pattern glob can't rule out an embedded newline (it matches anything,
# newline included), so check separately: one would inject an extra torrc
# directive after the substitution.
if [ "$(printf '%s' "${hashed}" | wc -l)" -ne 0 ]; then
    echo "tor: TOR_CONTROL_PASSWORD_HASH must not contain a newline" >&2
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
