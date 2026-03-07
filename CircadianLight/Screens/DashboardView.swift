import SwiftUI

struct DashboardView: View {

    @EnvironmentObject var viewModel: AppViewModel
    @State private var showingFeedback = false
    @State private var isSubmittingFeedback = false
    @State private var feedbackMessage: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {

                    // Current Lighting Recommendation Card
                    if let recommendation = viewModel.currentRecommendation {
                        LightingRecommendationCard(recommendation: recommendation)

                        // Feedback Buttons
                        FeedbackButtonsView(
                            isSubmitting: $isSubmittingFeedback,
                            feedbackMessage: $feedbackMessage,
                            onFeedback: { rating, comment in
                                submitFeedback(rating: rating, comment: comment)
                            }
                        )
                    } else if viewModel.isLoading {
                        ProgressView("Loading recommendation...")
                            .frame(maxWidth: .infinity)
                            .padding(.top, 100)
                    } else {
                        EmptyStateView()
                    }

                    // Feedback Success/Error Message
                    if let message = feedbackMessage {
                        FeedbackMessageBanner(message: message)
                    }

                    // Error Message
                    if let error = viewModel.errorMessage {
                        ErrorBanner(message: error)
                    }

                    Spacer()
                }
                .padding()
            }
            .navigationTitle("CircadianLight")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: {
                        Task {
                            await viewModel.refresh()
                        }
                    }) {
                        Image(systemName: "arrow.clockwise")
                    }
                    .disabled(viewModel.isLoading)
                }

                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Logout") {
                        viewModel.logout()
                    }
                    .font(.subheadline)
                }
            }
            .refreshable {
                await viewModel.refresh()
            }
        }
    }

    // MARK: - Helper Methods

    /// Submits feedback to the backend
    private func submitFeedback(rating: Int, comment: String?) {
        isSubmittingFeedback = true
        feedbackMessage = nil

        Task {
            do {
                try await viewModel.submitFeedback(rating: rating, comment: comment)
                feedbackMessage = "✅ Feedback submitted successfully!"

                // Clear message after 3 seconds
                try await Task.sleep(nanoseconds: 3_000_000_000)
                feedbackMessage = nil
            } catch {
                feedbackMessage = "❌ Failed to submit feedback: \(error.localizedDescription)"
            }

            isSubmittingFeedback = false
        }
    }
}

// MARK: - Lighting Recommendation Card

struct LightingRecommendationCard: View {
    let recommendation: LightingRecommendation

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {

            // Header
            HStack {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(.yellow)
                    .font(.title2)

                Text("Current Recommendation")
                    .font(.headline)

                Spacer()

                Text(recommendation.timestamp, style: .time)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            Divider()

            // Color Temperature
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Color Temperature")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text(recommendation.colorDescription)
                        .font(.subheadline)
                        .fontWeight(.semibold)
                }

                Text("\(recommendation.colorTemperature)K")
                    .font(.title)
                    .fontWeight(.bold)

                // Color temperature visualization
                Rectangle()
                    .fill(temperatureGradient(for: recommendation.colorTemperature))
                    .frame(height: 8)
                    .cornerRadius(4)
            }

            // Brightness
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Brightness")
                        .font(.subheadline)
                        .foregroundColor(.secondary)
                    Spacer()
                    Text("\(recommendation.brightness)%")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                }

                GeometryReader { geometry in
                    ZStack(alignment: .leading) {
                        Rectangle()
                            .fill(Color.gray.opacity(0.2))

                        Rectangle()
                            .fill(Color.blue)
                            .frame(width: geometry.size.width * CGFloat(recommendation.brightness) / 100)
                    }
                }
                .frame(height: 8)
                .cornerRadius(4)
            }

            // Reasoning
            VStack(alignment: .leading, spacing: 8) {
                Text("Why?")
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                Text(recommendation.reasoning)
                    .font(.body)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 2)
    }

    private func temperatureGradient(for kelvin: Int) -> LinearGradient {
        let colors: [Color]
        switch kelvin {
        case ..<3000:
            colors = [.orange, .red.opacity(0.8)]
        case 3000..<4000:
            colors = [.yellow, .orange]
        case 4000..<5000:
            colors = [.white, .yellow]
        case 5000..<6000:
            colors = [.white, .cyan.opacity(0.5)]
        default:
            colors = [.cyan, .blue.opacity(0.5)]
        }
        return LinearGradient(colors: colors, startPoint: .leading, endPoint: .trailing)
    }
}

