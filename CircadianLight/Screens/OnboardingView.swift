import SwiftUI

struct OnboardingView: View {

    @EnvironmentObject var viewModel: AppViewModel
    @State private var isRequestingHealthAccess = false
    @State private var healthAccessMessage: String?
    @State private var healthAccessGranted = false

    var body: some View {
        VStack(spacing: 30) {
            Spacer()

            // App Icon/Logo Area
            Image(systemName: "light.max")
                .font(.system(size: 80))
                .foregroundStyle(.blue.gradient)
                .padding(.bottom, 20)

            // Title
            Text("CircadianLight")
                .font(.largeTitle)
                .fontWeight(.bold)

            // Description
            Text("Optimize your lighting based on your body's natural rhythms")
                .font(.title3)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
                .padding(.horizontal, 40)

            Spacer()

            // Permissions Preview
            VStack(alignment: .leading, spacing: 16) {
                PermissionRow(
                    icon: "heart.fill",
                    title: "Health Data",
                    description: "We'll read your HRV, sleep, and activity data"
                )

                PermissionRow(
                    icon: "brain.head.profile",
                    title: "Smart Recommendations",
                    description: "AI-powered lighting suggestions for your wellbeing"
                )

                PermissionRow(
                    icon: "lightbulb.fill",
                    title: "Automated Control",
                    description: "Seamlessly adjust your smart lights throughout the day"
                )
            }
            .padding(.horizontal, 30)

            Spacer()

            // Health Data Connection Section
            VStack(spacing: 16) {
                // Connect Health Data Button
                Button(action: {
                    requestHealthAccess()
                }) {
                    HStack {
                        Image(systemName: healthAccessGranted ? "checkmark.circle.fill" : "heart.circle.fill")
                            .font(.title3)

                        Text(healthAccessGranted ? "Health Data Connected" : "Connect Health Data")
                            .font(.headline)

                        if isRequestingHealthAccess {
                            Spacer()
                            ProgressView()
                                .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        }
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding()
                    .background(healthAccessGranted ? Color.green : Color.blue)
                    .cornerRadius(12)
                }
                .disabled(isRequestingHealthAccess || healthAccessGranted)
                .padding(.horizontal, 30)

                // Feedback message
                if let message = healthAccessMessage {
                    Text(message)
                        .font(.caption)
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 30)
                }

                // Continue Button
                Button(action: {
                    viewModel.completeOnboarding()
                }) {
                    Text("Get Started")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.blue.opacity(0.8))
                        .cornerRadius(12)
                }
                .padding(.horizontal, 30)
            }
            .padding(.bottom, 40)
        }
    }

    // MARK: - Helper Methods

    /// Requests HealthKit access and updates UI accordingly
    private func requestHealthAccess() {
        isRequestingHealthAccess = true
        healthAccessMessage = nil

        Task {
            await viewModel.requestHealthKitAccess()

            // Update UI based on result
            // Note: We check if authorization was granted by seeing if HealthKit is now authorized
            await MainActor.run {
                // Give a small delay for the authorization sheet to complete
                Task {
                    try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds

                    isRequestingHealthAccess = false

                    // Check if access was granted
                    if viewModel.healthKitManager.isAuthorized {
                        healthAccessGranted = true
                        healthAccessMessage = "✓ Health data access granted! We'll use your real health metrics."
                    } else {
                        healthAccessMessage = "Health data access is optional. We'll use sample data instead."
                    }
                }
            }
        }
    }
}

// MARK: - Permission Row Component

struct PermissionRow: View {
    let icon: String
    let title: String
    let description: String

    var body: some View {
        HStack(alignment: .top, spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.blue)
                .frame(width: 30)

            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)

                Text(description)
                    .font(.subheadline)
                    .foregroundColor(.secondary)
            }
        }
    }
}

// MARK: - Preview

#Preview {
    OnboardingView()
        .environmentObject(AppViewModel())
}
