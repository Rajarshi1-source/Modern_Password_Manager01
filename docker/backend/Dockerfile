# =============================================================================
# Backend Dockerfile - Django Password Manager API
# =============================================================================
# Multi-stage build with Post-Quantum Crypto (liboqs)
# Supports: Django REST API, Celery Workers, Daphne WebSockets, FHE Operations
# =============================================================================

# Post-quantum pins (see the crypto-builder stage and DEPENDENCY_POLICY.md →
# "Post-quantum cryptography"). Declared before the first FROM so the
# production stage's smoke test asserts the same versions the build used.
ARG LIBOQS_REF=0.16.0
ARG LIBOQS_COMMIT=5a1a854b0dc9f2141bdc771c555ee60c37950183
ARG LIBOQSPY_REF=0.16.0.1
ARG LIBOQSPY_COMMIT=62385cd99ababa2a4875257232c68dccda256e3b

# -----------------------------------------------------------------------------
# Stage 1: Crypto Builder - Compile liboqs and Python crypto libraries
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS crypto-builder

ENV DEBIAN_FRONTEND=noninteractive

# Install system build tools required for liboqs and crypto libraries.
# `apt-get -y upgrade` pulls patched curl + util-linux to address Trivy
# CVEs #1393, #1396, #1399-#1403; without it the image inherits whatever
# was frozen into the python:3.12-slim-bookworm base.
RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    curl \
    pkg-config \
    openssl \
    libssl-dev \
    libgmp-dev \
    python3-dev \
    libffi-dev \
    libssh2-1 \
    libgnutls30 \
    libcurl4 \
    libxml2 \
    libsystemd0 \
    libcap2 \
    libkrb5-3 \
    libc6 \
    zlib1g \
    util-linux \
    tar \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Build and install liboqs (Open Quantum Safe C library)
#
# Pinning policy (see DEPENDENCY_POLICY.md → "Post-quantum cryptography"):
#   liboqs C library  → 0.16.0   (this stage, SHA 5a1a854b…)
#   liboqs-python     → 0.16.0.1 (next stage,  SHA 62385cd9…)
# Drift between the two halves manifests as runtime ABI breaks (the C
# library's symbol layout shifts and the Python wrapper's ctypes bindings
# silently mis-cast: 0.16's OQS_KEM struct gained length_keypair_seed and
# keypair_derand, which 0.10's wrapper does not know). Both pins must move
# together when bumped, and the production stage's oqs_smoke.py fails the
# build if they do not match.
#
# Belt-and-suspenders: we clone by tag (fast, --depth 1) AND assert the
# commit SHA matches a known-good value before building. Git release
# tags on this project have not been retargeted historically, but if
# upstream ever moves a tag (or a malicious actor pushes a tag rewrite
# to a mirror) the SHA assertion fails closed — the docker build aborts
# rather than silently shipping a different commit. Per CodeRabbit
# review of PR #274. SHAs verified via ``git ls-remote --tags`` against
# the canonical github.com upstream on 2026-10-19 (0.16.0 is the latest
# liboqs release; no 0.17.0 yet).
#
# OQS_MINIMAL_BUILD limits the compiled algorithms to what the Python
# code actually instantiates: FIPS 203 ML-KEM-{512,768,1024} for all new
# data, plus round-3 Kyber{512,768,1024}, kept so data written with
# Kyber768 before the ML-KEM migration still decrypts (the two are not
# interoperable) and for LatticeCryptoEngine configs naming kyber-*. No
# signature scheme is compiled in, so the LMS/XMSS advisories against
# 0.16.0 (CVE-2026-104254/-104255, fixed in 0.17.0) do not apply to this
# build. Saber, NTRU, and Dilithium were enabled previously but have zero
# call sites. Extend the list (and oqs_smoke.py) if a future feature
# introduces a new algorithm.
#
# OQS_DIST_BUILD=ON + OQS_OPT_TARGET=auto give a "distribution build"
# with runtime CPUID dispatch — production hosts on x86_64 with AVX2 or
# arm64 with NEON pick up the SIMD-optimised Kyber polynomial-multiplication
# path; hosts without those extensions transparently fall back to the
# portable constant-time implementation. This is the user-space hot-path
# optimisation lever; see DEPENDENCY_POLICY.md for why kernel/FPGA/GPU
# offload is explicitly out of scope.
# -----------------------------------------------------------------------------
ARG LIBOQS_REF
ARG LIBOQS_COMMIT
WORKDIR /tmp
RUN git clone --depth 1 --branch ${LIBOQS_REF} https://github.com/open-quantum-safe/liboqs.git && \
    actual=$(git -C liboqs rev-parse HEAD) && \
    if [ "$actual" != "${LIBOQS_COMMIT}" ]; then \
        echo "ERROR: liboqs ${LIBOQS_REF} resolved to $actual, expected ${LIBOQS_COMMIT}." >&2 ; \
        echo "Upstream tag may have been retargeted. Refusing to build." >&2 ; \
        exit 1 ; \
    fi && \
    mkdir -p liboqs/build
