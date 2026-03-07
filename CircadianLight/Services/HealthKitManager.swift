import Foundation
import HealthKit

/// Manages HealthKit authorization and data fetching for CircadianLight
/// Falls back to sensible defaults when data is unavailable
@MainActor
class HealthKitManager: ObservableObject {

    // MARK: - Properties

    /// The HKHealthStore instance for querying health data
    private let healthStore = HKHealthStore()

    /// Published authorization status for UI updates
    @Published var isAuthorized = false

    // MARK: - HealthKit Availability

    /// Checks if HealthKit is available on this device
    /// - Returns: true if HealthKit is available (false on simulator or unsupported devices)
    func isHealthKitAvailable() -> Bool {
        return HKHealthStore.isHealthDataAvailable()
    }

    // MARK: - Authorization

    /// Requests authorization to read health data from HealthKit
    /// - Throws: Error if authorization request fails
    func requestAuthorization() async throws {
        // Check if HealthKit is available on this device
        guard isHealthKitAvailable() else {
            throw HealthKitError.notAvailable
        }

        // Define the health data types we want to read
        guard let hrvType = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN),
              let sleepType = HKCategoryType.categoryType(forIdentifier: .sleepAnalysis),
              let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount) else {
            throw HealthKitError.dataTypeNotAvailable
        }

        let readTypes: Set<HKObjectType> = [hrvType, sleepType, stepType]

        // Request authorization
        try await healthStore.requestAuthorization(toShare: [], read: readTypes)

        // Update authorization status
        isAuthorized = true
    }

    // MARK: - Data Fetching

    /// Fetches current health features from HealthKit
    /// - Returns: HealthFeatures populated with real HealthKit data or sensible defaults
    /// - Throws: Error if data fetching fails
    func fetchCurrentFeatures() async throws -> HealthFeatures {
        guard isHealthKitAvailable() else {
            throw HealthKitError.notAvailable
        }

        // Fetch each metric individually with error handling
        let hrvValue = await fetchRecentHRV() ?? 65.0  // Default: 65ms (reasonable average)
        let sleepHours = await fetchLastNightSleep() ?? 7.5  // Default: 7.5 hours
        let steps = await fetchTodaySteps() ?? 8500  // Default: 8500 steps

        return HealthFeatures(
            hrvMilliseconds: hrvValue,
            sleepHours: sleepHours,
            stepCount: steps,
            timestamp: Date()
        )
    }

    // MARK: - Private Helper Methods

    /// Fetches the most recent HRV reading from the last 24 hours
    /// - Returns: Average HRV in milliseconds, or nil if no data available
    private func fetchRecentHRV() async -> Double? {
        guard let hrvType = HKQuantityType.quantityType(forIdentifier: .heartRateVariabilitySDNN) else {
            return nil
        }

        // Query for HRV samples from the last 24 hours
        let now = Date()
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: now)!
        let predicate = HKQuery.predicateForSamples(withStart: yesterday, end: now, options: .strictStartDate)

        // Sort by most recent
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)

        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: hrvType,
                predicate: predicate,
                limit: 10,  // Get last 10 readings to compute average
                sortDescriptors: [sortDescriptor]
            ) { _, samples, error in
                guard error == nil,
                      let quantitySamples = samples as? [HKQuantitySample],
                      !quantitySamples.isEmpty else {
                    continuation.resume(returning: nil)
                    return
                }

                // Calculate average HRV from available samples
                let hrvUnit = HKUnit.secondUnit(with: .milli)
                let hrvValues = quantitySamples.map { $0.quantity.doubleValue(for: hrvUnit) }
                let averageHRV = hrvValues.reduce(0.0, +) / Double(hrvValues.count)

                continuation.resume(returning: averageHRV)
            }

            healthStore.execute(query)
        }
    }

    /// Fetches total sleep duration from the previous night
    /// - Returns: Total sleep hours, or nil if no data available
    private func fetchLastNightSleep() async -> Double? {
        guard let sleepType = HKCategoryType.categoryType(forIdentifier: .sleepAnalysis) else {
            return nil
        }

        // Query for sleep data from the last 24 hours
        let now = Date()
        let yesterday = Calendar.current.date(byAdding: .day, value: -1, to: now)!
        let predicate = HKQuery.predicateForSamples(withStart: yesterday, end: now, options: .strictStartDate)

        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: sleepType,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: nil
            ) { _, samples, error in
                guard error == nil,
                      let categorySamples = samples as? [HKCategorySample] else {
                    continuation.resume(returning: nil)
                    return
                }

                // Calculate total sleep time (only count asleep states)
                var totalSleepSeconds: TimeInterval = 0

                for sample in categorySamples {
                    // Only count "in bed asleep" or "asleep" states
                    if sample.value == HKCategoryValueSleepAnalysis.asleepUnspecified.rawValue ||
                       sample.value == HKCategoryValueSleepAnalysis.asleepCore.rawValue ||
                       sample.value == HKCategoryValueSleepAnalysis.asleepDeep.rawValue ||
                       sample.value == HKCategoryValueSleepAnalysis.asleepREM.rawValue {
                        totalSleepSeconds += sample.endDate.timeIntervalSince(sample.startDate)
                    }
                }

                // Convert seconds to hours
                let sleepHours = totalSleepSeconds / 3600.0

                // Return nil if no sleep data (0 hours)
                continuation.resume(returning: sleepHours > 0 ? sleepHours : nil)
            }

            healthStore.execute(query)
        }
    }

    /// Fetches total step count for today (from midnight to now)
    /// - Returns: Total steps today, or nil if no data available
    private func fetchTodaySteps() async -> Int? {
        guard let stepType = HKQuantityType.quantityType(forIdentifier: .stepCount) else {
            return nil
        }

        // Get today's date range (from midnight to now)
        let calendar = Calendar.current
        let now = Date()
        let startOfDay = calendar.startOfDay(for: now)
        let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: now, options: .strictStartDate)

        return await withCheckedContinuation { continuation in
            let query = HKStatisticsQuery(
                quantityType: stepType,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum
            ) { _, statistics, error in
                guard error == nil,
                      let sum = statistics?.sumQuantity() else {
                    continuation.resume(returning: nil)
                    return
                }

                let steps = Int(sum.doubleValue(for: .count()))
                continuation.resume(returning: steps)
            }

            healthStore.execute(query)
        }
    }
}

// MARK: - Error Types

/// Custom errors for HealthKit operations
enum HealthKitError: LocalizedError {
    case notAvailable
    case dataTypeNotAvailable
    case authorizationDenied

    var errorDescription: String? {
        switch self {
        case .notAvailable:
            return "HealthKit is not available on this device"
        case .dataTypeNotAvailable:
            return "Required health data types are not available"
        case .authorizationDenied:
            return "HealthKit authorization was denied"
        }
    }
}
