import XCTest
@testable import PhotoOrganizerCore

/// 誤削除防止テスト(仕様49)を中心とした AssetMatcher の単体テスト。
/// 最重要方針: 少しでも確信が持てない照合は MATCHED にしてはならない。
final class AssetMatcherTests: XCTestCase {

    private let referenceDate = DateParsing.parseFlexibleISODate("2026-01-01T10:00:00")!

    private func makeManifestItem(
        mediaId: String = "1",
        fileName: String = "IMG_0001.jpg",
        mediaType: String = "photo",
        capturedAt: String? = "2026-01-01T10:00:00",
        fileSize: Int64 = 5_000_000,
        width: Int? = 4032,
        height: Int? = 3024,
        duration: Double? = nil,
        sha256: String? = "abc123",
        iphoneLocalIdentifier: String? = nil
    ) -> ManifestItem {
        ManifestItem(
            mediaId: mediaId, fileName: fileName, mediaType: mediaType, capturedAt: capturedAt,
            fileSize: fileSize, width: width, height: height, duration: duration,
            sha256: sha256, iphoneLocalIdentifier: iphoneLocalIdentifier
        )
    }

    private func makeAsset(
        id: String = "asset-1",
        mediaType: String = "photo",
        creationDate: Date? = nil,
        width: Int? = 4032,
        height: Int? = 3024,
        duration: Double? = nil,
        fileSize: Int64? = 5_000_000,
        fileName: String? = "IMG_0001.jpg"
    ) -> AssetInfo {
        AssetInfo(
            localIdentifier: id, mediaType: mediaType, creationDate: creationDate,
            pixelWidth: width, pixelHeight: height, duration: duration,
            approximateFileSize: fileSize, originalFileName: fileName
        )
    }

    // MARK: - 正しく一致するケース

