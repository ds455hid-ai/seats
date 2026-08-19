import Photos
import PhotoOrganizerCore

/// PHAssetを取得し、照合エンジン(AssetMatcher)が扱える AssetInfo に変換する(仕様20,21)。
enum PHAssetFetcher {
    /// 写真・動画の両方を対象にする(仕様21)。
    static func fetchAllAssetInfos(progress: ((Int, Int) -> Void)? = nil) -> [AssetInfo] {
        let options = PHFetchOptions()
        let fetchResult = PHAsset.fetchAssets(with: options)
        var results: [AssetInfo] = []
        results.reserveCapacity(fetchResult.count)

        fetchResult.enumerateObjects { asset, index, _ in
            let mediaTypeString: String
            switch asset.mediaType {
            case .image:
                mediaTypeString = "photo"
            case .video:
                mediaTypeString = "video"
            default:
                progress?(index + 1, fetchResult.count)
                return // 音声等、写真/動画以外は対象外(仕様21)
            }

            let resources = PHAssetResource.assetResources(for: asset)
            // 注意: "fileSize" はPHAssetResourceの公式APIとしては公開されていないKVCキーであり、
            // 将来のOSアップデートで取得できなくなる可能性がある。あくまでベストエフォートの
            // 参考情報として扱い、取得できない場合はnilのまま照合ロジック側で他の要素を使う。
            let fileSize = resources.first.flatMap { $0.value(forKey: "fileSize") as? Int64 }
            let fileName = resources.first?.originalFilename

            let info = AssetInfo(
                localIdentifier: asset.localIdentifier,
                mediaType: mediaTypeString,
                creationDate: asset.creationDate,
                pixelWidth: asset.pixelWidth,
                pixelHeight: asset.pixelHeight,
                duration: asset.mediaType == .video ? asset.duration : nil,
                approximateFileSize: fileSize,
                originalFileName: fileName
            )
            results.append(info)
            // 大量の写真(数万枚)を扱う際に進捗コールバックが大量発生しないよう間引く
            if (index + 1) % 200 == 0 || index + 1 == fetchResult.count {
                progress?(index + 1, fetchResult.count)
            }
        }

        return results
    }
}
