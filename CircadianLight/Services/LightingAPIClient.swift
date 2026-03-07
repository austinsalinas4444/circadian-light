import Foundation

/// API client for communicating with the CircadianLight backend
class LightingAPIClient {

    private let baseURL = "http://192.168.1.230:8000"
    private let session: URLSession

    // MARK: - Error Types

    enum APIError: LocalizedError {
        case invalidURL
        case invalidResponse
        case httpError(statusCode: Int, message: String?)
        case decodingError(Error)
        case encodingError(Error)
        case networkError(Error)

        var errorDescription: String? {
            switch self {
            case .invalidURL:
                return "Invalid API URL"
            case .invalidResponse:
                return "Invalid response from server"
            case .httpError(let code, let message):
                return "Server error (\(code)): \(message ?? "Unknown error")"
            case .decodingError(let error):
                return "Failed to decode response: \(error.localizedDescription)"
            case .encodingError(let error):
                return "Failed to encode request: \(error.localizedDescription)"
            case .networkError(let error):
                return "Network error: \(error.localizedDescription)"
            }
        }
    }

    // MARK: - Initialization

    init(session: URLSession = .shared) {
        self.session = session
    }

    // MARK: - Public Methods

    /// Sends health features to the backend and receives lighting recommendation
    /// - Parameter features: Health data to send
    /// - Returns: Recommended lighting configuration
    /// - Throws: APIError if the request fails
    func sendHealthFeatures(_ features: HealthFeatures) async throws -> LightingRecommendation {
        guard let url = URL(string: "\(baseURL)/api/v1/health-features") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Encode health features to JSON
        let encoder = JSONEncoder()
        do {
            request.httpBody = try encoder.encode(features)
        } catch {
            throw APIError.encodingError(error)
        }

        // Perform network request
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.networkError(error)
        }

        // Validate HTTP response
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            let errorMessage = String(data: data, encoding: .utf8)
            throw APIError.httpError(statusCode: httpResponse.statusCode, message: errorMessage)
        }

        // Decode recommendation from response
        let decoder = JSONDecoder()
        do {
            let recommendation = try decoder.decode(LightingRecommendation.self, from: data)
            return recommendation
        } catch {
            throw APIError.decodingError(error)
        }
    }

    /// Sends user feedback about a lighting recommendation
    /// - Parameter feedback: User's rating and comments
    /// - Throws: APIError if the request fails
    func sendFeedback(_ feedback: LightingFeedback) async throws {
        guard let url = URL(string: "\(baseURL)/api/v1/feedback") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Encode feedback to JSON
        let encoder = JSONEncoder()
        do {
            request.httpBody = try encoder.encode(feedback)
        } catch {
            throw APIError.encodingError(error)
        }

        // Perform network request
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.networkError(error)
        }

        // Validate HTTP response
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            let errorMessage = String(data: data, encoding: .utf8)
            throw APIError.httpError(statusCode: httpResponse.statusCode, message: errorMessage)
        }

        // Optionally decode feedback response for logging
        let decoder = JSONDecoder()
        if let feedbackResponse = try? decoder.decode(FeedbackResponse.self, from: data) {
            print("✅ Feedback submitted: \(feedbackResponse.message)")
        }
    }

    /// Fetches user's lighting history
    /// - Returns: Array of past recommendations
    func fetchHistory() async throws -> [LightingRecommendation] {
        // Simulate network delay
        try await Task.sleep(nanoseconds: 800_000_000) // 0.8 seconds

        // Return mock history
        return [
            LightingRecommendation(
                colorTemperature: 6000,
                brightness: 100,
                reasoning: "Previous daytime recommendation",
                timestamp: Date().addingTimeInterval(-3600)
            ),
            LightingRecommendation(
                colorTemperature: 4000,
                brightness: 60,
                reasoning: "Previous evening recommendation",
                timestamp: Date().addingTimeInterval(-7200)
            )
        ]
    }
}
