import Foundation
import AuthenticationServices

/// CredentialProviderStatus — asynchronously asks iOS whether our
/// ASCredentialProviderExtension is currently enabled in Settings.
public enum CredentialProviderStatus {
  public static func isEnabled() async -> Bool {
    await withCheckedContinuation { continuation in
      ASCredentialIdentityStore.shared.getState { state in
        continuation.resume(returning: state.isEnabled)
      }
    }
  }
}
