package expo.modules.fheautofill

import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

/**
 * In-memory store for decrypted plaintext awaiting pickup by
 * [FheAutofillService]. Entries:
 *   - carry a short TTL (default 120s) after which they self-expire.
 *   - are consumed destructively by [take] — the backing byte array
 *     is zeroed as soon as it is read so a second read sees zeros.
 *   - never touch disk; no SharedPreferences, no files, no cache.
 */
object PendingFillStore {
  private const val DEFAULT_TTL_MS = 120_000L

  data class Entry(
    val id: String,
    val plaintext: ByteArray,
    val packageHint: String?,
    val domainHint: String?,
    val expiresAt: Long,
  )

  private val entries = ConcurrentHashMap<String, Entry>()

  fun put(plaintextBytes: ByteArray, packageHint: String?, domainHint: String?): String {
    val id = UUID.randomUUID().toString()
    val entry = Entry(
      id = id,
      plaintext = plaintextBytes,
      packageHint = packageHint,
      domainHint = domainHint,
      expiresAt = System.currentTimeMillis() + DEFAULT_TTL_MS,
    )
    entries[id] = entry
    return id
  }

  /**
   * Find the freshest entry that matches the given autofill context.
   * Matching is best-effort: caller prefers packageName > domain.
   */
  fun takeMatching(packageName: String?, domain: String?): Entry? {
    expire()
    val now = System.currentTimeMillis()
    val candidates = entries.values
      .filter { it.expiresAt > now }
      .sortedByDescending { it.expiresAt }

    val byPackage = packageName?.let { pkg ->
      candidates.firstOrNull { it.packageHint == pkg }
    }
    if (byPackage != null) {
      entries.remove(byPackage.id)
      return byPackage
    }
    val byDomain = domain?.let { d ->
      candidates.firstOrNull { it.domainHint == d }
    }
    if (byDomain != null) {
      entries.remove(byDomain.id)
      return byDomain
    }
    val first = candidates.firstOrNull() ?: return null
    entries.remove(first.id)
    return first
  }

  fun clearAll() {
    for (e in entries.values) {
      e.plaintext.fill(0)
    }
    entries.clear()
  }

  private fun expire() {
    val now = System.currentTimeMillis()
    val expired = entries.values.filter { it.expiresAt <= now }
    for (e in expired) {
      e.plaintext.fill(0)
      entries.remove(e.id)
    }
  }
}