WORKDIR /tmp/liboqs/build
RUN cmake -GNinja .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON \
    -DOQS_USE_OPENSSL=ON \
    -DOQS_MINIMAL_BUILD="KEM_ml_kem_512;KEM_ml_kem_768;KEM_ml_kem_1024;KEM_kyber_512;KEM_kyber_768;KEM_kyber_1024" \
    -DOQS_DIST_BUILD=ON \
    -DOQS_OPT_TARGET=auto \
    && ninja \
    && ninja install

# Set library path for liboqs
ENV LD_LIBRARY_PATH="/usr/local/lib"
ENV PKG_CONFIG_PATH="/usr/local/lib/pkgconfig"

# -----------------------------------------------------------------------------
# Install liboqs-python wrapper.
#
# Pinned to 0.16.0.1 to pair with liboqs 0.16.0 above (0.16.0.1 also fixes
# a command injection in the wrapper's automatic liboqs installation). The
# build once cloned `main` HEAD, which produced reproducibility drift: the
# same Dockerfile could yield different wrapper versions across builds, and
# requirements-lock.txt's line lied about what was actually installed. The
# tag pin makes the Docker build and the lock file agree.
#
# Installed with --target so the package's .dist-info travels with it into
# the venv: 0.16 reads its own version from that metadata at import time,
# and without it warns and skips its C/Python version check.
#
# SHA assertion mirrors the liboqs stage above — clone by tag, then
# verify the commit hash hasn't drifted (per CodeRabbit review of PR
# #274).
# -----------------------------------------------------------------------------
ARG LIBOQSPY_REF
ARG LIBOQSPY_COMMIT
WORKDIR /tmp
RUN git clone --depth 1 --branch ${LIBOQSPY_REF} https://github.com/open-quantum-safe/liboqs-python.git && \
    actual=$(git -C liboqs-python rev-parse HEAD) && \
    if [ "$actual" != "${LIBOQSPY_COMMIT}" ]; then \
        echo "ERROR: liboqs-python ${LIBOQSPY_REF} resolved to $actual, expected ${LIBOQSPY_COMMIT}." >&2 ; \
        echo "Upstream tag may have been retargeted. Refusing to build." >&2 ; \
        exit 1 ; \
    fi
WORKDIR /tmp/liboqs-python
RUN pip install --no-cache-dir --no-deps --target /opt/oqs-python .
WORKDIR /tmp
RUN rm -rf liboqs-python

# pqcrypto and concrete-python (FHE) used to be pip-installed here. Both
# went into this stage's system Python, which the production stage never
# copies (it takes only /opt/oqs-python and the liboqs .so files), so neither
# ever reached the shipped image. concrete-python==2.5.0 also has no cp312
# wheel, and the `|| echo` hid that failure on every build. kyber_crypto's
# pqcrypto fallback (dead in the image for that reason) has been removed, so
# liboqs is the only real KEM backend. The FHE service falls back to plaintext scoring when
# `concrete.fhe` is missing. Shipping real FHE is tracked separately: every
# current concrete-python (2.9-2.11) requires numpy<2, needs setuptools<81
# for pkg_resources, and needs a linker at runtime to compile circuits.

# -----------------------------------------------------------------------------
# Stage 2: Dependencies Builder - Install Python dependencies
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS deps-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RESOLVER_BACKTRACK_LIMIT=200000

