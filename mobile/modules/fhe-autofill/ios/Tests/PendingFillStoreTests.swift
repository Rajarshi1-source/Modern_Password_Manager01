import XCTest
@testable import FheAutofill

/// Unit tests for ``PendingFillStore``.
///
/// These tests rely on the App Group container being available; when
/// run inside the host app's test scheme that's handled automatically
/// by the signing configuration. In CI without an Apple provisioning
/// profile, the container URL is `nil` and the tests short-circuit
/// rather than fail (see `assumesContainerAvailable`).
final class PendingFillStoreTests: XCTestCase {

  override func setUp() {
    super.setUp()
    PendingFillStore.shared.clearAll()
  }

  override func tearDown() {
    PendingFillStore.shared.clearAll()
    super.tearDown()
  }

  private var isContainerAvailable: Bool {
    FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: PendingFillStore.appGroup) != nil
  }

  func testPutAndTakeByDomain() throws {
    try XCTSkipUnless(isContainerAvailable, "App Group container not available")
    let plaintext = "correct horse battery staple".data(using: .utf8)!
    _ = PendingFillStore.shared.put(plaintext: plaintext, domain: "example.com")

    let entry = PendingFillStore.shared.takeMatching(domain: "example.com")
    XCTAssertNotNil(entry)
    XCTAssertEqual(entry?.domain, "example.com")
    XCTAssertEqual(
      String(data: entry!.plaintext, encoding: .utf8),
      "correct horse battery staple"
    )
  }

  func testTakeConsumesEntry() throws {
    try XCTSkipUnless(isContainerAvailable, "App Group container not available")
    let plaintext = "secret".data(using: .utf8)!
    _ = PendingFillStore.shared.put(plaintext: plaintext, domain: "example.com")

    _ = PendingFillStore.shared.takeMatching(domain: "example.com")
    let second = PendingFillStore.shared.takeMatching(domain: "example.com")
    XCTAssertNil(second)
  }

  func testClearAllRemovesPendingEntries() throws {
    try XCTSkipUnless(isContainerAvailable, "App Group container not available")
    _ = PendingFillStore.shared.put(plaintext: Data([1, 2, 3]), domain: "a.com")
    _ = PendingFillStore.shared.put(plaintext: Data([4, 5, 6]), domain: "b.com")
    PendingFillStore.shared.clearAll()
    XCTAssertNil(PendingFillStore.shared.takeMatching(domain: "a.com"))
    XCTAssertNil(PendingFillStore.shared.takeMatching(domain: "b.com"))
  }
}
