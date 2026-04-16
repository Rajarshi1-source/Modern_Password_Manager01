package expo.modules.fheautofill

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumentation tests for [PendingFillStore].  These run on a
 * device/emulator so they prove that the in-memory store behaves
 * correctly under the Android runtime.
 */
@RunWith(AndroidJUnit4::class)
class PendingFillStoreTest {

  @Before
  fun clear() {
    PendingFillStore.clearAll()
  }

  @Test
  fun putAndTakeByPackage() {
    val plaintext = "correct horse battery staple".toByteArray(Charsets.UTF_8)
    val id = PendingFillStore.put(plaintext, packageHint = "com.example.app", domainHint = null)
    assertNotNull(id)

    val entry = PendingFillStore.takeMatching("com.example.app", null)
    assertNotNull(entry)
    assertEquals(id, entry!!.id)
    // The returned ByteArray IS the stored buffer — caller must
    // zero it after use. Before zeroing, it should still carry the
    // plaintext bytes.
    assertArrayEquals("correct horse battery staple".toByteArray(Charsets.UTF_8), entry.plaintext)
  }

  @Test
  fun takeConsumesEntry() {
    val plaintext = "secret".toByteArray(Charsets.UTF_8)
    PendingFillStore.put(plaintext, "com.example.app", null)

    val first = PendingFillStore.takeMatching("com.example.app", null)
    assertNotNull(first)
    val second = PendingFillStore.takeMatching("com.example.app", null)
    assertNull(second)
  }

  @Test
  fun domainFallbackWhenPackageMismatches() {
    val plaintext = "pw".toByteArray(Charsets.UTF_8)
    PendingFillStore.put(plaintext, packageHint = null, domainHint = "example.com")

    val entry = PendingFillStore.takeMatching("com.other.app", "example.com")
    assertNotNull(entry)
    assertEquals("example.com", entry!!.domainHint)
  }

  @Test
  fun clearAllZeroesPlaintext() {
    val plaintext = "secret".toByteArray(Charsets.UTF_8)
    PendingFillStore.put(plaintext, "com.example.app", null)
    PendingFillStore.clearAll()
    // Reference still holds the backing array; it should now be zeros.
    assertTrue(plaintext.all { it == 0.toByte() })
  }
}
