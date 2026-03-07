import Foundation

/// Mock service for simulating HealthKit data retrieval
/// In production, this will be replaced with actual HealthKit queries
class MockHealthService {

    /// Fetches mock health features
    /// - Returns: Hardcoded HealthFeatures with sample data
    func fetchHealthFeatures() async throws -> HealthFeatures {
        // Simulate network/processing delay
        try await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds

        return HealthFeatures(
            hrvMilliseconds: 65.0,
            sleepHours: 7.5,
            stepCount: 8500
        )
    }

    /// Simulates checking HealthKit authorization status
    /// - Returns: Always returns true in mock implementation
    func isAuthorized() -> Bool {
        return true
    }

    /// Simulates requesting HealthKit authorization
    /// - Returns: Always returns true in mock implementation
    func requestAuthorization() async throws -> Bool {
        // Simulate authorization delay
        try await Task.sleep(nanoseconds: 1_000_000_000) // 1 second
        return true
    }
}
