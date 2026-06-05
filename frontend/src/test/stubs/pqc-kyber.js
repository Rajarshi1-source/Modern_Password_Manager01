/**
 * Test stub for the `pqc-kyber` package.
 *
 * The real `pqc-kyber` is a wasm-bindgen module whose package.json declares no
 * resolvable entry point (no `main`/`module`/`exports`), so Vite cannot resolve
 * the dynamic `import('pqc-kyber')` inside `kyberService._loadKyberModule()` and
 * any test that imports kyberService fails to collect. `vitest.config.js` aliases
 * `pqc-kyber` to this file so the unit tests exercise kyberService's real hybrid
 * (Kyber + X25519) logic without the broken WASM package.
 *
 * It implements the flat pqc-kyber surface the service adapts — `keypair()`,
 * `encapsulate(pk)`, `decapsulate(ct, sk)` — with the genuine Kyber-768 byte
 * sizes. The first 32 bytes of the public and secret keys share a random seed;
 * encapsulate XORs the shared secret with that seed and decapsulate recovers it.
 * This yields correct round-trips and genuine rejection under a wrong key, which
 * is all the kyberService unit tests assert. It is NOT cryptographically secure
 * and must never be used outside tests.
 */

const PUBLIC_KEY_SIZE = 1184;
const SECRET_KEY_SIZE = 2400;
const CIPHERTEXT_SIZE = 1088;
const SHARED_SECRET_SIZE = 32;

const randomBytes = (n) => {
  const a = new Uint8Array(n);
  globalThis.crypto.getRandomValues(a);
  return a;
};

export const keypair = () => {
  const seed = randomBytes(SHARED_SECRET_SIZE);
  const pubkey = randomBytes(PUBLIC_KEY_SIZE);
  const secret = randomBytes(SECRET_KEY_SIZE);
  // Embed the same seed at the front of both keys so decapsulate (which only
  // sees the secret key) can reconstruct what encapsulate derived from the
  // public key.
  pubkey.set(seed, 0);
  secret.set(seed, 0);
  return { pubkey, secret };
};

export const encapsulate = (pk) => {
  const sharedSecret = randomBytes(SHARED_SECRET_SIZE);
  const ciphertext = randomBytes(CIPHERTEXT_SIZE);
  for (let i = 0; i < SHARED_SECRET_SIZE; i++) {
    ciphertext[i] = sharedSecret[i] ^ pk[i];
  }
  return { ciphertext, sharedSecret };
};

export const decapsulate = (ct, sk) => {
  const sharedSecret = new Uint8Array(SHARED_SECRET_SIZE);
  for (let i = 0; i < SHARED_SECRET_SIZE; i++) {
    sharedSecret[i] = ct[i] ^ sk[i];
  }
  return sharedSecret;
};

export default { keypair, encapsulate, decapsulate };