// MARK: - Empty State

struct EmptyStateView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "lightbulb.slash")
                .font(.system(size: 60))
                .foregroundColor(.gray)

            Text("No Recommendation Yet")
                .font(.title2)
                .fontWeight(.semibold)

            Text("Pull to refresh to get your personalized lighting recommendation")
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
        }
        .padding(.top, 100)
    }
}

// MARK: - Error Banner

struct ErrorBanner: View {
    let message: String

    var body: some View {
        HStack {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.red)

            Text(message)
                .font(.subheadline)
                .foregroundColor(.secondary)

            Spacer()
        }
        .padding()
        .background(Color.red.opacity(0.1))
        .cornerRadius(12)
    }
}

// MARK: - Feedback Buttons

struct FeedbackButtonsView: View {
    @Binding var isSubmitting: Bool
    @Binding var feedbackMessage: String?
    let onFeedback: (Int, String?) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("How's the recommendation?")
                .font(.headline)
                .padding(.horizontal)

            VStack(spacing: 12) {
                HStack(spacing: 12) {
                    FeedbackButton(
                        title: "Too Bright",
                        icon: "sun.max.fill",
                        color: .orange,
                        isSubmitting: isSubmitting
                    ) {
                        onFeedback(2, "Too bright")
                    }

                    FeedbackButton(
                        title: "Too Dim",
                        icon: "sun.min.fill",
                        color: .gray,
                        isSubmitting: isSubmitting
                    ) {
                        onFeedback(2, "Too dim")
                    }
                }

                HStack(spacing: 12) {
                    FeedbackButton(
                        title: "Too Warm",
                        icon: "flame.fill",
                        color: .red,
                        isSubmitting: isSubmitting
                    ) {
                        onFeedback(2, "Too warm")
                    }

                    FeedbackButton(
                        title: "Too Cool",
                        icon: "snowflake",
                        color: .blue,
                        isSubmitting: isSubmitting
                    ) {
                        onFeedback(2, "Too cool")
                    }
                }

                FeedbackButton(
                    title: "Perfect!",
                    icon: "checkmark.circle.fill",
                    color: .green,
                    isSubmitting: isSubmitting,
                    fullWidth: true
                ) {
                    onFeedback(5, "Perfect recommendation")
                }
            }
            .padding(.horizontal)
        }
        .padding(.vertical)
        .background(Color(.systemBackground))
        .cornerRadius(16)
        .shadow(color: .black.opacity(0.1), radius: 8, x: 0, y: 2)
    }
}

// MARK: - Individual Feedback Button

struct FeedbackButton: View {
    let title: String
    let icon: String
    let color: Color
    let isSubmitting: Bool
    var fullWidth: Bool = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack {
                Image(systemName: icon)
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.medium)
            }
            .frame(maxWidth: fullWidth ? .infinity : nil)
            .padding(.vertical, 12)
            .padding(.horizontal, 16)
            .background(color.opacity(0.15))
            .foregroundColor(color)
            .cornerRadius(10)
        }
        .disabled(isSubmitting)
        .opacity(isSubmitting ? 0.6 : 1.0)
    }
}

// MARK: - Feedback Message Banner

struct FeedbackMessageBanner: View {
    let message: String

    var body: some View {
        HStack {
            Text(message)
                .font(.subheadline)
                .foregroundColor(.primary)

            Spacer()
        }
        .padding()
        .background(Color.green.opacity(0.1))
        .cornerRadius(12)
    }
}

// MARK: - Preview

#Preview {
    @Previewable @State var viewModel: AppViewModel = {
        let vm = AppViewModel()
        vm.appState = .dashboard
        vm.currentRecommendation = LightingRecommendation(
            colorTemperature: 5500,
            brightness: 80,
            reasoning: "Morning light to support natural cortisol rise and alertness"
        )
        return vm
    }()

    DashboardView()
        .environmentObject(viewModel)
}
