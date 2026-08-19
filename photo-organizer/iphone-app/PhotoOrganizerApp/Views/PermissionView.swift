import SwiftUI
import UIKit

/// 写真ライブラリへのアクセス許可をリクエストする画面(仕様31)。
struct PermissionView: View {
    @ObservedObject var viewModel: PhotoOrganizerViewModel

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "photo.on.rectangle.angled")
                .font(.system(size: 60))
                .foregroundStyle(.blue)
            Text("写真・動画へのアクセスが必要です")
                .font(.title2).bold()
            Text("削除候補の写真・動画を安全に照合するため、写真ライブラリへの「フルアクセス」を許可してください。")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .padding(.horizontal)
            Button("アクセスを許可する") {
                Task { await viewModel.requestPermission() }
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
        }
        .padding()
    }
}

/// 権限が拒否された場合の案内画面(仕様31)。
struct PermissionDeniedView: View {
    @ObservedObject var viewModel: PhotoOrganizerViewModel

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 60))
                .foregroundStyle(.orange)
            Text("写真ライブラリへのアクセスが許可されていません")
                .font(.title2).bold()
            Text("設定アプリから「写真」→「フルアクセスを許可」に変更してください。限定アクセスの場合、選択されていない写真は削除候補にできません。")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .padding(.horizontal)
            Button("設定を開く") {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            }
            .buttonStyle(.borderedProminent)
            Button("再確認する") {
                viewModel.checkPermission()
            }
        }
        .padding()
    }
}
