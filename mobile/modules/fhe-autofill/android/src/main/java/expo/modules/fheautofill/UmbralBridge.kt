package expo.modules.fheautofill

import android.util.Base64
import java.security.SecureRandom

/**
 * UmbralBridge — Kotlin-facing façade over the Rust `umbral-pre`
 * crate.  When the JNI library `libumbral_pre_jni.so` is bundled
 * into the APK, we route the real implementations through it; in
 * its absence we throw [UmbralUnavailableException] so callers can
 * decide to fall back to the pure-JS path in the RN layer.
 *
 * Integrators wanting the production path should:
 *   - Vendor the pre-built `libumbral_pre_jni.so` for each ABI
 *     under `android/src/main/jniLibs/<abi>/`.
 *   - Ensure the JNI layer exposes the four `native` functions
 *     declared at the bottom of this file.
 *
 * Until then, the bridge defaults to "unavailable".
 */
object UmbralBridge {
  data class KeyPair(
    val publicKey: String,
    val verifyingKey: String,
    val signerPublicKey: String,
    val secretKey: String,
    val signerSecretKey: String,
  )

  class UmbralUnavailableException(message: String) : RuntimeException(message)

  private val nativeAvailable: Boolean = try {
    System.loadLibrary("umbral_pre_jni")
    true
  } catch (_: Throwable) {
    false
  }

  fun isAvailable(): Boolean = nativeAvailable

  fun generateKeyPair(): KeyPair {
    if (!nativeAvailable) {
      throw UmbralUnavailableException("libumbral_pre_jni.so not bundled")
    }
    val raw = nativeGenerateKeyPair()
    require(raw.size == 5) { "unexpected JNI response shape" }
    return KeyPair(
      publicKey = b64url(raw[0]),
      verifyingKey = b64url(raw[1]),
      signerPublicKey = b64url(raw[2]),
      secretKey = b64url(raw[3]),
      signerSecretKey = b64url(raw[4]),
    )
  }

  fun decryptReencrypted(
    recipientSkB64: String,
    delegatingPkB64: String,
    verifyingPkB64: String,
    capsuleB64: String,
    cfragB64: String,
    ciphertextB64: String,
  ): ByteArray {
    if (!nativeAvailable) {
      throw UmbralUnavailableException("libumbral_pre_jni.so not bundled")
    }
    return nativeDecryptReencrypted(
      b64urlDecode(recipientSkB64),
      b64urlDecode(delegatingPkB64),
      b64urlDecode(verifyingPkB64),
      b64urlDecode(capsuleB64),
      b64urlDecode(cfragB64),
      b64urlDecode(ciphertextB64),
    )
  }

  fun zeroize(bytes: ByteArray) {
    bytes.fill(0)
  }

  private fun b64url(bytes: ByteArray): String =
    Base64.encodeToString(bytes, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)

  private fun b64urlDecode(s: String): ByteArray =
    Base64.decode(s, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)

  // JNI bindings. Implementations live in Rust; see
  // `password_manager/fhe_sharing/SPEC.md` for the expected ABI.
  @JvmStatic private external fun nativeGenerateKeyPair(): Array<ByteArray>
  @JvmStatic private external fun nativeDecryptReencrypted(
    recipientSk: ByteArray,
    delegatingPk: ByteArray,
    verifyingPk: ByteArray,
    capsule: ByteArray,
    cfrag: ByteArray,
    ciphertext: ByteArray,
  ): ByteArray
}
