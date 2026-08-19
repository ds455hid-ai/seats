import Photos
import PhotoOrganizerCore

/// PhotoKitの正式な変更APIを使った削除実行(仕様39)。
///
/// 重要: この関数はユーザーが最終確認ボタンを押した後にのみ呼び出すこと。
/// 呼び出すとiOS標準の削除確認ダイアログが表示される(アプリ側で抑制不可、これは仕様通り)。
enum DeletionService {
    static func deleteAssets(localIdentifiers: [String]) async -> DeletionOutcome {
        let executedAt = ISO8601DateFormatter().string(from: Date())

        guard !localIdentifiers.isEmpty else {
            return DeletionOutcome(executedAt: executedAt, successCount: 0, failureCount: 0, skippedCount: 0)
        }

        let fetchResult = PHAsset.fetchAssets(withLocalIdentifiers: localIdentifiers, options: nil)
        var assetsToDelete: [PHAsset] = []
        fetchResult.enumerateObjects { asset, _, _ in assetsToDelete.append(asset) }

        // 要求したlocalIdentifierのうち、既にライブラリに存在しないものはスキップ扱い(仕様39)
        let skippedCount = localIdentifiers.count - assetsToDelete.count

        guard !assetsToDelete.isEmpty else {
            return DeletionOutcome(executedAt: executedAt, successCount: 0, failureCount: 0, skippedCount: skippedCount)
        }

        let (success, _): (Bool, Error?) = await withCheckedContinuation { continuation in
            PHPhotoLibrary.shared().performChanges({
                PHAssetChangeRequest.deleteAssets(assetsToDelete as NSArray)
            }, completionHandler: { success, error in
                continuation.resume(returning: (success, error))
            })
        }

        return DeletionOutcome(
            executedAt: executedAt,
            successCount: success ? assetsToDelete.count : 0,
            failureCount: success ? 0 : assetsToDelete.count,
            skippedCount: skippedCount
        )
    }
}