    func testAllFactorsAgree_producesMatched() {
        let item = makeManifestItem()
        let candidate = makeAsset(creationDate: referenceDate)
        let results = AssetMatcher.match(manifestItems: [item], candidates: [candidate])

        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results[0].status, .matched)
        XCTAssertEqual(results[0].matchedLocalIdentifier, "asset-1")
        XCTAssertTrue(results[0].isDeletable)
    }

    func testLocalIdentifierDirectMatch_isTrusted() {
        let item = makeManifestItem(iphoneLocalIdentifier: "asset-99")
        let candidate = makeAsset(id: "asset-99", width: 1, height: 1, fileSize: 1, fileName: "different.jpg")
        let results = AssetMatcher.match(manifestItems: [item], candidates: [candidate])

        XCTAssertEqual(results[0].status, .matched)
        XCTAssertEqual(results[0].matchedLocalIdentifier, "asset-99")
    }

    func testLocalIdentifierPointingToMissingAsset_isAmbiguousNotMatched() {
        let item = makeManifestItem(iphoneLocalIdentifier: "asset-does-not-exist")
        let results = AssetMatcher.match(manifestItems: [item], candidates: [])

        XCTAssertEqual(results[0].status, .ambiguous)
        XCTAssertFalse(results[0].isDeletable)
    }

    // MARK: - 誤削除防止: 単一要素の一致だけではMATCHEDにしない

    func testNoCandidatesAtAll_producesNotFound() {
        let item = makeManifestItem()
        let results = AssetMatcher.match(manifestItems: [item], candidates: [])
        XCTAssertEqual(results[0].status, .notFound)
        XCTAssertFalse(results[0].isDeletable)
    }

    func testSameCapturedAtOnly_doesNotProduceMatched() {
        // 撮影日時だけが一致し、サイズ・解像度・ファイル名が全く異なる別写真
        let item = makeManifestItem(fileName: "IMG_0001.jpg", fileSize: 5_000_000, width: 4032, height: 3024)
        let candidate = makeAsset(
            creationDate: referenceDate, width: 100, height: 100, fileSize: 999, fileName: "totally_different.png"
        )
        let results = AssetMatcher.match(manifestItems: [item], candidates: [candidate])
        XCTAssertNotEqual(results[0].status, .matched)
    }

    func testSameFileNameOnly_doesNotProduceMatched() {
        // ファイル名だけが一致し、他の要素は全く異なる(異なるフォルダの別写真が同名の場合を想定)
        let item = makeManifestItem(fileName: "IMG_0001.jpg", fileSize: 5_000_000, width: 4032, height: 3024, capturedAt: "2026-01-01T10:00:00")
        let candidate = makeAsset(
            creationDate: DateParsing.parseFlexibleISODate("2020-05-05T00:00:00"),
            width: 100, height: 100, fileSize: 999, fileName: "IMG_0001.jpg"
        )
        let results = AssetMatcher.match(manifestItems: [item], candidates: [candidate])
        XCTAssertNotEqual(results[0].status, .matched)
    }

    func testSimilarFileSizeOnly_doesNotProduceMatched() {
        let item = makeManifestItem(fileSize: 5_000_000, width: 4032, height: 3024, capturedAt: "2026-01-01T10:00:00")
        let candidate = makeAsset(
            creationDate: DateParsing.parseFlexibleISODate("2024-03-03T00:00:00"),
            width: 100, height: 100, fileSize: 5_050_000, fileName: "unrelated.jpg"
        )
        let results = AssetMatcher.match(manifestItems: [item], candidates: [candidate])
        XCTAssertNotEqual(results[0].status, .matched)
    }

    func testSameVideoDurationOnly_doesNotProduceMatched() {
        let item = makeManifestItem(
            mediaType: "video", fileSize: 50_000_000, width: 1920, height: 1080, duration: 30.0,
            capturedAt: "2026-01-01T10:00:00"
        )
        let candidate = makeAsset(
            mediaType: "video",
            creationDate: DateParsing.parseFlexibleISODate("2020-01-01T00:00:00"),
            width: 640, height: 480, duration: 30.1, fileSize: 3_000_000, fileName: "other.mov"
        )
        let results = AssetMatcher.match(manifestItems: [item], candidates: [candidate])
        XCTAssertNotEqual(results[0].status, .matched)
    }

    func testMissingCapturedAtAndResolution_neverProducesMatched() {
        // メタデータ欠損のケース: 判断材料が乏しいため、絶対にMATCHEDにしてはならない
        let item = makeManifestItem(capturedAt: nil, width: nil, height: nil, fileSize: 5_000_000)
        let candidate = makeAsset(creationDate: nil, width: nil, height: nil, fileSize: 5_010_000, fileName: "IMG_9999.jpg")
        let results = AssetMatcher.match(manifestItems: [item], candidates: [candidate])
        XCTAssertNotEqual(results[0].status, .matched)
    }

    func testTwoNearlyIdenticalCandidates_resultsInAmbiguousNotArbitraryMatch() {
        // 似たような写真が2枚デバイスにある場合、どちらか一方を勝手に選んで削除してはいけない
        let item = makeManifestItem()
        let candidateA = makeAsset(id: "asset-A", creationDate: referenceDate)
        let candidateB = makeAsset(id: "asset-B", creationDate: referenceDate)
        let results = AssetMatcher.match(manifestItems: [item], candidates: [candidateA, candidateB])

        XCTAssertEqual(results[0].status, .ambiguous)
        XCTAssertFalse(results[0].isDeletable)
    }

    // MARK: - 1つのPHAssetは1つのmanifestアイテムにしか割り当てない

    func testSameAssetIsNotMatchedToTwoDifferentManifestItems() {
        let itemA = makeManifestItem(mediaId: "1", fileName: "IMG_0001.jpg")
        let itemB = makeManifestItem(mediaId: "2", fileName: "IMG_0002.jpg")
        let candidate = makeAsset(id: "asset-1", creationDate: referenceDate)

        let results = AssetMatcher.match(manifestItems: [itemA, itemB], candidates: [candidate])

        let matchedResults = results.filter { $0.status == .matched }
        XCTAssertEqual(matchedResults.count, 1, "同じPHAssetが複数のmanifestアイテムに一致してはならない")
    }

    // MARK: - 集計

    func testMatchSummaryCountsEachStatus() {
        let matchedItem = makeManifestItem(mediaId: "1")
        let matchedCandidate = makeAsset(id: "asset-1", creationDate: referenceDate)

        let notFoundItem = makeManifestItem(mediaId: "2", fileName: "no_match.jpg")

        let results = AssetMatcher.match(
            manifestItems: [matchedItem, notFoundItem],
            candidates: [matchedCandidate]
        )
        let summary = MatchSummary.summarize(results)

        XCTAssertEqual(summary.matchedCount, 1)
        XCTAssertEqual(summary.notFoundCount, 1)
        XCTAssertEqual(summary.ambiguousCount, 0)
        XCTAssertEqual(summary.matchedPhotoCount, 1)
    }
}