# Install build dependencies for Python packages. `apt-get -y upgrade`
# patches curl / util-linux in the builder layer (Trivy #1393, #1396,
# #1399-#1403) so any tooling that links against them has the fixed
# versions.
RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    cmake \
    clang \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    libgmp-dev \
    libmpfr-dev \
    libomp-dev \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    zlib1g-dev \
    git \
    libssh2-1 \
    libgnutls30 \
    libcurl4 \
    libxml2 \
    libsystemd0 \
    libcap2 \
    libkrb5-3 \
    libc6 \
    util-linux \
    tar \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements (split into layers) and install Python dependencies.
#
# Notes on the staged install:
# * Layer 1 (core) is the Django/web stack and is REQUIRED for the image to
#   boot. Failure here aborts the build.
# * Layer 2 (ml) is large (multi-GB) and OPTIONAL on space-constrained
#   runners. If installation fails (typically due to disk exhaustion on
#   GHA hosted runners) the build continues — the app has fallback paths.
# * Layer 3 (servers) is small and ensures gunicorn/daphne/uvicorn are
#   present even if the ml layer was skipped.
#
# General pip flags:
# * pip is pinned to a version known to handle large dependency graphs
#   without "resolution-too-deep" errors against unbounded specifiers.
# * `--prefer-binary` forces pip to pick a wheel whenever one exists
#   (avoids multi-hour source builds under qemu for scipy, torch, etc.).
# * `--retries` cushions transient PyPI timeouts.
WORKDIR /app
COPY password_manager/requirements-core.txt .
COPY password_manager/requirements-ml.txt .

# setuptools is upper-bounded at <82 because neurokit2 0.2.13 and
# torch 2.12.0+cpu both declare ``setuptools<82``. Letting pip upgrade
# past that ceiling produces a noisy "dependency conflict" line in the
# CI log (it does not currently break the build, but a future pip
# version may promote it to a hard failure).
RUN pip install --upgrade "pip>=25.0" "setuptools>=78.1.1,<82" "wheel>=0.46.2" && \
    pip install --prefer-binary --retries 5 -r requirements-core.txt

# Mandatory: the backend cannot start without this layer. auth_module/urls.py
# imports mfa_views, which imports numpy at module level, and numpy (like
# OpenCV/Pillow/SciPy) comes only from requirements-ml.txt. A core-only image
# fails URLconf loading on every request, so a failed ML install must fail
# the build instead of shipping that image (it used to be `|| echo` warned).
RUN pip install --prefer-binary --retries 5 -r requirements-ml.txt

RUN pip install --prefer-binary --retries 5 \
    gunicorn daphne "uvicorn[standard]" redis django-redis

# Copy the liboqs-python package AND its .dist-info from crypto-builder into
# the venv (see the --target install above).
COPY --from=crypto-builder /opt/oqs-python /tmp/oqs-staging
RUN PY_SITELIB=$(python -c "import sysconfig; print(sysconfig.get_path('purelib'))") && \
    cp -r /tmp/oqs-staging/. "$PY_SITELIB/" && \
    rm -rf /tmp/oqs-staging

# -----------------------------------------------------------------------------
# Stage 3: Production - Final optimized image
# -----------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    DJANGO_SETTINGS_MODULE=password_manager.settings \
    PATH="/opt/venv/bin:$PATH" \
    LD_LIBRARY_PATH="/usr/local/lib" \
    # Application settings
    APP_HOME=/app \
    APP_USER=appuser \
    APP_GROUP=appgroup

# Install runtime dependencies including crypto runtime libraries.
# `curl` is intentionally NOT installed in the runtime stage — the
# HEALTHCHECK below uses python's stdlib urllib instead. Dropping curl
# closes Trivy CVEs #1399-#1403 (curl/libcurl) at the layer level
# rather than only patching them. `apt-get -y upgrade` patches the
# remaining transitive packages (util-linux: Trivy #1393, #1396).
#
# The explicit security-package list forces apt to resolve patched
# versions from bookworm-security for the CVEs flagged by Trivy:
# libssh2 (#1694), libgnutls30 (#1667/#1668/#1670/#1672/#1673),
# libcurl4 (#1649-#1666 — needed by other deps even though curl bin
# is not installed), libncurses6 (#1479/#1499/#1531/#1533),
# libxml2 (#1515), libsystemd0 (#1489/#1501), libcap2 (#1439),
# libkrb5 (#1680-#1687), libc6/glibc (#1656-#1659),
# zlib1g (#1548), util-linux (#1544/#1547), tar (#1541).
# libxcb1/libgl1/libglib2.0-0: OpenCV runtime. mediapipe depends on
# opencv-contrib-python (the GUI build), whose cv2 needs them even headless;
# without them `import cv2` and mediapipe fail with "libxcb.so.1: cannot open
# shared object file" and the biometric/liveness paths silently fall back.
RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat-openbsd \
    libgmp10 \
    libmpfr6 \
    libomp5 \
    libssl3 \
    libgomp1 \
    libssh2-1 \
    libgnutls30 \
    libcurl4 \
    libncurses6 \
    libxml2 \
    libsystemd0 \
    libcap2 \
    libkrb5-3 \
    libgssapi-krb5-2 \
    libc6 \
    zlib1g \
    util-linux \
    tar \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd --gid 1000 ${APP_GROUP} && \
    useradd --uid 1000 --gid ${APP_GROUP} --shell /bin/bash --create-home ${APP_USER}

