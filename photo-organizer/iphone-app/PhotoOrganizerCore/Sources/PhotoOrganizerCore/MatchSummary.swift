import Foundation

/// 照合結果の集計(仕様37の画面表示に使う)。
public struct MatchSummary: Equatable {
    public var matchedCount: Int
    public var ambiguousCount: Int
    public var notFoundCount: Int
    public var matchedPhotoCount: Int
    public var matchedVideoCount: Int
    public var matchedTotalSize: Int64

    public static func summarize(_ results: [MatchResult]) -> MatchSummary {
        var matched = 0
        var ambiguous = 0
        var notFound = 0
        var matchedPhoto = 0
        var matchedVideo = 0
        var totalSize: Int64 = 0

        for result in results {
            switch result.status {
            case .matched:
                matched += 1
                totalSize += result.manifestItem.fileSize
                if result.manifestItem.mediaType == "photo" {
                    matchedPhoto += 1
                } else {
                    matchedVideo += 1
                }
            case .ambiguous:
                ambiguous += 1
            case .notFound:
                notFound += 1
            }
        }

        return MatchSummary(
            matchedCount: matched,
            ambiguousCount: ambiguous,
            notFoundCount: notFound,
            matchedPhotoCount: matchedPhoto,
            matchedVideoCount: matchedVideo,
            matchedTotalSize: totalSize
        )
    }
}
