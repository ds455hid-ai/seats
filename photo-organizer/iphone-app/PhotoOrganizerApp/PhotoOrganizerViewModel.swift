import Foundation
import Photos
import PhotoOrganizerCore

@MainActor
final class PhotoOrganizerViewModel: ObservableObject {
    @Published var step: AppStep = .checkingPermission
    @Published var authorizationStatus: PHAuthorizationStatus = .notDetermined
    @Published var manifest: DeleteManifest?
    @Published var matchResults: [MatchResult] = []
    @Published var excludedMediaIds: Set<String> = []
    @Published var deletionOutcome: DeletionOutcome?
    @Published var errorMessage: String?
    @Published var matchingProgressText: String = ""
    @Published var backupConfirmed: Bool = false

    var summary: MatchSummary { MatchSummary.summarize(matchResults) }

    /// 実際に削除対象になる項目(MATCHEDかつユーザーが除外していないもの、仕様36・37)
    var deletableResults: [MatchResult] {
        matchResults.filter { $0.isDeletable && !excludedMediaIds.contains($0.manifestItem.mediaId) }
    }

    var deletableTotalSize: Int64 {
        deletableResults.reduce(0) { $0 + $1.manifestItem.fileSize }
    }

    var deletablePhotoCount: Int {
        deletableResults.filter { $0.manifestItem.mediaType == "photo" }.count
    }

    var deletableVideoCount: Int {
        deletableResults.filter { $0.manifestItem.mediaType == "video" }.count
    }

    func checkPermission() {
        authorizationStatus = PhotoLibraryPermission.currentStatus
        switch authorizationStatus {
        case .authorized, .limited:
            step = .importManifest
        case .notDetermined:
            step = .checkingPermission
        default:
            step = .permissionDenied
        }
    }

    func requestPermission() async {
        let status = await PhotoLibraryPermission.requestAuthorization()
        authorizationStatus = status
        if status == .authorized || status == .limited {
            step = .importManifest
        } else {
            step = .permissionDenied
        }
    }

    func loadManifest(from url: URL) {
        let didAccess = url.startAccessingSecurityScopedResource()
        defer { if didAccess { url.stopAccessingSecurityScopedResource() } }
        do {
            let loaded = try ManifestLoader.load(from: url)
            manifest = loaded
            errorMessage = nil
            OperationLogger.log(eventType: "manifest_imported", detail: ["item_count": loaded.items.count])
            runMatching(items: loaded.items)
        } catch {
            errorMessage = "manifestの読み込みに失敗しました。ファイルが壊れているか、対応していない形式です。"
        }
    }

    func runMatching(items: [ManifestItem]) {
        step = .matching
        matchingProgressText = "写真ライブラリを読み込み中..."

        Task.detached(priority: .userInitiated) { [weak self] in
            let candidates = PHAssetFetcher.fetchAllAssetInfos { done, total in
                Task { @MainActor in
                    self?.matchingProgressText = "写真ライブラリを読み込み中... \(done)/\(total)"
                }
            }
            let results = AssetMatcher.match(manifestItems: items, candidates: candidates)
            let summary = MatchSummary.summarize(results)

            OperationLogger.log(eventType: "matching_completed", detail: [
                "matched": summary.matchedCount,
                "ambiguous": summary.ambiguousCount,
                "not_found": summary.notFoundCount,
            ])

            await MainActor.run {
                guard let self else { return }
                self.matchResults = results
                self.excludedMediaIds = []
                self.step = .review
            }
        }
    }

    func toggleExclude(mediaId: String) {
        if excludedMediaIds.contains(mediaId) {
            excludedMediaIds.remove(mediaId)
        } else {
            excludedMediaIds.insert(mediaId)
        }
    }

    func proceedToFinalConfirm() {
        backupConfirmed = false
        step = .finalConfirm
    }

    func backToReview() {
        step = .review
    }

    func executeDeletion() async {
        guard backupConfirmed else { return } // 仕様41: バックアップ確認なしでは削除させない
        step = .deleting
        let identifiers = deletableResults.compactMap { $0.matchedLocalIdentifier }
        let outcome = await DeletionService.deleteAssets(localIdentifiers: identifiers)
        deletionOutcome = outcome
        step = .result
        OperationLogger.log(eventType: "deletion_executed", detail: [
            "success": outcome.successCount,
            "failure": outcome.failureCount,
            "skipped": outcome.skippedCount,
        ])
    }

    func reset() {
        manifest = nil
        matchResults = []
        excludedMediaIds = []
        deletionOutcome = nil
        errorMessage = nil
        backupConfirmed = false
        step = .importManifest
    }
}
