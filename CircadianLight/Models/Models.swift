import Foundation

// MARK: - Health Features

/// Health data features extracted from HealthKit
struct HealthFeatures: Codable {
    let hrvMilliseconds: Double
    let sleepHours: Double
    let stepCount: Int
    let timestamp: Date

    init(
        hrvMilliseconds: Double,
        sleepHours: Double,
        stepCount: Int,
        timestamp: Date = Date()
    ) {
        self.hrvMilliseconds = hrvMilliseconds
        self.sleepHours = sleepHours
        self.stepCount = stepCount
        self.timestamp = timestamp
    }

    // Map Swift camelCase to Python snake_case for API requests
    enum CodingKeys: String, CodingKey {
        case hrvMilliseconds = "hrv_ms"
        case sleepHours = "sleep_hours"
        case stepCount = "step_count"
        // timestamp is not sent to backend (client-only field)
    }

    // Custom encoding to exclude timestamp
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(hrvMilliseconds, forKey: .hrvMilliseconds)
        try container.encode(sleepHours, forKey: .sleepHours)
        try container.encode(stepCount, forKey: .stepCount)
    }

    // Custom decoding to handle missing timestamp from backend
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        hrvMilliseconds = try container.decode(Double.self, forKey: .hrvMilliseconds)
        sleepHours = try container.decode(Double.self, forKey: .sleepHours)
        stepCount = try container.decode(Int.self, forKey: .stepCount)
        timestamp = Date() // Set to current time when decoding
    }
}

// MARK: - Lighting Recommendation

/// Lighting recommendation returned from backend API
struct LightingRecommendation: Codable, Identifiable {
    let id: String
    let colorTemperature: Int // Kelvin (2000-6500)
    let brightness: Int // Percentage (0-100)
    let reasoning: String
    let timestamp: Date

    init(
        id: String = UUID().uuidString,
        colorTemperature: Int,
        brightness: Int,
        reasoning: String,
        timestamp: Date = Date()
    ) {
        self.id = id
        self.colorTemperature = colorTemperature
        self.brightness = brightness
        self.reasoning = reasoning
        self.timestamp = timestamp
    }

    // Map Swift camelCase to Python snake_case for API responses
    enum CodingKeys: String, CodingKey {
        case id = "recommendation_id"
        case colorTemperature = "color_temp_kelvin"
        case brightness = "brightness_percent"
        case reasoning
        case timestamp = "generated_at"
    }

    // Custom decoding to handle optional fields from backend
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // Backend returns optional recommendation_id, default to UUID if nil
        id = try container.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString

        colorTemperature = try container.decode(Int.self, forKey: .colorTemperature)
        brightness = try container.decode(Int.self, forKey: .brightness)
        reasoning = try container.decode(String.self, forKey: .reasoning)

        // Backend returns optional ISO8601 datetime, default to now if nil
        if let isoDateString = try container.decodeIfPresent(String.self, forKey: .timestamp) {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            timestamp = formatter.date(from: isoDateString) ?? Date()
        } else {
            timestamp = Date()
        }
    }

    /// Returns a color representation for the temperature
    var colorDescription: String {
        switch colorTemperature {
        case 2000..<3000:
            return "Warm Orange"
        case 3000..<4000:
            return "Warm White"
        case 4000..<5000:
            return "Neutral White"
        case 5000..<6000:
            return "Cool White"
        default:
            return "Daylight"
        }
    }
}

// MARK: - Feedback

/// User feedback on lighting recommendation
/// Note: Encodable only - we send this to the backend but never decode it from JSON
struct LightingFeedback: Encodable {
    let recommendationId: String
    let rating: Int // 1-5
    let comment: String?
    let timestamp: Date

    init(
        recommendationId: String,
        rating: Int,
        comment: String? = nil,
        timestamp: Date = Date()
    ) {
        self.recommendationId = recommendationId
        self.rating = rating
        self.comment = comment
        self.timestamp = timestamp
    }

    // Map Swift camelCase to Python snake_case for API requests
    enum CodingKeys: String, CodingKey {
        case recommendationId = "recommendation_id"
        case rating
        case comment
        // timestamp is not sent to backend (client-only field)
    }

    // Custom encoding to exclude timestamp
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(recommendationId, forKey: .recommendationId)
        try container.encode(rating, forKey: .rating)
        try container.encodeIfPresent(comment, forKey: .comment)
    }
}

// MARK: - Feedback Response

/// Response from backend after submitting feedback
struct FeedbackResponse: Codable {
    let success: Bool
    let message: String
    let feedbackId: String?

    // Map Swift camelCase to Python snake_case
    enum CodingKeys: String, CodingKey {
        case success
        case message
        case feedbackId = "feedback_id"
    }
}