# Copy liboqs shared libraries and headers from crypto-builder
COPY --from=crypto-builder /usr/local/lib/liboqs.so* /usr/local/lib/
COPY --from=crypto-builder /usr/local/include/oqs /usr/local/include/oqs

# Copy virtual environment from deps-builder
COPY --from=deps-builder /opt/venv /opt/venv

# Strip example/test private keys shipped by third-party packages (e.g.
# autobahn's wamp/cryptosign.py:165 example key that Trivy flagged as
# #1559/#1560 "Asymmetric Private Key"). Vendor ``test``/``tests``/``testing``
# DIRECTORIES are deliberately NOT removed wholesale: several are runtime
# packages that get imported at startup -- django/test (needed by
# rest_framework_simplejwt), torch/testing, numpy/testing, absl/testing,
# web3/testing -- and deleting them left an image that could not start Django.
# A Trivy secret scan of the venv with them intact reports nothing beyond the
# autobahn cryptosign pair handled below. Also drop
# the system-site pip (24.0 in the base image, Trivy #1550/#1551/#1761) —
# the application uses the /opt/venv interpreter so the system pip is dead
# weight. Finally upgrade any system-site stale wheels (python-dotenv 1.0.0,
# Trivy #1556) by removing them so only the venv's pinned version remains.
#
# autobahn.wamp.cryptosign:
#   We use Django Channels' ASGI dispatcher, not WAMP cryptosign auth, so the
#   ``cryptosign`` modules are dead code in our image. Removing them
#   eliminates Trivy #1559/#1560 (documentation-purpose Ed25519 key in
#   cryptosign.py:165 mis-detected as a real secret). Also remove the compiled
#   __pycache__ entry so Trivy's secret scan doesn't re-fire on the .pyc copy.
#   Do NOT remove the whole ``autobahn/wamp`` package: since autobahn 26.x,
#   ``autobahn/websocket/interfaces.py`` imports ``autobahn.wamp.types``
#   unconditionally, so without it ``import daphne.server`` raises
#   ModuleNotFoundError and Django cannot start. The import check below fails
#   the build if that ever happens again.
RUN find /opt/venv -type f \( -name "*.example.pem" -o -name "*-example.pem" -o -name "example_key*.pem" \) -delete && \
    /opt/venv/bin/python -m pip install --no-cache-dir --upgrade "pip>=25.0" "setuptools>=78.1.1,<82" "wheel>=0.46.2" && \
    # autobahn 25.12.2 ships cryptosign code at two locations:
    # ``autobahn/wamp/cryptosign.py`` AND ``autobahn/twisted/cryptosign.py``
    # (with their compiled __pycache__/*.pyc siblings). Both contain the
    # documentation-purpose Ed25519 keypair that Trivy flags as a
    # secret. We don't use WAMP cryptosign auth in either subpackage, so
    # ``-delete`` every cryptosign source/bytecode file anywhere under
    # ``autobahn/``. The rest of ``autobahn/wamp`` stays: autobahn imports
    # it at load time (see the comment above the RUN). The guard below
    # matches the same pattern, so any future relocation the strip misses
    # is caught loudly.
    find /opt/venv -type f -path "*/autobahn/*cryptosign*.py*" -delete && \
    # Fail the build if any cryptosign file survived the strip — without this
    # guard, a future autobahn upgrade that reorganises the package layout
    # would silently re-introduce Trivy #1559/#1560 (the example Ed25519
    # private key in autobahn.wamp.cryptosign) without us noticing until a
    # subsequent scan ran. A loud failure here is better than a quiet
    # regression of a documented zero-knowledge-adjacent finding.
    if find /opt/venv -type f -path "*/autobahn/*cryptosign*.py*" -print -quit | grep -q .; then \
        echo "ERROR: autobahn cryptosign artefacts survived strip — Trivy #1559/#1560 will re-fire." >&2; \
        find /opt/venv -type f -path "*/autobahn/*cryptosign*.py*" -print >&2; \
        exit 1; \
    fi && \
    # The strip must not break what the app imports at startup. Nothing in CI
    # ever RAN this image, so removing autobahn/wamp and the test directories
    # wholesale shipped an image whose Django could not start. Import the two
    # packages that were hit (daphne -> autobahn.wamp, simplejwt -> django.test.signals).
    /opt/venv/bin/python -c "import autobahn.twisted.websocket, daphne.server, django.test.signals" && \
    # ``|| true`` sits INSIDE the braces, on the rm itself, so it ONLY swallows
    # a missing system-site path. The earlier links in the && chain -- pip
    # upgrade, the cryptosign guard and the startup import check -- must
    # fail the build. Writing ``{ rm ...; } || true`` instead does NOT confine
    # the ``||`` to the group: ``&&`` and ``||`` have equal precedence and are
    # left-associative, so it applies to the WHOLE chain before it and a
    # failed import check would still leave the build green.
    { rm -rf /usr/lib/python3*/dist-packages/python_dotenv* \
             /usr/local/lib/python3*/dist-packages/python_dotenv* \
             /usr/lib/python3*/dist-packages/pip \
             /usr/lib/python3*/dist-packages/pip-* \
             /usr/local/lib/python3*/dist-packages/pip \
             /usr/local/lib/python3*/dist-packages/pip-* \
             /usr/lib/python3*/dist-packages/wheel-* \
             /usr/local/lib/python3*/dist-packages/wheel-* \
             /usr/lib/python3*/dist-packages/jaraco* \
             /usr/local/lib/python3*/dist-packages/jaraco* \
             /usr/lib/python3*/dist-packages/urllib3-2.6* \
             /usr/local/lib/python3*/dist-packages/urllib3-2.6* 2>/dev/null || true; }

