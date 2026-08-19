import Foundation

/// 削除実行1回分の結果(仕様39)。写真/動画の内容は一切含まない、件数のみの記録。
public struct DeletionOutcome: Codable, Equatable {
    public var executedAt: String
    public var successCount: Int
    public var failureCount: Int
    public var skippedCount: Int

    public init(executedAt: String, successCount: Int, failureCount: Int, skippedCount: Int) {
        self.executedAt = executedAt
        self.successCount = successCount
        self.failureCount = failureCount
        self.skippedCount = skippedCount
    }
}

/// 操作ログ1件(仕様44)。ファイルパスや画像内容は含めない。
public struct OperationLogEntry: Codable, Equatable {
    public var eventType: String
    public var occurredAt: String
    public var detail: [String: Int]

    public init(eventType: String, occurredAt: String, detail: [String: Int]) {
        self.eventType = eventType
        self.occurredAt = occurredAt
        self.detail = detail
    }
}
