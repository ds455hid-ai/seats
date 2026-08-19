import Foundation

public enum ManifestLoaderError: Error, Equatable {
    case invalidJSON(String)
    case unsupportedVersion(Int)
}

/// delete_manifest.json の読み込み・パース(仕様22: iPhone側)。
public enum ManifestLoader {
    static let supportedVersion = 1

    public static func decode(_ data: Data) throws -> DeleteManifest {
        let decoder = JSONDecoder()
        let manifest: DeleteManifest
        do {
            manifest = try decoder.decode(DeleteManifest.self, from: data)
        } catch {
            throw ManifestLoaderError.invalidJSON(error.localizedDescription)
        }
        guard manifest.version == supportedVersion else {
            throw ManifestLoaderError.unsupportedVersion(manifest.version)
        }
        return manifest
    }

    public static func load(from url: URL) throws -> DeleteManifest {
        let data = try Data(contentsOf: url)
        return try decode(data)
    }
}
