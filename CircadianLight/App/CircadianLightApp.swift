import SwiftUI

@main
struct CircadianLightApp: App {

    @StateObject private var viewModel = AppViewModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(viewModel)
        }
    }
}

/// Root view that handles navigation between app states
struct RootView: View {

    @EnvironmentObject var viewModel: AppViewModel

    var body: some View {
        switch viewModel.appState {
        case .onboarding:
            OnboardingView()
        case .authentication:
            AuthView()
        case .dashboard:
            DashboardView()
        }
    }
}

