import Foundation

/// PC側のファイルと、iPhone上のPHAssetとの照合結果ステータス(仕様35)。
///
/// MATCHEDのみが削除対象になりうる。AMBIGUOUSとNOT_FOUNDは
/// どれだけスコアが高くても絶対に削除対象にしない(仕様36: 誤削除防止最優先)。
public enum MatchStatus: String, Codable, Equatable {
    case matched = "MATCHED"
    case ambiguous = "AMBIGUOUS"
    case notFound = "NOT_FOUND"
}

public struct MatchResult: Equatable {
    public var manifestItem: ManifestItem
    public var status: MatchStatus
    public var matchedLocalIdentifier: String?
    public var confidenceScore: Int // 0-100。あくまで参考値、削除可否の判定には使わない
    public var reason: String

    public init(
        manifestItem: ManifestItem,
        status: MatchStatus,
        matchedLocalIdentifier: String?,
        confidenceScore: Int,
        reason: String
    ) {
        self.manifestItem = manifestItem
        self.status = status
        self.matchedLocalIdentifier = matchedLocalIdentifier
        self.confidenceScore = confidenceScore
        self.reason = reason
    }

    /// 削除操作の対象にしてよいのはMATCHEDのみ(仕様36)。
    public var isDeletable: Bool {
        status == .matched && matchedLocalIdentifier != nil
    }
}
