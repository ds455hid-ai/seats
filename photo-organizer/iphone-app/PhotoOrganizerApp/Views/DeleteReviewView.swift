import Foundation
import SwiftUI
import PhotoOrganizerCore

/// 削除候補一覧表示(仕様25, 37)。
/// AMBIGUOUS/NOT_FOUNDは自動的に削除対象から除外され、選択すらできない(仕様36の徹底)。
struct DeleteReviewView: View {
    @ObservedObject var viewModel: PhotoOrganizerViewModel

    var body: some View {
        List {
            Section {
                summaryCard
            }

            Section("削除候補(MATCHEDのみ選択可能)") {
                ForEach(matchedResults, id: \.manifestItem.mediaId) { result in
                    matchedRow(result)
                }
            }

            if !ambiguousOrNotFoundResults.isEmpty {
                Section("削除対象外(照合に確信が持てないため、安全のため除外)") {
                    ForEach(ambiguousOrNotFoundResults, id: \.manifestItem.mediaId) { result in
                        excludedRow(result)
                    }
                }
            }
        }
        .safeAreaInset(edge: .bottom) {
            Button("この内容で確認画面へ進む") {
                viewModel.proceedToFinalConfirm()
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(viewModel.deletableResults.isEmpty)
            .padding()
            .background(.bar)
        }
    }

    private var matchedResults: [MatchResult] {
        viewModel.matchResults.filter { $0.status == .matched }
    }

    private var ambiguousOrNotFoundResults: [MatchResult] {
        viewModel.matchResults.filter { $0.status != .matched }
    }

    private var summaryCard: some View {
        let summary = viewModel.summary
        return VStack(alignment: .leading, spacing: 8) {
            Text("削除候補").font(.headline)
            HStack {
                statBlock(label: "写真", value: "\(viewModel.deletablePhotoCount)件")
                statBlock(label: "動画", value: "\(viewModel.deletableVideoCount)件")
                statBlock(label: "削減予定", value: formattedSize(viewModel.deletableTotalSize))
            }
            Divider()
            HStack {
                statBlock(label: "MATCHED", value: "\(summary.matchedCount)件", color: .green)
                statBlock(label: "AMBIGUOUS", value: "\(summary.ambiguousCount)件", color: .orange)
                statBlock(label: "NOT_FOUND", value: "\(summary.notFoundCount)件", color: .red)
            }
        }
        .padding(.vertical, 8)
    }

    private func statBlock(label: String, value: String, color: Color = .primary) -> some View {
        VStack(alignment: .leading) {
            Text(label).font(.caption).foregroundStyle(.secondary)
            Text(value).font(.title3).bold().foregroundStyle(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func matchedRow(_ result: MatchResult) -> some View {
        let isExcluded = viewModel.excludedMediaIds.contains(result.manifestItem.mediaId)
        return Button {
            viewModel.toggleExclude(mediaId: result.manifestItem.mediaId)
        } label: {
            HStack {
                Image(systemName: isExcluded ? "square" : "checkmark.square.fill")
                    .foregroundStyle(isExcluded ? .secondary : .blue)
                VStack(alignment: .leading) {
                    Text(result.manifestItem.fileName)
                    Text("\(formattedSize(result.manifestItem.fileSize)) ・ 一致理由: \(result.reason)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .foregroundStyle(.primary)
    }

    private func excludedRow(_ result: MatchResult) -> some View {
        HStack {
            Text(result.status == .ambiguous ? "AMBIGUOUS" : "NOT_FOUND")
                .font(.caption).bold()
                .foregroundStyle(result.status == .ambiguous ? .orange : .red)
            VStack(alignment: .leading) {
                Text(result.manifestItem.fileName)
                Text(result.reason).font(.caption).foregroundStyle(.secondary)
            }
        }
    }

    private func formattedSize(_ bytes: Int64) -> String {
        ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)
    }
}