# Update library cache after all native libs and venv are in place
RUN ldconfig

# Post-quantum smoke test, at build time, in the shipped venv: liboqs loads,
# the C and Python halves are the pinned versions, exactly the
# OQS_MINIMAL_BUILD KEMs are enabled, every one of them round-trips, and
# Kyber768 and ML-KEM-768 do not interoperate. CI builds this image but
# never runs it (PR #545), so this is where a broken pairing must fail.
ARG LIBOQS_REF
ARG LIBOQSPY_REF
COPY docker/backend/oqs_smoke.py /tmp/oqs_smoke.py
RUN /opt/venv/bin/python -I /tmp/oqs_smoke.py "${LIBOQS_REF}" "${LIBOQSPY_REF}" && \
    rm -f /tmp/oqs_smoke.py

# Set working directory
WORKDIR ${APP_HOME}

# Copy application code
COPY --chown=${APP_USER}:${APP_GROUP} password_manager/ .

# Create necessary directories
RUN mkdir -p \
    ${APP_HOME}/staticfiles \
    ${APP_HOME}/media \
    ${APP_HOME}/logs \
    ${APP_HOME}/geoip \
    && chown -R ${APP_USER}:${APP_GROUP} ${APP_HOME}

# Copy entrypoint script
COPY --chown=${APP_USER}:${APP_GROUP} docker/backend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to non-root user
USER 1000:1000

# Expose ports
# 8000 - Gunicorn (REST API)
# 8001 - Daphne (WebSockets)
EXPOSE 8000 8001

# Health check — uses python stdlib urllib instead of curl so the
# runtime image doesn't need to ship curl (see Trivy CVEs #1399-#1403).
# urllib.request.urlopen raises on non-2xx responses, which gives the
# right non-zero exit code for the orchestrator to mark the container
# unhealthy.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health/', timeout=8).status == 200 else 1)" || exit 1

# Default entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# Default command (can be overridden)
CMD ["daphne", \
    "-b", "0.0.0.0", \
    "-p", "8000", \
    "--websocket_timeout", "300", \
    "password_manager.asgi:application"]
