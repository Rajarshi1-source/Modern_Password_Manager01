#!/usr/bin/env python3
"""
Behavioural smoke test for the crypto / TLS dependency stack.

Why this exists: `pip` resolution and `pip check` only compare version
metadata. They cannot see that a release removed an API another package still
calls. This script exercises the primitives and the transitive consumers the
application relies on, at whatever versions are installed, so a bump of
cryptography / pyOpenSSL / Twisted / fido2 / PyJWT / ... fails here in about a
minute instead of surfacing in production.

What it covers
  * cryptography primitives cross-checked against independent implementations
    (hashlib, pycryptodome) and RFC test vectors -- so data written by an older
    version must still decrypt/verify byte-for-byte.
  * A real TLS handshake with hostname verification through Twisted's `ssl:`
    endpoint (the form `daphne -e ssl:...` uses), and Scrapy's pyOpenSSL context.
  * JOSE / JWT / WebAuthn (COSE) / NTLM paths that sit on cryptography.

What it deliberately does NOT cover: application logic. The Django test suite
remains the authority for that; this is a fast tripwire for library breakage.

Known limitations are registered in KNOWN_BROKEN, not hidden: each is run and
reported. A known-broken check that starts passing prints XPASS (so the
caveat can be removed); a NEW failure exits non-zero.

Packages that are not installed are SKIPped, so the script also runs locally.
"""
import base64
import datetime
import hashlib
import importlib.util
import os
import sys
import tempfile
import warnings
from importlib import metadata

KEY_PACKAGES = (
    "cryptography", "pyOpenSSL", "fido2", "PyJWT", "Twisted", "daphne",
    "autobahn", "Scrapy", "service-identity", "josepy", "Authlib",
    "pyspnego", "requests-ntlm", "pycryptodome",
)


def _have(*modules):
    """True when every named top-level module can be imported."""
    return all(importlib.util.find_spec(m) is not None for m in modules)


# name -> reason. These are real incompatibilities in APIs this project does not
# call; see the cryptography block in password_manager/requirements.txt.
KNOWN_BROKEN = {
    "Twisted KeyPair.selfSignedCert": (
        "Twisted still calls OpenSSL.crypto.X509Req, removed in pyOpenSSL 26.3.0 "
        "(needed for cryptography>=49). Unused: daphne/scrapy/autobahn only load PEM files."
    ),
    "Twisted CertificateRequest": "same X509Req removal as above",
}
# A KNOWN_BROKEN check is only XFAIL when it fails for the documented reason;
# any other exception (a new breakage) must still fail the run.
KNOWN_BROKEN_SIGNATURE = "X509Req"

CHECKS = []


def check(name, requires=()):
    """Register a check; it is SKIPped if any of `requires` is not installed."""
    def deco(fn):
        CHECKS.append((name, tuple(requires), fn))
        return fn
    return deco


# --------------------------------------------------------------- primitives
@check("PBKDF2-HMAC-SHA256 == hashlib", ["cryptography"])
def _pbkdf2():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    pw, salt = b"correct horse", b"saltsaltsalt1234"
    assert PBKDF2HMAC(hashes.SHA256(), 32, salt, 600000).derive(pw) == \
        hashlib.pbkdf2_hmac("sha256", pw, salt, 600000, 32)


@check("Scrypt == hashlib.scrypt", ["cryptography"])
def _scrypt():
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    pw, salt = b"correct horse", b"saltsaltsalt1234"
    assert Scrypt(salt, 32, 2 ** 14, 8, 1).derive(pw) == \
        hashlib.scrypt(pw, salt=salt, n=2 ** 14, r=8, p=1, dklen=32)


