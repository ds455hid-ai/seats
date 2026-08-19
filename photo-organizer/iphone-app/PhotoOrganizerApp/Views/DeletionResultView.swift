import SwiftUI

/// 削除結果表示(仕様39, 40)。
struct DeletionResultView: View {
    @ObservedObject var viewModel: PhotoOrganizerViewModel

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 60))
                .foregroundStyle(.green)
            Text("削除処理が完了しました")
                .font(.title2).bold()

            if let outcome = viewModel.deletionOutcome {
                VStack(alignment: .leading, spacing: 8) {
                    resultRow(label: "成功", value: outcome.successCount, color: .green)
                    resultRow(label: "失敗", value: outcome.failureCount, color: .red)
                    resultRow(label: "スキップ", value: outcome.skippedCount, color: .secondary)
                }
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            Text("削除した写真・動画は、しばらく「最近削除した項目」に残ります。ストレージ容量を完全に空けるには、写真アプリの「最近削除した項目」も確認して完全に削除してください。")
                .font(.footnote)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)

            Button("最初の画面に戻る") {
                viewModel.reset()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }

    private func resultRow(label: String, value: Int, color: Color) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text("\(value)件").bold().foregroundStyle(color)
        }
    }
}
