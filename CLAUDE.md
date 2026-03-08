# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CircadianLight is an iOS 17+ app built with SwiftUI that provides personalized lighting recommendations based on health data. The app analyzes HealthKit metrics (HRV, sleep, steps) and uses a backend API to determine optimal color temperature and brightness for smart lighting throughout the day.

**Current Status**: Fully functional iOS app with real HealthKit integration + FastAPI backend with research-validated 6-phase circadian policy. HealthKit is implemented on iOS. WiZ bulb integration is the active lighting control for MVP. Supabase persistence layer and PyTorch ML infrastructure are implemented but optional (controlled by env vars). The app gracefully falls back to mock data when HealthKit is unavailable.

## Build Commands

### iOS App
```bash
# Open project in Xcode
open CircadianLight.xcodeproj

# Build from command line
xcodebuild -project CircadianLight.xcodeproj -scheme CircadianLight -sdk iphonesimulator -configuration Debug build

# Run tests (when tests are added)
xcodebuild test -project CircadianLight.xcodeproj -scheme CircadianLight -destination 'platform=iOS Simulator,name=iPhone 15'
```

### Backend API
```bash
# Install dependencies
cd backend
python3 -m pip install -r requirements.txt

# Run development server (hot-reload enabled)
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# API docs available at:
# - Interactive: http://localhost:8000/docs
# - Alternative: http://localhost:8000/redoc
```

**Note**: The iOS app expects the backend at `http://localhost:8000` (configured in `LightingAPIClient.swift:6`)

## Architecture

### Navigation Flow
The app uses a state machine pattern via `AppViewModel.AppState`:
1. **Onboarding** → Welcome screen with permissions overview
2. **Authentication** → Email/password or Sign in with Apple (mock)
3. **Dashboard** → Current lighting recommendation display

State transitions are managed by `AppViewModel` methods:
- `completeOnboarding()` → moves to authentication
- `completeAuthentication()` → moves to dashboard, triggers first recommendation fetch
- `logout()` → returns to onboarding

### Data Layer

**iOS Services** (`CircadianLight/Services/`):
- `HealthKitManager`: Real HealthKit integration that fetches HRV, sleep, and step data with graceful fallbacks to defaults when data is unavailable
- `MockHealthService`: Returns hardcoded HealthKit data (HRV: 65ms, Sleep: 7.5h, Steps: 8500) - used as fallback
- `LightingAPIClient`: Real HTTP client using URLSession with POST to `http://localhost:8000/api/v1/health-features` and `/api/v1/feedback`
- `HueLightingService`: Philips Hue integration that converts recommendations to Hue API format (Kelvin → mireds, brightness % → bri 1-254)

**iOS Models** (`CircadianLight/Models/Models.swift`):
- `HealthFeatures`: Codable struct with HRV, sleep hours, step count
- `LightingRecommendation`: Color temperature (Kelvin), brightness (%), reasoning text
- `LightingFeedback`: User rating/comment on recommendations
- `FeedbackResponse`: Backend response after submitting feedback
- Custom `CodingKeys` map Swift camelCase ↔ Python snake_case (e.g., `hrvMilliseconds` ↔ `hrv_ms`)

**Backend** (`backend/app/`):
- `services/circadian_policy.py`: 6-phase circadian model with recovery mode and research-validated thresholds
- `models/request_models.py`: Pydantic models for incoming health data (core + extended sleep/ML fields)
- `models/response_models.py`: Pydantic models for lighting recommendations and feedback (includes `recovery_mode`)
- `routers/lighting.py`: FastAPI endpoints with ML flag, policy fallback, and async Supabase persistence
- `db/supabase_client.py`: Supabase client initialization from env vars
- `db/schemas.py`: Pydantic models for Supabase tables (HealthSnapshot, LightingFeedback, UserSettings)
- `db/crud.py`: Async CRUD helpers wrapping the sync supabase-py client

**ML Infrastructure** (`backend/ml/`):
- `models/circadian_net.py`: CircadianNet PyTorch model (8→32→16→2)
- `preprocessing.py`: FeatureProcessor — z-score normalization, output denormalization
- `inference.py`: CircadianModelInference — lazy model loading, safe predict() with fallback
- `training/generate_labels.py`: Builds training_data.csv from health CSVs + policy labels
- `training/train.py`: Trains CircadianNet, saves to `ml/models/circadian_model.pt`

### UI Components

**Screens** (`CircadianLight/Screens/`):
- `OnboardingView`: Welcome + permission preview with `PermissionRow` components
- `AuthView`: Email/password form + Sign in with Apple button
- `DashboardView`: Main screen with `LightingRecommendationCard`, pull-to-refresh, error handling, and feedback buttons

**ViewModels** (`CircadianLight/ViewModels/`):
- `AppViewModel`: Main `@MainActor` `ObservableObject` managing app state, data fetching, and navigation
  - Includes Hue integration via `applyCurrentRecommendationToHue()` method
  - Handles HealthKit authorization and graceful fallback to mock data

## SwiftUI Patterns

- All async operations use Swift concurrency (`async/await`)
- `@EnvironmentObject` for dependency injection of `AppViewModel`
- `@Published` properties trigger view updates
- Preview providers in each view file for Xcode canvas

