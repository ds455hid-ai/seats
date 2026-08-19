import Foundation

/// delete_manifest.json 内の1件分。PC側の manifest.py が生成するJSON構造と一致させる。
public struct ManifestItem: Codable, Equatable, Identifiable {
    public var mediaId: String
    public var fileName: String
    public var mediaType: String // "photo" | "video"
    public var capturedAt: String?
    public var fileSize: Int64
    public var width: Int?
    public var height: Int?
    public var duration: Double?
    public var sha256: String?
    public var iphoneLocalIdentifier: String?

    public var id: String { mediaId }

    enum CodingKeys: String, CodingKey {
        case mediaId = "media_id"
        case fileName = "file_name"
        case mediaType = "media_type"
        case capturedAt = "captured_at"
        case fileSize = "file_size"
        case width
        case height
        case duration
        case sha256
        case iphoneLocalIdentifier = "iphone_local_identifier"
    }

    public init(
        mediaId: String,
        fileName: String,
        mediaType: String,
        capturedAt: String?,
        fileSize: Int64,
        width: Int?,
        height: Int?,
        duration: Double?,
        sha256: String?,
        iphoneLocalIdentifier: String?
    ) {
        self.mediaId = mediaId
        self.fileName = fileName
        self.mediaType = mediaType
        self.capturedAt = capturedAt
        self.fileSize = fileSize
        self.width = width
        self.height = height
        self.duration = duration
        self.sha256 = sha256
        self.iphoneLocalIdentifier = iphoneLocalIdentifier
    }

    /// captured_at はPC側のPythonが `datetime.isoformat()` で出力した文字列で、
    /// タイムゾーン付き/無し・小数秒あり/なしが混在しうる。パース失敗時はnilを返し、
    /// 呼び出し元(AssetMatcher)は日時による照合スコアを単に加点しないだけで処理は継続する。
    public var capturedAtDate: Date? {
        guard let capturedAt, !capturedAt.isEmpty else { return nil }
        return DateParsing.parseFlexibleISODate(capturedAt)
    }
}

/// 複数のISO8601風フォーマットを許容する日時パーサー。
public enum DateParsing {
    private static let candidateFormats = [
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSSZZZZZ",
        "yyyy-MM-dd'T'HH:mm:ssZZZZZ",
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
        "yyyy-MM-dd'T'HH:mm:ss",
    ]

    public static func parseFlexibleISODate(_ raw: String) -> Date? {
        for format in candidateFormats {
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.timeZone = TimeZone(identifier: "UTC")
            formatter.dateFormat = format
            if let date = formatter.date(from: raw) {
                return date
            }
        }
        return nil
    }
}

/// delete_manifest.json 全体。
public struct DeleteManifest: Codable, Equatable {
    public var version: Int
    public var createdAt: String
    public var items: [ManifestItem]

    enum CodingKeys: String, CodingKey {
        case version
        case createdAt = "created_at"
        case items
    }

    public init(version: Int, createdAt: String, items: [ManifestItem]) {
        self.version = version
        self.createdAt = createdAt
        self.items = items
    }
}
