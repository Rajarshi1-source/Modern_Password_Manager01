# =============================================================================
# Tor daemon — publishes the backend as a v3 onion service
# =============================================================================
# This container is what makes Dark Protocol's anonymity claim true rather than
# decorative: it publishes an onion service so clients reach the backend over a
# circuit that terminates inside Tor (no exit node), and it exposes a control
# port so the backend can VERIFY that state instead of assuming it.
#
# Opt-in. `docker compose up` does not start it; `docker compose --profile tor
# up` does. Without it the feature reports Unavailable, which is the honest
# answer for a deployment that has no anonymity transport.
# =============================================================================

FROM alpine:3.21

# tor — the daemon itself. Two busybox applets from the base image are also
# load-bearing, so neither is incidental if this base ever changes: `nc`, which
# the health check pipes its control-port query through, and `nslookup`, which
# the entrypoint uses to resolve TOR_ONION_TARGET to an IP (HiddenServicePort
# does not accept a DNS name). Alpine's busybox builds both; it does NOT build
# `getent`, which is why the entrypoint uses nslookup for that lookup.
RUN apk add --no-cache tor

COPY docker/tor/torrc.template /etc/tor/torrc.template
COPY docker/tor/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# Pre-create the volume mount points owned by `tor`, with the 0700 that Tor
# demands of a HiddenServiceDir. Docker seeds a fresh named volume from the
# image's directory ownership, so the container never needs root to fix
# permissions — which is what lets it run entirely as an unprivileged user
# below (Trivy DS-0002 / Semgrep missing-user-entrypoint).
#
# This seeding only happens once, when the named volume is first created --
# Docker never re-applies it to a volume that already has content. So it
# only reaches an EXISTING tor_data volume that was previously populated by
# a root-owned container (entrypoint.sh's `id -u = 0` branch is a supported,
# if non-default, fallback). If that ever applies to a real deployment,
# either `chown -R tor:tor` the volume's contents once, or accept a fresh
# .onion address by recreating the volume — this image cannot fix ownership
# on its own once it is running as `tor`.
RUN mkdir -p /var/lib/tor/data /var/lib/tor/hidden_service /var/lib/tor-shared \
    && chown -R tor:tor /var/lib/tor /var/lib/tor-shared \
    && chmod 0700 /var/lib/tor/data /var/lib/tor/hidden_service \
    && chmod 0755 /var/lib/tor-shared

# The SOCKS port (client egress, used by the loopback self-check) and the
# control port (read-only state queries). Neither is published to the host in
# docker-compose; both stay on the internal network.
EXPOSE 9050 9051

# Bootstrap can take a while on a cold start, so the health check is generous.
# `GETINFO status/bootstrap-phase` over the control port is the same signal the
# backend gates on, so a healthy container means a usable capability.
HEALTHCHECK --interval=15s --timeout=10s --start-period=180s --retries=10 \
    CMD /usr/local/bin/entrypoint.sh healthcheck

# Never root. The entrypoint already branches on uid and skips the chown that
# is unnecessary here, and torrc omits its `User` directive when it is not
# root, so the daemon runs as this user throughout.
USER tor

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
