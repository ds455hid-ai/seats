import SwiftUI
import UniformTypeIdentifiers

/// PC側で生成した delete_manifest.json を読み込む画面(仕様22)。
/// USB/SSD経由でiPhoneのFilesアプリに入れたファイルを選択する想定。
struct ManifestImportView: View {
    @ObservedObject var viewModel: PhotoOrganizerViewModel
    @State private var isPickerPresented = false

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "doc.badge.arrow.up")
                .font(.system(size: 60))
                .foregroundStyle(.blue)
            Text("削除候補リストを読み込む")
                .font(.title2).bold()
            Text("PC側アプリで生成した delete_manifest.json をFilesアプリに保存してから、下のボタンで選択してください。")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .padding(.horizontal)

            if let errorMessage = viewModel.errorMessage {
                Text(errorMessage)
                    .foregroundStyle(.red)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }

            Button("manifestファイルを選択") {
                isPickerPresented = true
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
        }
        .padding()
        .fileImporter(
            isPresented: $isPickerPresented,
            allowedContentTypes: [.json],
            allowsMultipleSelection: false
        ) { result in
            switch result {
            case .success(let urls):
                if let url = urls.first {
                    viewModel.loadManifest(from: url)
                }
            case .failure(let error):
                viewModel.errorMessage = "ファイル選択に失敗しました: \(error.localizedDescription)"
            }
        }
    }
}

/// 照合処理中の進捗表示。
struct MatchingProgressView: View {
    @ObservedObject var viewModel: PhotoOrganizerViewModel

    var body: some View {
        VStack(spacing: 16) {
            ProgressView()
            Text(viewModel.matchingProgressText)
                .foregroundStyle(.secondary)
            Text("写真の枚数によっては数分かかる場合があります")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
        .padding()
    }
}
