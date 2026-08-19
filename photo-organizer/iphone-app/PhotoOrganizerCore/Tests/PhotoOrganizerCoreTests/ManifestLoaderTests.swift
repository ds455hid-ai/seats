import XCTest
@testable import PhotoOrganizerCore

final class ManifestLoaderTests: XCTestCase {

    private let validJSON = """
    {
      "version": 1,
      "created_at": "2026-01-01T00:00:00+00:00",
      "items": [
        {
          "media_id": "1",
          "file_name": "IMG_0001.jpg",
          "media_type": "photo",
          "captured_at": "2026-01-01T10:00:00",
          "file_size": 1234567,
          "width": 4032,
          "height": 3024,
          "duration": null,
          "sha256": "abc123",
          "iphone_local_identifier": null
        },
        {
          "media_id": "2",
          "file_name": "IMG_0002.mov",
          "media_type": "video",
          "captured_at": "2026-01-01T10:05:00",
          "file_size": 98765432,
          "width": 1920,
          "height": 1080,
          "duration": 12.5,
          "sha256": "def456",
          "iphone_local_identifier": null
        }
      ]
    }
    """

    func testDecodeValidManifest() throws {
        let manifest = try ManifestLoader.decode(validJSON.data(using: .utf8)!)
        XCTAssertEqual(manifest.version, 1)
        XCTAssertEqual(manifest.items.count, 2)
        XCTAssertEqual(manifest.items[0].mediaId, "1")
        XCTAssertEqual(manifest.items[0].mediaType, "photo")
        XCTAssertNil(manifest.items[0].duration)
        XCTAssertEqual(manifest.items[1].duration, 12.5)
        XCTAssertNil(manifest.items[1].iphoneLocalIdentifier)
    }

    func testDecodeInvalidJSONThrows() {
        let invalidData = "not json".data(using: .utf8)!
        XCTAssertThrowsError(try ManifestLoader.decode(invalidData)) { error in
            guard case ManifestLoaderError.invalidJSON = error else {
                return XCTFail("invalidJSONエラーになるべき")
            }
        }
    }

    func testDecodeUnsupportedVersionThrows() {
        let json = """
        {"version": 999, "created_at": "2026-01-01T00:00:00Z", "items": []}
        """
        XCTAssertThrowsError(try ManifestLoader.decode(json.data(using: .utf8)!)) { error in
            guard case ManifestLoaderError.unsupportedVersion(let version) = error else {
                return XCTFail("unsupportedVersionエラーになるべき")
            }
            XCTAssertEqual(version, 999)
        }
    }

    func testEmptyItemsListDecodesSuccessfully() throws {
        let json = """
        {"version": 1, "created_at": "2026-01-01T00:00:00Z", "items": []}
        """
        let manifest = try ManifestLoader.decode(json.data(using: .utf8)!)
        XCTAssertEqual(manifest.items.count, 0)
    }
}
