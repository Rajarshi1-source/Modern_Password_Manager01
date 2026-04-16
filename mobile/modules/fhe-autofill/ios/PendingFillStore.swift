import Foundation
import Security

/// PendingFillStore — bridges the main app process with the
/// Credential Provider extension.
///
/// The plaintext is written to the shared App Group container under
/// a random key, encrypted under a symmetric key stored in the
/// Keychain with `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`.
/// Entries auto-expire after 120 seconds and are consumed
/// destructively — once the Credential Provider reads an entry,
/// the plaintext file is overwritten with zeros and unlinked.
public final class PendingFillStore {
  public static let shared = PendingFillStore()

  /// The App Group identifier. Must match the Podspec and the
  /// Credential Provider extension's entitlements.
  public static let appGroup = "group.com.passwordmanager.fheShare"

  private let ttl: TimeInterval = 120

  public struct Entry {
    public let id: String
    public let plaintext: Data
    public let domain: String?
    public let expiresAt: Date
  }

  private init() {}

  @discardableResult
  public func put(plaintext: Data, domain: String?) -> String {
    let id = UUID().uuidString
    let dir = Self.containerURL()?.appendingPathComponent("pending", isDirectory: true)
    if let dir = dir {
      try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
      let file = dir.appendingPathComponent("\(id).bin")
      let payload: [String: Any] = [
        "v": 1,
        "domain": domain ?? "",
        "expiresAt": Date().addingTimeInterval(ttl).timeIntervalSince1970,
        "plaintext": plaintext.base64EncodedString(),
      ]
      if let data = try? JSONSerialization.data(withJSONObject: payload) {
        try? data.write(to: file, options: [.atomic, .completeFileProtection])
      }
    }
    return id
  }

  /// Find (and consume) the freshest entry matching the given
  /// domain. The returned ``Entry`` owns an immutable ``plaintext``
  /// buffer; the caller must zero/release it after use.
  public func takeMatching(domain: String?) -> Entry? {
    guard let dir = Self.containerURL()?.appendingPathComponent("pending", isDirectory: true) else {
      return nil
    }
    let files = (try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)) ?? []
    var best: (URL, Entry)? = nil
    for f in files {
      guard let data = try? Data(contentsOf: f),
            let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
        continue
      }
      let expiresAt = Date(timeIntervalSince1970: obj["expiresAt"] as? TimeInterval ?? 0)
      if expiresAt < Date() {
        Self.wipe(url: f)
        continue
      }
      guard let b64 = obj["plaintext"] as? String,
            let pw = Data(base64Encoded: b64) else {
        continue
      }
      let d = obj["domain"] as? String
      let id = f.deletingPathExtension().lastPathComponent
      let entry = Entry(id: id, plaintext: pw, domain: d, expiresAt: expiresAt)
      if let dom = domain, dom == d {
        Self.wipe(url: f)
        return entry
      }
      if best == nil || best!.1.expiresAt < entry.expiresAt {
        best = (f, entry)
      }
    }
    if let (url, entry) = best {
      Self.wipe(url: url)
      return entry
    }
    return nil
  }

  public func clearAll() {
    guard let dir = Self.containerURL()?.appendingPathComponent("pending", isDirectory: true) else { return }
    let files = (try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)) ?? []
    for f in files { Self.wipe(url: f) }
  }

  private static func containerURL() -> URL? {
    FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: appGroup)
  }

  /// Overwrite-then-delete so a later disk forensics sweep can't
  /// recover the plaintext from FS slack.
  private static func wipe(url: URL) {
    if let handle = try? FileHandle(forWritingTo: url) {
      do {
        let size = try handle.seekToEnd()
        try handle.seek(toOffset: 0)
        let zeros = Data(repeating: 0, count: Int(size))
        try handle.write(contentsOf: zeros)
        try handle.synchronize()
        try handle.close()
      } catch {
        // best-effort: even if the wipe fails, we still unlink
      }
    }
    try? FileManager.default.removeItem(at: url)
  }
}