@check("HKDF RFC 5869 test case 1", ["cryptography"])
def _hkdf():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    out = HKDF(hashes.SHA256(), 42, bytes.fromhex("000102030405060708090a0b0c"),
               bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")).derive(bytes.fromhex("0b" * 22))
    assert out.hex() == ("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56"
                         "ecc4c5bf34007208d5b887185865")


@check("AES-GCM and ChaCha20-Poly1305 == pycryptodome", ["cryptography", "Crypto"])
def _aead():
    from Crypto.Cipher import AES, ChaCha20_Poly1305
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM, ChaCha20Poly1305
    key, nonce, aad, pt = bytes(range(32)), bytes(range(12)), b"hdr", b"vault item plaintext" * 5
    ct = AESGCM(key).encrypt(nonce, pt, aad)
    c = AES.new(key, AES.MODE_GCM, nonce=nonce)
    c.update(aad)
    body, tag = c.encrypt_and_digest(pt)
    assert ct == body + tag, "AES-GCM output differs from pycryptodome"
    p = ChaCha20_Poly1305.new(key=key, nonce=nonce)
    p.update(aad)
    b2, t2 = p.encrypt_and_digest(pt)
    assert ChaCha20Poly1305(key).encrypt(nonce, pt, aad) == b2 + t2, "ChaCha20-Poly1305 differs"
    try:
        AESGCM(key).decrypt(nonce, ct[:-1] + bytes([ct[-1] ^ 1]), aad)
    except InvalidTag:
        return
    raise AssertionError("tampered ciphertext was accepted")


@check("Cipher(AES, GCM) with default_backend() (low-level path)", ["cryptography"])
def _lowlevel_gcm():
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key, nonce, aad, pt = bytes(range(32)), bytes(range(12)), b"hdr", b"x" * 40
    enc = Cipher(algorithms.AES(key), modes.GCM(nonce), backend=default_backend()).encryptor()
    enc.authenticate_additional_data(aad)
    out = enc.update(pt) + enc.finalize()
    assert out + enc.tag == AESGCM(key).encrypt(nonce, pt, aad)


@check("Ed25519 RFC 8032 + X25519 RFC 7748 + ECDH", ["cryptography"])
def _asymmetric():
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, x25519
    sk = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"))
    sig = sk.sign(b"")
    assert sig.hex() == ("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e0652249"
                         "01555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
    sk.public_key().verify(sig, b"")
    try:
        sk.public_key().verify(sig, b"x")
        raise AssertionError("tampered message verified")
    except InvalidSignature:
        pass
    a = x25519.X25519PrivateKey.from_private_bytes(bytes.fromhex(
        "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"))
    b = x25519.X25519PublicKey.from_public_bytes(bytes.fromhex(
        "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f"))
    assert a.exchange(b).hex() == "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742"
    e1, e2 = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    point = e1.public_key().public_bytes(serialization.Encoding.X962,
                                         serialization.PublicFormat.UncompressedPoint)
    peer = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point)
    assert e2.exchange(ec.ECDH(), peer) == e1.exchange(ec.ECDH(), e2.public_key())


@check("Fernet round-trip and InvalidToken", ["cryptography"])
def _fernet():
    from cryptography.fernet import Fernet, InvalidToken
    f = Fernet(base64.urlsafe_b64encode(bytes(range(32))))
    tok = f.encrypt_at_time(b"hello", current_time=1700000000)
    assert f.decrypt(tok) == b"hello"
    try:
        f.decrypt(tok[:-2] + b"AA")
    except InvalidToken:
        return
    raise AssertionError("corrupted token was accepted")


# ---------------------------------------------------------------- TLS stack
def _self_signed_pem(directory):
    """Write k.pem / c.pem (self-signed, SAN localhost) using cryptography's supported API."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(65537, 2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .sign(key, hashes.SHA256()))
    with open(os.path.join(directory, "k.pem"), "wb") as fh:
        fh.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                   serialization.NoEncryption()))
    with open(os.path.join(directory, "c.pem"), "wb") as fh:
        fh.write(cert.public_bytes(serialization.Encoding.PEM))
    return key


@check("TLS handshake + hostname verification via Twisted ssl: endpoint (Daphne path)",
       ["cryptography", "OpenSSL", "twisted", "service_identity"])
def _twisted_loopback():
    from twisted.internet import endpoints, protocol, reactor, ssl
    workdir = tempfile.mkdtemp()
    _self_signed_pem(workdir)
    previous = os.getcwd()
    os.chdir(workdir)  # relative names: Twisted's endpoint syntax treats ':' (C:\...) as a separator
    out = {}

    class Echo(protocol.Protocol):
        def dataReceived(self, data):
            self.transport.write(data)

    class Client(protocol.Protocol):
        def connectionMade(self):
            self.transport.write(b"ping")

        def dataReceived(self, data):
            out["echo"] = data
            out["cn"] = self.transport.getPeerCertificate().get_subject().CN
            self.transport.loseConnection()
            reactor.stop()

    def fail(failure):
        out.setdefault("error", failure.getErrorMessage())
        reactor.stop()

    def connect(listening):
        trust = ssl.Certificate.loadPEM(open("c.pem", "rb").read())
        opts = ssl.optionsForClientTLS("localhost", trustRoot=trust)
        endpoints.SSL4ClientEndpoint(reactor, "127.0.0.1", listening.getHost().port, opts) \
            .connect(protocol.ClientFactory.forProtocol(Client)).addErrback(fail)

    try:
        endpoints.serverFromString(
            reactor, "ssl:port=0:privateKey=k.pem:certKey=c.pem:interface=127.0.0.1"
        ).listen(protocol.Factory.forProtocol(Echo)).addCallbacks(connect, fail)
        reactor.callLater(20, lambda: (out.setdefault("error", "timed out"), reactor.stop()))
        reactor.run()
    finally:
        os.chdir(previous)
    assert out.get("echo") == b"ping", out
    assert out.get("cn") == "localhost", out


@check("Scrapy ScrapyClientContextFactory builds a pyOpenSSL context",
       ["OpenSSL", "twisted", "scrapy"])
def _scrapy_context():
    from OpenSSL import SSL
    from scrapy.core.downloader.contextfactory import ScrapyClientContextFactory
    assert isinstance(ScrapyClientContextFactory().getContext(), SSL.Context)


@check("Twisted CertificateOptions from PEM", ["cryptography", "OpenSSL", "twisted"])
def _twisted_options():
    from twisted.internet import ssl
    workdir = tempfile.mkdtemp()
    _self_signed_pem(workdir)
    pem = open(os.path.join(workdir, "k.pem"), "rb").read() + open(os.path.join(workdir, "c.pem"), "rb").read()
    assert ssl.PrivateCertificate.loadPEM(pem).options().getContext() is not None


@check("Twisted KeyPair.selfSignedCert", ["OpenSSL", "twisted"])
def _twisted_selfsigned():
    from twisted.internet import ssl
    ssl.KeyPair.generate(size=2048).selfSignedCert(1, CN="localhost")


@check("Twisted CertificateRequest", ["OpenSSL", "twisted"])
def _twisted_request():
    from twisted.internet import ssl
    ssl.KeyPair.generate(size=2048).requestObject(ssl.DN(CN="localhost"))


@check("autobahn.twisted.websocket and daphne.server import", ["autobahn", "daphne", "twisted"])
def _imports():
    import autobahn.twisted.websocket  # noqa: F401
    import daphne.server  # noqa: F401


# --------------------------------------------------------------- JOSE & co.
@check("josepy RS256 sign/verify", ["josepy", "cryptography"])
def _josepy():
    import josepy
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = josepy.JWKRSA(key=rsa.generate_private_key(65537, 2048))
    assert josepy.JWS.sign(b"payload", key=key, alg=josepy.RS256).verify(key.public_key())


@check("Authlib RS256 JWT", ["authlib", "cryptography"])
def _authlib():
    from authlib.jose import JsonWebKey, jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    pem = rsa.generate_private_key(65537, 2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    key = JsonWebKey.import_key(pem)
    assert jwt.decode(jwt.encode({"alg": "RS256"}, {"sub": "u"}, key), key)["sub"] == "u"


@check("PyJWT RS256 and RSAAlgorithm.from_jwk (the OIDC service path)", ["jwt", "cryptography"])
def _pyjwt():
    import jwt
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from jwt.algorithms import RSAAlgorithm
    key = rsa.generate_private_key(65537, 2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    token = jwt.encode({"sub": "u"}, pem, algorithm="RS256")
    assert jwt.decode(token, key.public_key(), algorithms=["RS256"])["sub"] == "u"
    assert RSAAlgorithm.from_jwk(RSAAlgorithm.to_jwk(key.public_key()))


@check("fido2 ES256 COSE key verifies a cryptography signature", ["fido2", "cryptography"])
def _fido2():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from fido2.cose import ES256
    key = ec.generate_private_key(ec.SECP256R1())
    ES256.from_cryptography_key(key.public_key()).verify(
        b"m", key.sign(b"m", ec.ECDSA(hashes.SHA256())))


@check("ARC4 available for NTLM, and pyspnego builds a negotiate token",
       ["cryptography", "spnego"])
def _ntlm():
    import spnego
    from cryptography.hazmat.decrepit.ciphers.algorithms import ARC4
    from cryptography.hazmat.primitives.ciphers import Cipher
    assert Cipher(ARC4(b"k" * 16), mode=None).encryptor().update(b"abc")
    token = spnego.client("user", "pw", protocol="ntlm").step()
    assert token and token.startswith(b"NTLMSSP")


# ------------------------------------------------------------------- runner
def main():
    """Run every check; return the process exit code."""
    warnings.simplefilter("ignore")
    print("Installed versions:")
    for dist in KEY_PACKAGES:
        try:
            print(f"  {dist:<18} {metadata.version(dist)}")
        except metadata.PackageNotFoundError:
            print(f"  {dist:<18} (not installed)")
    print()
    unexpected, counts = [], {"PASS": 0, "SKIP": 0, "XFAIL": 0, "XPASS": 0}
    for name, requires, fn in CHECKS:
        missing = [m for m in requires if not _have(m)]
        if missing:
            counts["SKIP"] += 1
            print(f"SKIP  {name} (not installed: {', '.join(missing)})")
            continue
        known = next((why for key, why in KNOWN_BROKEN.items() if name.startswith(key)), None)
        try:
            fn()
        except Exception as exc:  # noqa: BLE001 - report every failure kind
            detail = f"{type(exc).__name__}: {str(exc)[:140]}"
            if known and KNOWN_BROKEN_SIGNATURE in str(exc):
                counts["XFAIL"] += 1
                print(f"XFAIL {name}\n        known: {known}\n        got:   {detail}")
            else:
                unexpected.append(name)
                print(f"FAIL  {name}\n        {detail}")
        else:
            if known:
                counts["XPASS"] += 1
                print(f"XPASS {name} -- known limitation no longer reproduces; remove it from KNOWN_BROKEN")
            else:
                counts["PASS"] += 1
                print(f"PASS  {name}")
    print("\n" + ", ".join(f"{v} {k}" for k, v in counts.items()) + f", {len(unexpected)} FAILED")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
