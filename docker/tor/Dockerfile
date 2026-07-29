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

# tor — the daemon itself. It creates the `tor` user and drops privileges on
# its own via the `User` directive in torrc; busybox supplies the `nc` the
# health check uses.
RUN apk add --no-cache tor

COPY docker/tor/torrc.template /etc/tor/torrc.template
COPY docker/tor/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

# The SOCKS port (client egress, used by the loopback self-check) and the
# control port (read-only state queries). Neither is published to the host in
# docker-compose; both stay on the internal network.
EXPOSE 9050 9051

# Bootstrap can take a while on a cold start, so the health check is generous.
# `GETINFO status/bootstrap-phase` over the control port is the same signal the
# backend gates on, so a healthy container means a usable capability.
HEALTHCHECK --interval=15s --timeout=10s --start-period=180s --retries=10 \
    CMD /usr/local/bin/entrypoint.sh healthcheck

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