## Backend API Details

### 6-Phase Circadian Policy (`backend/app/services/circadian_policy.py`)

Phases are anchored to `WAKE_TIME` (default 8am) and `SLEEP_TIME` (default midnight = 24):

| Phase | Hours (default) | CCT | Brightness | Rationale |
|---|---|---|---|---|
| **night** | 00:00–06:59 | 2100K | 15% | Preserve melatonin / sleep quality |
| **wake_ramp** | 07:00–08:59 | 3000→5500K ramp | 50→80% ramp | Support cortisol rise |
| **morning** | 09:00–10:59 | 5500K | 90% | Peak circadian entrainment |
| **focus** | 11:00–16:59 | 5000K | 85% | Sustained cognitive performance |
| **transition** | 17:00–20:59 | 4500→3000K ramp | 70→50% ramp | Begin melatonin onset |
| **wind_down** | 21:00–23:59 | 2700→2200K ramp | 40→25% ramp | Sleep preparation |

**Health thresholds (research-validated):**
- `HRV_LOW = 40ms` — below: stress indicator
- `HRV_HIGH = 80ms` — above: excellent recovery
- `SLEEP_HOURS_LOW = 6h` — below: suboptimal quantity
- `SLEEP_SCORE_LOW = 70` — at/below: recovery mode triggers
- `ACTIVITY_HIGH = 12,000 steps` — above: high activity day

**Recovery mode** activates when `hrv < 40ms OR sleep_hours < 6h OR sleep_score ≤ 70`:
- Caps CCT at 3500K
- Multiplies brightness by 0.70
- Sets `recovery_mode: true` in response

**Normal health modulation:**
- Low HRV (40–60ms): −300K, −10% brightness
- Poor sleep (<6.5h): −200K, −15% brightness
- High activity (>12k steps) in transition/wind-down: −10% brightness

**`compute_sleep_score(sleep_hours, deep_sleep_pct, rem_sleep_pct, sleep_efficiency)`:**
```
score = (sleep_hours/8)*30 + (deep_sleep_pct/0.20)*25 + (rem_sleep_pct/0.25)*25 + sleep_efficiency*20
```
Returns 0–100, clamped.

### PyTorch Model Architecture

`CircadianNet` (8 → 32 → ReLU → 16 → ReLU → 2):
- **Input (8 features):** hrv_ms, sleep_hours, sleep_score, resting_hr, steps, active_energy, hour, day_of_week
- **Output (2 values):** cct_normalized, brightness_normalized (both in [0,1])
- **Training:** MSELoss, Adam lr=0.001, 100 epochs, 80/20 split
- **Activation in USE_ML_MODEL mode:** off by default (`USE_ML_MODEL=false`)

### Supabase Schema

Three tables (create in Supabase dashboard):

**`health_snapshots`**: user_id, timestamp, hrv_ms, sleep_hours, sleep_score, resting_hr, steps, active_energy

**`lighting_feedback`**: user_id, timestamp, recommended_cct, recommended_brightness, actual_cct, actual_brightness, rating (1-5), feedback_type (too_warm/too_cool/too_bright/too_dim/perfect)

**`user_settings`**: user_id, wake_time, sleep_time, bulb_ip

### Training Pipeline

```bash
cd backend
# 1. Generate policy-labelled training data from health CSVs
python -m ml.training.generate_labels
# → writes ml/training/training_data.csv

# 2. Train CircadianNet
python -m ml.training.train
# → writes ml/models/circadian_model.pt
# → prints MAE for CCT (K) and brightness (%) on validation set
```

See `backend/README.md` for full API documentation.

## HealthKit Integration

The app has a fully implemented `HealthKitManager` that:
- Requests authorization for HRV (heart rate variability SDNN), sleep analysis, and step count
- Queries recent data with intelligent defaults:
  - HRV: Averages last 10 readings from past 24 hours, defaults to 65ms
  - Sleep: Sums all sleep stages from last 24 hours, defaults to 7.5 hours
  - Steps: Cumulative count from midnight to now, defaults to 8500 steps
- Returns sensible defaults when HealthKit is unavailable (simulator) or data is missing
- Uses `@MainActor` for thread safety with SwiftUI

**Fallback Pattern**: The `AppViewModel.fetchRecommendation()` method tries real HealthKit data first, then falls back to `MockHealthService` if unavailable or unauthorized. This ensures the app works on simulators and devices without health data.

## WiZ Bulb Integration (MVP)

The backend controls a WiZ bulb directly over local UDP using `pywizlight`. This replaces Philips Hue as the active lighting control for MVP.

**How it works** (control flow): iOS app → POST `/api/v1/health-features` → Backend generates recommendation → Backend sends UDP command to WiZ bulb → Returns recommendation to iOS app.

`backend/app/services/wiz_lighting.py`:
- `WizLightingService.apply_recommendation(color_temp_kelvin, brightness_percent)` — async method
- Bulb IP is hardcoded to `192.168.1.48` (`BULB_IP` constant at top of file)
- Converts brightness: 0–100% → 0–255 for pywizlight's `PilotBuilder`
- Opens a connection, sends the command, then closes the connection each call

