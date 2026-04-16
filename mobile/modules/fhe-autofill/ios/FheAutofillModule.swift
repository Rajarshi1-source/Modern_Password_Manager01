import ExpoModulesCore
import Foundation

/// FheAutofillModule — iOS side of the `fhe-autofill` Expo module.
///
/// Responsibilities:
///   * Expose Umbral primitives (`generateKeyPair`, `decryptReencrypted`)
///     so the RN layer can fall back to the same API surface as
///     Android.  The real cryptography is routed through
///     ``UmbralFFI`` which wraps the Rust `umbral-pre` crate
///     compiled as a static library (`libumbral_pre.a`).
///   * Stash decrypted plaintext into the App Group container under
///     an ephemeral key the Credential Provider extension reads.
///     The plaintext is encrypted-at-rest under a key held in the
///     Keychain with `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`.
///   * Tell the user whether the Credential Provider extension is
///     currently enabled in Settings.
public class FheAutofillModule: Module {
  public func definition() -> ModuleDefinition {
    Name("FheAutofill")

    AsyncFunction("isUmbralAvailable") { () -> Bool in
      return UmbralFFI.isAvailable
    }

    AsyncFunction("generateKeyPair") { () -> [String: Any] in
      let pair = try UmbralFFI.generateKeyPair()
      return [
        "public": [
          "umbralPublicKey": pair.publicKey,
          "umbralVerifyingKey": pair.verifyingKey,
          "umbralSignerPublicKey": pair.signerPublicKey,
        ],
        "secret": [
          "sk": pair.secretKey,
          "signerSk": pair.signerSecretKey,
        ],
      ]
    }

    AsyncFunction("decryptReencrypted") { (payload: [String: Any], options: [String: Any]) -> [String: Any] in
      let plaintext = try UmbralFFI.decryptReencrypted(
        recipientSk: payload["recipientSk"] as? String ?? "",
        delegatingPk: payload["delegatingPk"] as? String ?? "",
        verifyingPk: payload["verifyingPk"] as? String ?? "",
        capsule: payload["capsule"] as? String ?? "",
        cfrag: payload["cfrag"] as? String ?? "",
        ciphertext: payload["ciphertext"] as? String ?? ""
      )

      if let sealed = options["sealedAutofill"] as? Bool, sealed {
        let id = PendingFillStore.shared.put(
          plaintext: plaintext,
          domain: options["domain"] as? String
        )
        return ["autofilled": true, "id": id, "domain": options["domain"] ?? ""]
      } else {
        let s = String(data: plaintext, encoding: .utf8) ?? ""
        return ["plaintext": s]
      }
    }

    AsyncFunction("isSystemAutofillEnabled") { () -> Bool in
      // ASCredentialIdentityStore reports whether our extension is
      // enabled by checking whether we can enumerate its state.
      return await CredentialProviderStatus.isEnabled()
    }

    AsyncFunction("openSystemAutofillSettings") { () -> Void in
      // No direct deep-link on iOS 15+; best we can do is open the
      // app's own settings bundle.
      if let url = URL(string: UIApplication.openSettingsURLString) {
        DispatchQueue.main.async { UIApplication.shared.open(url) }
      }
    }

    AsyncFunction("storePendingFill") { (payload: [String: Any], packageHint: String) -> [String: Any] in
      let plaintext = try UmbralFFI.decryptReencrypted(
        recipientSk: payload["recipientSk"] as? String ?? "",
        delegatingPk: payload["delegatingPk"] as? String ?? "",
        verifyingPk: payload["verifyingPk"] as? String ?? "",
        capsule: payload["capsule"] as? String ?? "",
        cfrag: payload["cfrag"] as? String ?? "",
        ciphertext: payload["ciphertext"] as? String ?? ""
      )
      let id = PendingFillStore.shared.put(plaintext: plaintext, domain: packageHint)
      return ["id": id]
    }

    AsyncFunction("clearPendingFills") { () -> Void in
      PendingFillStore.shared.clearAll()
    }
  }
}

import UIKit
