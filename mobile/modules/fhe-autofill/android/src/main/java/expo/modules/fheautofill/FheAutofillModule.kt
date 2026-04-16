package expo.modules.fheautofill

import android.content.Context
import android.content.Intent
import android.provider.Settings
import android.view.autofill.AutofillManager
import expo.modules.kotlin.Promise
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.util.UUID

/**
 * FheAutofillModule — Kotlin side of the `fhe-autofill` Expo module.
 *
 * Responsibilities:
 *   - Expose Umbral primitives to the JS layer.
 *     The real cryptography lives in [UmbralBridge] (JNI-backed when
 *     available, pure-Java BBS98 fallback otherwise).
 *   - Stash "pending fill" plaintexts into [PendingFillStore] so that
 *     a subsequent focus event on the target app wakes up
 *     [FheAutofillService] which pulls the plaintext out and hands it
 *     to the platform autofill framework.
 *   - Expose settings helpers so the RN screen can deep-link into
 *     the Android autofill chooser.
 *
 * Threat model & invariants:
 *   - The plaintext never lives outside the single
 *     [PendingFillStore.Entry] byte array. The entry is consumed
 *     destructively by [FheAutofillService] and zeroed immediately.
 *   - The JS bridge never sees the plaintext when
 *     `options.sealedAutofill == true`; the module returns
 *     `{ autofilled: true, domain }` instead.
 */
class FheAutofillModule : Module() {

  override fun definition() = ModuleDefinition {
    Name("FheAutofill")

    AsyncFunction("isUmbralAvailable") {
      UmbralBridge.isAvailable()
    }

    AsyncFunction("generateKeyPair") { promise: Promise ->
      try {
        val pair = UmbralBridge.generateKeyPair()
        promise.resolve(mapOf(
          "public" to mapOf(
            "umbralPublicKey" to pair.publicKey,
            "umbralVerifyingKey" to pair.verifyingKey,
            "umbralSignerPublicKey" to pair.signerPublicKey,
          ),
          "secret" to mapOf(
            "sk" to pair.secretKey,
            "signerSk" to pair.signerSecretKey,
          )
        ))
      } catch (e: Throwable) {
        promise.reject("ERR_UMBRAL_KEYGEN", e.message ?: "keygen failed", e)
      }
    }

    AsyncFunction("decryptReencrypted") { payload: Map<String, Any?>, options: Map<String, Any?>, promise: Promise ->
      try {
        val plaintextBytes = UmbralBridge.decryptReencrypted(
          recipientSkB64 = payload["recipientSk"] as String,
          delegatingPkB64 = payload["delegatingPk"] as String,
          verifyingPkB64 = payload["verifyingPk"] as String,
          capsuleB64 = payload["capsule"] as String,
          cfragB64 = payload["cfrag"] as String,
          ciphertextB64 = payload["ciphertext"] as String,
        )
        val sealed = options["sealedAutofill"] == true
        if (sealed) {
          val id = PendingFillStore.put(
            plaintextBytes = plaintextBytes,
            packageHint = options["packageName"] as? String,
            domainHint = options["domain"] as? String,
          )
          promise.resolve(mapOf(
            "autofilled" to true,
            "id" to id,
            "domain" to (options["domain"] ?: ""),
          ))
        } else {
          val plaintext = String(plaintextBytes, Charsets.UTF_8)
          UmbralBridge.zeroize(plaintextBytes)
          promise.resolve(mapOf("plaintext" to plaintext))
        }
      } catch (e: Throwable) {
        promise.reject("ERR_UMBRAL_DECRYPT", e.message ?: "decrypt failed", e)
      }
    }

    AsyncFunction("storePendingFill") { payload: Map<String, Any?>, packageHint: String, promise: Promise ->
      try {
        val plaintextBytes = UmbralBridge.decryptReencrypted(
          recipientSkB64 = payload["recipientSk"] as String,
          delegatingPkB64 = payload["delegatingPk"] as String,
          verifyingPkB64 = payload["verifyingPk"] as String,
          capsuleB64 = payload["capsule"] as String,
          cfragB64 = payload["cfrag"] as String,
          ciphertextB64 = payload["ciphertext"] as String,
        )
        val id = PendingFillStore.put(plaintextBytes, packageHint, null)
        promise.resolve(mapOf("id" to id))
      } catch (e: Throwable) {
        promise.reject("ERR_UMBRAL_PENDING_FILL", e.message ?: "store failed", e)
      }
    }

    AsyncFunction("clearPendingFills") {
      PendingFillStore.clearAll()
      null
    }

    AsyncFunction("isSystemAutofillEnabled") {
      val ctx = appContext.reactContext ?: return@AsyncFunction false
      val mgr = ctx.getSystemService(AutofillManager::class.java) ?: return@AsyncFunction false
      mgr.hasEnabledAutofillServices()
    }

    AsyncFunction("openSystemAutofillSettings") { promise: Promise ->
      val ctx = appContext.reactContext
      if (ctx == null) {
        promise.reject("ERR_CONTEXT", "no reactContext", null)
        return@AsyncFunction
      }
      val intent = Intent(Settings.ACTION_REQUEST_SET_AUTOFILL_SERVICE).apply {
        data = android.net.Uri.parse("package:${ctx.packageName}")
        addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
      }
      try {
        ctx.startActivity(intent)
        promise.resolve(null)
      } catch (e: Throwable) {
        promise.reject("ERR_AUTOFILL_SETTINGS", e.message ?: "settings failed", e)
      }
    }
  }
}