**Integration in router**: After `policy_service.generate_recommendation()` succeeds, the router calls `wiz_service.apply_recommendation()` in a `try/except`. Bulb errors are logged but do not fail the API response — the recommendation is always returned to the iOS app.

**Configuration**: To change the bulb IP, update `BULB_IP` in `backend/app/services/wiz_lighting.py`.

## Philips Hue Integration (iOS, inactive for MVP)

The iOS `HueLightingService` is fully implemented but not the active control path for MVP:
- Requires `HueConfig` with bridge base URL (e.g., `http://<bridge-ip>/api/<username>`) and light ID
- Converts recommendations to Hue API format:
  - Kelvin → mireds (1,000,000 / kelvin, clamped 153-500)
  - Brightness % (0-100) → Hue bri (1-254)
- Sends PUT requests to `lights/<id>/state` endpoint with `on`, `ct`, and `bri` fields
- Development mode: Detects localhost URLs and skips actual API calls (logs only)
- Error handling with custom `HueError` enum

## Error Handling & Resilience

The app follows a graceful degradation pattern:
1. **HealthKit unavailable** → Uses mock data (simulator, unsupported devices)
2. **HealthKit permission denied** → Falls back to mock data
3. **HealthKit query fails** → Returns sensible defaults (65ms HRV, 7.5h sleep, 8500 steps)
4. **Backend API error** → Shows error message, allows retry via pull-to-refresh
5. **WiZ bulb error** → Logs error, doesn't block recommendation display (API still returns recommendation)

## Key Files

**iOS App**:
- `CircadianLight/App/CircadianLightApp.swift` - App entry point with `@main`
- `CircadianLight/ViewModels/AppViewModel.swift` - Central state management with HealthKit and Hue integration
- `CircadianLight/Models/Models.swift` - All data models with API serialization
- `CircadianLight/Services/LightingAPIClient.swift` - HTTP client for backend communication
- `CircadianLight/Services/HealthKitManager.swift` - Real HealthKit integration with fallbacks
- `CircadianLight/Services/HueLightingService.swift` - Philips Hue API client
- `CircadianLight/Services/MockHealthService.swift` - Fallback mock data provider
- `CircadianLight/App/Info.plist` - Contains HealthKit usage descriptions

**Backend**:
- `backend/app/main.py` - FastAPI app entry point with CORS configuration
- `backend/app/services/circadian_policy.py` - 6-phase circadian policy with recovery mode
- `backend/app/routers/lighting.py` - API endpoints with ML flag + async Supabase persistence
- `backend/app/services/wiz_lighting.py` - WiZ bulb UDP control via pywizlight
- `backend/app/db/supabase_client.py` - Supabase client (requires SUPABASE_URL + SUPABASE_KEY)
- `backend/app/db/schemas.py` - Supabase table schemas (HealthSnapshot, LightingFeedback, UserSettings)
- `backend/app/db/crud.py` - Async CRUD helpers
- `backend/ml/models/circadian_net.py` - PyTorch CircadianNet architecture
- `backend/ml/preprocessing.py` - Feature normalization and output denormalization
- `backend/ml/inference.py` - Safe inference wrapper with policy fallback
- `backend/ml/training/generate_labels.py` - Build training_data.csv from health CSVs
- `backend/ml/training/train.py` - Train and save circadian_model.pt
- `backend/requirements.txt` - Python dependencies (fastapi, uvicorn, pydantic, pywizlight, torch, supabase, pandas, numpy)
- `backend/.env.example` - Environment variable template

## Development Notes

**iOS**:
- Minimum deployment target: iOS 17.0
- SwiftUI lifecycle (no SceneDelegate/AppDelegate)
- Portrait orientation only (configurable in project settings)
- Bundle ID: `com.circadianlight.app`
- Uses Swift concurrency (async/await) throughout
- HealthKit works on physical devices only (simulator will use mock data)
- Hue integration requires physical Hue bridge and valid authentication token

**Backend**:
- Python 3.8+ required
- FastAPI with Pydantic v2 for request/response validation
- CORS enabled for localhost development
- Hot-reload enabled by default in development mode

## Testing Recommendations

**iOS App**:
- Test on physical device to verify real HealthKit data flow
- Test on simulator to verify mock data fallback works correctly
- Test backend connectivity by ensuring server is running before fetching recommendations
- Test Hue integration by configuring real bridge URL in `AppViewModel` initializer

**Backend**:
- Test all 6 circadian phases: `local_hour` values 2, 7, 9, 14, 18, 22
- Test recovery mode by sending `hrv_ms=35` or `sleep_hours=5`
- Test health modulation with intermediate HRV (45-60ms) and poor sleep (6.0-6.4h)
- Verify `recovery_mode: true` appears in response JSON when thresholds are breached
- Test Supabase persistence by setting SUPABASE_URL + SUPABASE_KEY and sending `user_id`
- Verify JSON field mapping matches Swift `CodingKeys` in `Models.swift`
- Test ML pipeline: run `generate_labels.py`, then `train.py`, set `USE_ML_MODEL=true`
