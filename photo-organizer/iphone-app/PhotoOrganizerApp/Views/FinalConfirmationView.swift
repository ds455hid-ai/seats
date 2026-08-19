import Foundation
import SwiftUI

/// 最終確認画面(仕様38, 41)。
/// バックアップ確認と、削除件数・容量の最終表示を経てからでないと削除できない。
struct FinalConfirmationView: View {
    @ObservedObject var viewModel: PhotoOrganizerViewModel
    @State private var showDeleteAlert = false

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("最終確認")
                .font(.title2).bold()

            VStack(alignment: .leading, spacing: 8) {
                Text("選択した\(viewModel.deletableResults.count)件を写真ライブラリから削除します")
                    .font(.headline)
                Text("写真 \(viewModel.deletablePhotoCount)件")
                Text("動画 \(viewModel.deletableVideoCount)件")
                Text("推定削減容量 \(ByteCountFormatter.string(fromByteCount: viewModel.deletableTotalSize, countStyle: .file))")
            }
            .padding()
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))

            Toggle(isOn: $viewModel.backupConfirmed) {
                VStack(alignment: .leading) {
                    Text("バックアップ済みですか?").bold()
                    Text("SSD/PCへのバックアップが完了していることを確認してください。削除後は元に戻せません。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding()
            .background(Color(.secondarySystemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 12))

            Text("削除後、すぐに完全に消去されない場合があります。「最近削除した項目」からも完全に削除するには、写真アプリで確認してください。")
                .font(.footnote)
                .foregroundStyle(.secondary)

            Spacer()

            HStack {
                Button("戻る") { viewModel.backToReview() }
                    .buttonStyle(.bordered)
                Spacer()
                Button("削除を実行") { showDeleteAlert = true }
                    .buttonStyle(.borderedProminent)
                    .tint(.red)
                    .disabled(!viewModel.backupConfirmed || viewModel.deletableResults.isEmpty)
            }
        }
        .padding()
        .alert("本当に削除しますか?", isPresented: $showDeleteAlert) {
            Button("キャンセル", role: .cancel) {}
            Button("削除する", role: .destructive) {
                Task { await viewModel.executeDeletion() }
            }
        } message: {
            Text("選択した\(viewModel.deletableResults.count)件を写真ライブラリから削除します。この操作は取り消せません。")
        }
    }
}
