import Foundation

/// Configuration for connecting to a Philips Hue bridge
struct HueConfig {
    let baseURL: URL      // e.g. http://<bridge-ip>/api/<username>
    let lightID: String   // e.g. "1"
}

/// Errors that can occur during Hue API operations
enum HueError: Error {
    case invalidURL
    case requestFailed(statusCode: Int)
    case network(Error)
    case encoding(Error)
    case unknown
}

/// Service for controlling Philips Hue smart lights via the Hue REST API
final class HueLightingService {

    // MARK: - Properties

    private let config: HueConfig
    private let urlSession: URLSession

    // MARK: - Initialization

    init(config: HueConfig,
         urlSession: URLSession = .shared) {
        self.config = config
        self.urlSession = urlSession
    }

    // MARK: - Public Methods

    /// Apply a lighting recommendation to the configured Hue light.
    /// - Parameter recommendation: The lighting recommendation to apply
    /// - Throws: HueError if the request fails
    func apply(recommendation: LightingRecommendation) async throws {
        // Skip network call if this is a localhost/development config
        if let host = config.baseURL.host, host == "localhost" || host == "127.0.0.1" {
            print("[Hue DEV] Skipping PUT to localhost. This is a placeholder config.")
            print("[Hue DEV] Would apply: \(recommendation.colorTemperature)K, \(recommendation.brightness)%")
            return
        }

        // 1) Convert Kelvin -> mireds (Hue ct)
        let ct = Self.kelvinToMireds(recommendation.colorTemperature)

        // 2) Convert brightness % (0–100) -> Hue bri (1–254)
        let bri = Self.percentToBri(recommendation.brightness)

        // 3) Build Hue lights/<id>/state URL
        guard let url = URL(string: "lights/\(config.lightID)/state", relativeTo: config.baseURL) else {
            throw HueError.invalidURL
        }

        // 4) Build JSON body that matches Hue's API
        let body: [String: Any] = [
            "on": true,
            "ct": ct,
            "bri": bri
        ]

        let data: Data
        do {
            data = try JSONSerialization.data(withJSONObject: body, options: [])
        } catch {
            throw HueError.encoding(error)
        }

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.httpBody = data
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 5.0  // 5 second timeout

        do {
            let (responseData, response) = try await urlSession.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw HueError.unknown
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                // Log response body for debugging
                if let responseBody = String(data: responseData, encoding: .utf8) {
                    print("[Hue Error] Non-2xx response (\(httpResponse.statusCode)): \(responseBody)")
                } else {
                    print("[Hue Error] Non-2xx response (\(httpResponse.statusCode)): Unable to decode response body")
                }
                throw HueError.requestFailed(statusCode: httpResponse.statusCode)
            }

            // Success - log for debugging
            print("[Hue Success] Applied lighting: \(recommendation.colorTemperature)K, \(recommendation.brightness)%")
        } catch {
            if let urlError = error as? URLError {
                throw HueError.network(urlError)
            }
            throw error
        }
    }

    // MARK: - Conversions

    /// Convert Kelvin to mireds and clamp to Hue's typical supported range (153–500).
    /// - Parameter kelvin: Color temperature in Kelvin (e.g., 2700–6500)
    /// - Returns: Color temperature in mireds (mired = 1,000,000 / kelvin)
    private static func kelvinToMireds(_ kelvin: Int) -> Int {
        guard kelvin > 0 else { return 300 }
        let raw = 1_000_000.0 / Double(kelvin)
        let mireds = Int(raw.rounded())
        return max(153, min(500, mireds))
    }

    /// Convert 0–100% brightness into Hue bri value (1–254).
    /// - Parameter percent: Brightness as percentage (0–100)
    /// - Returns: Hue brightness value (1–254)
    private static func percentToBri(_ percent: Int) -> Int {
        let clamped = max(0, min(100, percent))
        if clamped == 0 { return 1 }
        let bri = Int((Double(clamped) / 100.0 * 254.0).rounded())
        return max(1, min(254, bri))
    }
}
