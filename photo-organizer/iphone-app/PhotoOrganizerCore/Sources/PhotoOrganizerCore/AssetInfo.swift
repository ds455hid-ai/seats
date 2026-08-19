import Foundation

/// PHAsset から抽出した、照合に必要な情報だけを持つ軽量な構造体。
///
/// PhotoKit(PHAsset)に直接依存させず、この構造体を介すことで、
/// 実機・シミュレータが無くてもAssetMatcherのロジックを単体テストできるようにしている。
public struct AssetInfo: Equatable {
    public var localIdentifier: String
    public var mediaType: String // "photo" | "video"
    public var creationDate: Date?
    public var pixelWidth: Int?
    public var pixelHeight: Int?
    public var duration: Double? // 動画のみ。写真はnil
    public var approximateFileSize: Int64? // 取得できない場合はnil(ベストエフォート)
    public var originalFileName: String?

    public init(
        localIdentifier: String,
        mediaType: String,
        creationDate: Date?,
        pixelWidth: Int?,
        pixelHeight: Int?,
        duration: Double?,
        approximateFileSize: Int64?,
        originalFileName: String?
    ) {
        self.localIdentifier = localIdentifier
        self.mediaType = mediaType
        self.creationDate = creationDate
        self.pixelWidth = pixelWidth
        self.pixelHeight = pixelHeight
        self.duration = duration
        self.approximateFileSize = approximateFileSize
        self.originalFileName = originalFileName
    }
}
