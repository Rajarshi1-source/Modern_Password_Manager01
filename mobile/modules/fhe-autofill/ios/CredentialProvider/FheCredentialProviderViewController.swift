import AuthenticationServices
import UIKit

/// FheCredentialProviderViewController — iOS Credential Provider
/// extension entry point.
///
/// Flow:
///   1. The OS launches the extension when the user taps "Passwords"
///      on a login form.
///   2. `prepareCredentialList(for:)` is called with the
///      identifying `ASCredentialServiceIdentifier`s for the host
///      app or website.
///   3. We ask ``PendingFillStore`` for the freshest entry whose
///      `domain` matches the first identifier. If found, we
///      immediately `completeRequest(withSelectedCredential:)`.
///   4. If no pending entry is queued, we present a minimal UI that
///      tells the user to open the main app and receive the share
///      first.
///
/// We never display the plaintext to the user.  The
/// `ASPasswordCredential` object is constructed, handed to the OS,
/// and released; the plaintext buffer is zeroed in `deinit` on
/// best-effort.
public final class FheCredentialProviderViewController: ASCredentialProviderViewController {

  public override func prepareCredentialList(for serviceIdentifiers: [ASCredentialServiceIdentifier]) {
    let domain = serviceIdentifiers.first?.identifier ?? ""
    guard let entry = PendingFillStore.shared.takeMatching(domain: domain) else {
      renderEmptyState(domain: domain)
      return
    }
    guard let plaintextString = String(data: entry.plaintext, encoding: .utf8) else {
      self.extensionContext.cancelRequest(withError: NSError(
        domain: ASExtensionErrorDomain,
        code: ASExtensionError.failed.rawValue
      ))
      return
    }
    let credential = ASPasswordCredential(user: "", password: plaintextString)
    self.extensionContext.completeRequest(withSelectedCredential: credential) { _ in
      // plaintext is immutable Swift String here; best effort cleanup
    }
  }

  public override func provideCredentialWithoutUserInteraction(
    for credentialIdentity: ASPasswordCredentialIdentity
  ) {
    // Same logic as prepareCredentialList, but without UI.
    let domain = credentialIdentity.serviceIdentifier.identifier
    guard let entry = PendingFillStore.shared.takeMatching(domain: domain) else {
      self.extensionContext.cancelRequest(withError: NSError(
        domain: ASExtensionErrorDomain,
        code: ASExtensionError.userInteractionRequired.rawValue
      ))
      return
    }
    let plaintext = String(data: entry.plaintext, encoding: .utf8) ?? ""
    let credential = ASPasswordCredential(user: credentialIdentity.user ?? "", password: plaintext)
    self.extensionContext.completeRequest(withSelectedCredential: credential, completionHandler: nil)
  }

  private func renderEmptyState(domain: String) {
    let label = UILabel()
    label.translatesAutoresizingMaskIntoConstraints = false
    label.text = "No FHE share ready for \(domain).\nOpen the Password Manager app and receive a share first."
    label.numberOfLines = 0
    label.textAlignment = .center
    label.textColor = .label
    view.addSubview(label)
    NSLayoutConstraint.activate([
      label.centerXAnchor.constraint(equalTo: view.centerXAnchor),
      label.centerYAnchor.constraint(equalTo: view.centerYAnchor),
      label.leadingAnchor.constraint(greaterThanOrEqualTo: view.leadingAnchor, constant: 20),
      label.trailingAnchor.constraint(lessThanOrEqualTo: view.trailingAnchor, constant: -20),
    ])
  }
}
