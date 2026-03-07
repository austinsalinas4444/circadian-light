import Foundation
import SwiftUI

/// Main application view model managing navigation and app state
@MainActor
class AppViewModel: ObservableObject {

    // MARK: - Published Properties

    @Published var appState: AppState = .onboarding
    @Published var currentRecommendation: LightingRecommendation?
    @Published var isLoading = false
    @Published var errorMessage: String?

    // MARK: - Services

    let healthKitManager = HealthKitManager()  // Public for access from OnboardingView
    private let healthService = MockHealthService()
    private let apiClient = LightingAPIClient()
    private let hueService: HueLightingService

    // MARK: - App State

    enum AppState {
        case onboarding
        case authentication
        case dashboard
    }

    // MARK: - Initialization

    init(hueService: HueLightingService? = nil) {
        if let hueService = hueService {
            self.hueService = hueService
        } else {
            // Temporary placeholder config for development
            let dummyURL = URL(string: "http://localhost:8000/api/dev-user")!
            let dummyConfig = HueConfig(baseURL: dummyURL, lightID: "1")
            self.hueService = HueLightingService(config: dummyConfig)
        }
    }

    // MARK: - Navigation Methods

    /// Completes onboarding and moves to authentication
    func completeOnboarding() {
        appState = .authentication
    }

    // MARK: - HealthKit Authorization

    /// Requests HealthKit access from the user
    /// Handles errors gracefully and logs the result
    func requestHealthKitAccess() async {
        do {
            try await healthKitManager.requestAuthorization()
            print("✅ HealthKit authorization granted")
        } catch {
            print("⚠️ HealthKit authorization failed: \(error.localizedDescription)")
            // Don't block the user experience - we'll fall back to mock data
        }
    }

    /// Completes authentication and moves to dashboard
    func completeAuthentication() {
        appState = .dashboard
        Task {
            await fetchRecommendation()
        }
    }

    /// Returns to onboarding (for testing/demo purposes)
    func logout() {
        appState = .onboarding
        currentRecommendation = nil
        errorMessage = nil
    }

    // MARK: - Data Fetching

    /// Fetches health data and gets lighting recommendation
    /// Tries HealthKit first, falls back to mock data if unavailable
    func fetchRecommendation() async {
        isLoading = true
        errorMessage = nil

        do {
            // Try to fetch real HealthKit data first
            let features: HealthFeatures

            if healthKitManager.isHealthKitAvailable() && healthKitManager.isAuthorized {
                do {
                    features = try await healthKitManager.fetchCurrentFeatures()
                    print("📊 Using real HealthKit data: HRV=\(features.hrvMilliseconds)ms, Sleep=\(features.sleepHours)h, Steps=\(features.stepCount)")
                } catch {
                    // Fall back to mock data if HealthKit fetch fails
                    print("⚠️ HealthKit fetch failed, using mock data: \(error.localizedDescription)")
                    features = try await healthService.fetchHealthFeatures()
                }
            } else {
                // HealthKit not available or not authorized - use mock data
                print("ℹ️ HealthKit not available/authorized, using mock data")
                features = try await healthService.fetchHealthFeatures()
            }

            // Get recommendation from API (real backend call)
            let recommendation = try await apiClient.sendHealthFeatures(features)

            currentRecommendation = recommendation
        } catch {
            errorMessage = "Failed to fetch recommendation: \(error.localizedDescription)"
        }

        isLoading = false
    }

    /// Submits feedback for current recommendation
    func submitFeedback(rating: Int, comment: String?) async throws {
        guard let recommendationId = currentRecommendation?.id else { return }

        let feedback = LightingFeedback(
            recommendationId: recommendationId,
            rating: rating,
            comment: comment
        )

        try await apiClient.sendFeedback(feedback)
    }

    /// Refreshes the current recommendation
    func refresh() async {
        await fetchRecommendation()
    }

    // MARK: - Hue Integration

    /// Applies the current lighting recommendation to the configured Hue light
    @MainActor
    func applyCurrentRecommendationToHue() async {
        guard let recommendation = currentRecommendation else {
            print("No current recommendation to apply to Hue.")
            return
        }

        do {
            try await hueService.apply(recommendation: recommendation)
            print("✅ Successfully applied recommendation to Hue.")
        } catch {
            print("❌ Failed to apply recommendation to Hue: \(error)")
        }
    }
}
