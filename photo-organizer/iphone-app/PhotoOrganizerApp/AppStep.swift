import Foundation

/// アプリ全体の画面遷移状態。
///
/// 仕様通りの流れ: 権限確認 → manifest読込 → 照合 → レビュー → 最終確認 → 削除 → 結果表示
enum AppStep {
    case checkingPermission
    case permissionDenied
    case importManifest
    case matching
    case review
    case finalConfirm
    case deleting
    case result
}
