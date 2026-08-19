import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = PhotoOrganizerViewModel()

    var body: some View {
        NavigationStack {
            Group {
                switch viewModel.step {
                case .checkingPermission:
                    PermissionView(viewModel: viewModel)
                case .permissionDenied:
                    PermissionDeniedView(viewModel: viewModel)
                case .importManifest:
                    ManifestImportView(viewModel: viewModel)
                case .matching:
                    MatchingProgressView(viewModel: viewModel)
                case .review:
                    DeleteReviewView(viewModel: viewModel)
                case .finalConfirm:
                    FinalConfirmationView(viewModel: viewModel)
                case .deleting:
                    ProgressView("削除しています...")
                        .padding()
                case .result:
                    DeletionResultView(viewModel: viewModel)
                }
            }
            .navigationTitle("写真・動画の整理")
        }
        .onAppear { viewModel.checkPermission() }
    }
}

#Preview {
    ContentView()
}
