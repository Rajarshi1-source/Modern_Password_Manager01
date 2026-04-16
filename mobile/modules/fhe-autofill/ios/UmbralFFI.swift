import Foundation

/// UmbralFFI — Swift façade over the Rust `umbral-pre` crate.
///
/// Integration steps (see SPEC.md):
///   * Vendor `libumbral_pre.a` into `mobile/modules/fhe-autofill/ios/`
///     (universal static library containing arm64 + x86_64 slices).
///   * Declare the C-ABI functions in `umbral_pre.h` and add that
///     header to the module's `umbrella` header so Swift can see
///     them.
///   * Link against `libresolv` and `libSystem` via the Podspec.
///
/// Until the static library is vendored, `isAvailable` returns
/// `false` and the other calls throw ``UmbralError.unavailable``.
/// That is fine: the JS layer falls back to the JS implementation.
public enum UmbralFFI {
  public struct KeyPair {
    public let publicKey: String
    public let verifyingKey: String
    public let signerPublicKey: String
    public let secretKey: String
    public let signerSecretKey: String
  }

  public enum UmbralError: Error {
    case unavailable
    case invalidInput(String)
    case decryptFailed
  }

  public static var isAvailable: Bool {
    // The real implementation will `dlsym("umbral_pre_generate_keypair")`
    // or check a compile-time flag.  Returning `false` here forces a
    // graceful JS fallback until the Rust static library is linked.
    return false
  }

  public static func generateKeyPair() throws -> KeyPair {
    guard isAvailable else { throw UmbralError.unavailable }
    // Forward to the C-ABI entry point.  The real implementation
    // populates `publicKey`, `verifyingKey`, `signerPublicKey`,
    // `secretKey`, `signerSecretKey` from `umbral_pre_generate_keypair`.
    throw UmbralError.unavailable
  }

  public static func decryptReencrypted(
    recipientSk: String,
    delegatingPk: String,
    verifyingPk: String,
    capsule: String,
    cfrag: String,
    ciphertext: String
  ) throws -> Data {
    guard isAvailable else { throw UmbralError.unavailable }
    // The production path decodes the base64url inputs, calls the
    // Rust entry point, and returns the plaintext as `Data`.
    throw UmbralError.unavailable
  }

  /// Best-effort zeroization: `Data` is a value type so pass it
  /// `inout`. After this call, any pointer previously taken from
  /// `data` is invalid.
  public static func zeroize(_ data: inout Data) {
    data.withUnsafeMutableBytes { buf in
      guard let base = buf.baseAddress else { return }
      memset_s(base, buf.count, 0, buf.count)
    }
    data = Data()
  }
}
