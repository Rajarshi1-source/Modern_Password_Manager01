/**
 * Browser-local credential wallet using IndexedDB.
 *
 * We deliberately avoid the `idb` dependency to keep the wallet self-contained
 * and auditable. The DB holds:
 *   - dids:     { did, publicKeyMultibase, privateKeyHex (encrypted), isPrimary }
 *   - creds:    { id, jwt, jsonld }
 */

const DB_NAME = 'securevault.did.wallet.v1';
const DB_VERSION = 1;
const STORES = ['dids', 'creds'];

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      for (const name of STORES) {
        if (!db.objectStoreNames.contains(name)) {
          db.createObjectStore(name, { keyPath: 'id' });
        }
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx(store, mode, fn) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const t = db.transaction(store, mode);
    const s = t.objectStore(store);
    const result = fn(s);
    t.oncomplete = () => resolve(result);
    t.onerror = () => reject(t.error);
    t.onabort = () => reject(t.error);
  });
}

export async function saveDid(entry) {
  await tx('dids', 'readwrite', (s) => {
    s.put({ id: entry.did, ...entry });
  });
}

export async function listDids() {
  return tx('dids', 'readonly', (s) =>
    new Promise((resolve) => {
      const out = [];
      const cursor = s.openCursor();
      cursor.onsuccess = (e) => {
        const c = e.target.result;
        if (c) { out.push(c.value); c.continue(); } else { resolve(out); }
      };
    })
  );
}

export async function deleteDid(did) {
  await tx('dids', 'readwrite', (s) => s.delete(did));
}

export async function saveCredential(credId, jwt, jsonld) {
  await tx('creds', 'readwrite', (s) => {
    s.put({ id: credId, jwt, jsonld, savedAt: new Date().toISOString() });
  });
}

export async function listCredentials() {
  return tx('creds', 'readonly', (s) =>
    new Promise((resolve) => {
      const out = [];
      const cursor = s.openCursor();
      cursor.onsuccess = (e) => {
        const c = e.target.result;
        if (c) { out.push(c.value); c.continue(); } else { resolve(out); }
      };
    })
  );
}

export async function deleteCredential(credId) {
  await tx('creds', 'readwrite', (s) => s.delete(credId));
}

/**
 * Export the wallet as a JSON blob for backup. The caller is responsible for
 * re-encrypting the payload if the user provides a passphrase.
 */
export async function exportWallet() {
  const [dids, creds] = await Promise.all([listDids(), listCredentials()]);
  return { dids, creds, exportedAt: new Date().toISOString() };
}

export async function importWallet(blob) {
  if (!blob || !Array.isArray(blob.dids) || !Array.isArray(blob.creds)) {
    throw new Error('Invalid wallet blob');
  }
  for (const d of blob.dids) await saveDid(d);
  for (const c of blob.creds) await saveCredential(c.id, c.jwt, c.jsonld);
}
