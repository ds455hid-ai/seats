import Foundation

/// PC側delete_manifest.jsonの各アイテムと、iPhone上のPHAssetを安全に照合するロジック。
///
/// 最重要方針(仕様36): 少しでも確信が持てない場合はAMBIGUOUSとし、削除対象にしない。
/// 複数の要素(ファイルサイズ・撮影日時・解像度・動画時間・ファイル名)を組み合わせたスコアで判定し、
/// 単一要素だけでMATCHEDにはしない設計にしている(仕様34)。
public enum AssetMatcher {
    public struct Config: Equatable {
        /// このスコア以上、かつ2位候補と十分な差がある場合のみMATCHEDにする
        public var matchThreshold: Int
        /// 1位と2位のスコア差がこれ未満なら「確信が持てない」としてAMBIGUOUSにする
        public var ambiguousMarginThreshold: Int
        /// これ未満のスコアの候補は「一致の可能性なし」としてNOT_FOUND扱いの材料にする
        public var minimumConsiderScore: Int
        public var dateToleranceSeconds: Double
        public var durationToleranceSeconds: Double

        public init(
            matchThreshold: Int = 70,
            ambiguousMarginThreshold: Int = 15,
            minimumConsiderScore: Int = 30,
            dateToleranceSeconds: Double = 5,
            durationToleranceSeconds: Double = 1.5
        ) {
            self.matchThreshold = matchThreshold
            self.ambiguousMarginThreshold = ambiguousMarginThreshold
            self.minimumConsiderScore = minimumConsiderScore
            self.dateToleranceSeconds = dateToleranceSeconds
            self.durationToleranceSeconds = durationToleranceSeconds
        }

        public static let `default` = Config()
    }

    /// manifest内の各アイテムをPHAsset候補群と照合する。
    ///
    /// - Important: 1つのPHAssetは1つのmanifestアイテムにしか一致させない
    ///   (同じ写真が複数の削除候補と誤って一致するのを防ぐ)。
    public static func match(
        manifestItems: [ManifestItem],
        candidates: [AssetInfo],
        config: Config = .default
    ) -> [MatchResult] {
        var results: [MatchResult] = []
        var usedIdentifiers = Set<String>()

        for item in manifestItems {
            // 高速パス: Phase2以降でiPhone側エクスポート時にlocalIdentifierが既に埋め込まれている場合。
            // Phase1のPC単純解析では基本的にnilだが、将来の拡張に備えて対応する。
            if let directId = item.iphoneLocalIdentifier, !directId.isEmpty {
                if !usedIdentifiers.contains(directId),
                   let directCandidate = candidates.first(where: { $0.localIdentifier == directId }) {
                    usedIdentifiers.insert(directId)
                    results.append(MatchResult(
                        manifestItem: item, status: .matched, matchedLocalIdentifier: directCandidate.localIdentifier,
                        confidenceScore: 100, reason: "localIdentifierによる直接一致"
                    ))
                } else {
                    results.append(MatchResult(
                        manifestItem: item, status: .ambiguous, matchedLocalIdentifier: nil,
                        confidenceScore: 0, reason: "localIdentifier指定があるが対応する写真/動画が見つからない"
                    ))
                }
                continue
            }

            let sameTypeCandidates = candidates.filter {
                $0.mediaType == item.mediaType && !usedIdentifiers.contains($0.localIdentifier)
            }
            if sameTypeCandidates.isEmpty {
                results.append(MatchResult(
                    manifestItem: item, status: .notFound, matchedLocalIdentifier: nil,
                    confidenceScore: 0, reason: "同じ種類の写真/動画がライブラリ内に見つからない"
                ))
                continue
            }

            let scored = sameTypeCandidates
                .map { candidate -> (candidate: AssetInfo, score: Int, reasons: [String]) in
                    let (score, reasons) = scoreMatch(item: item, candidate: candidate, config: config)
                    return (candidate, score, reasons)
                }
                .sorted { $0.score > $1.score }

            guard let best = scored.first, best.score >= config.minimumConsiderScore else {
                results.append(MatchResult(
                    manifestItem: item, status: .notFound, matchedLocalIdentifier: nil,
                    confidenceScore: scored.first?.score ?? 0, reason: "十分に一致する候補が見つからない"
                ))
                continue
            }

            let secondScore = scored.count > 1 ? scored[1].score : 0
            let margin = best.score - secondScore

            if best.score >= config.matchThreshold && margin >= config.ambiguousMarginThreshold {
                usedIdentifiers.insert(best.candidate.localIdentifier)
                results.append(MatchResult(
                    manifestItem: item, status: .matched, matchedLocalIdentifier: best.candidate.localIdentifier,
                    confidenceScore: best.score, reason: best.reasons.joined(separator: "、")
                ))
            } else {
                results.append(MatchResult(
                    manifestItem: item, status: .ambiguous, matchedLocalIdentifier: nil,
                    confidenceScore: best.score,
                    reason: "候補が複数あり確信が持てないため安全のため保留(" + best.reasons.joined(separator: "、") + ")"
                ))
            }
        }

        return results
    }

    /// 2つの要素間の類似度を0〜100のスコアとして算出する。単一要素だけでは高スコアにならないよう、
    /// 複数の一致要素が揃って初めて閾値を超えるように重み付けしている。
    private static func scoreMatch(item: ManifestItem, candidate: AssetInfo, config: Config) -> (Int, [String]) {
        var score = 0
        var reasons: [String] = []

        if let candidateSize = candidate.approximateFileSize, item.fileSize > 0, candidateSize > 0 {
            let ratio = Double(min(candidateSize, item.fileSize)) / Double(max(candidateSize, item.fileSize))
            if ratio > 0.98 {
                score += 30
                reasons.append("ファイルサイズがほぼ一致")
            } else if ratio > 0.90 {
                score += 15
                reasons.append("ファイルサイズが近い")
            }
        }

        if let itemDate = item.capturedAtDate, let candidateDate = candidate.creationDate {
            let diff = abs(itemDate.timeIntervalSince(candidateDate))
            if diff <= config.dateToleranceSeconds {
                score += 30
                reasons.append("撮影日時が一致")
            } else if diff <= 60 {
                score += 10
                reasons.append("撮影日時が近い(1分以内)")
            }
        }

        if let iw = item.width, let ih = item.height,
           let cw = candidate.pixelWidth, let ch = candidate.pixelHeight {
            if iw == cw && ih == ch {
                score += 20
                reasons.append("解像度が一致")
            } else if iw == ch && ih == cw {
                score += 12
                reasons.append("解像度が回転違いで一致")
            }
        }

        if item.mediaType == "video", let itemDuration = item.duration, let candidateDuration = candidate.duration {
            if abs(itemDuration - candidateDuration) <= config.durationToleranceSeconds {
                score += 20
                reasons.append("動画時間が一致")
            }
        }

        if let candidateName = candidate.originalFileName,
           candidateName.caseInsensitiveCompare(item.fileName) == .orderedSame {
            score += 10
            reasons.append("ファイル名が一致")
        }

        return (min(score, 100), reasons)
    }
}
