import Foundation
import PhotoOrganizerCore

/// 操作ログ記録(仕様44)。写真/動画の内容・ファイルパスは一切記録しない。件数と日時のみ。
enum OperationLogger {
    private static var logFileURL: URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("operation_log.jsonl")
    }

    static func log(eventType: String, detail: [String: Int]) {
        let entry = OperationLogEntry(
            eventType: eventType,
            occurredAt: ISO8601DateFormatter().string(from: Date()),
            detail: detail
        )
        guard let data = try? JSONEncoder().encode(entry),
              let line = String(data: data, encoding: .utf8) else { return }
        appendLine(line)
    }

    private static func appendLine(_ line: String) {
        let url = logFileURL
        let fullLine = line + "\n"
        guard let lineData = fullLine.data(using: .utf8) else { return }

        if FileManager.default.fileExists(atPath: url.path), let handle = try? FileHandle(forWritingTo: url) {
            handle.seekToEndOfFile()
            handle.write(lineData)
            handle.closeFile()
        } else {
            try? fullLine.write(to: url, atomically: true, encoding: .utf8)
        }
    }
}
