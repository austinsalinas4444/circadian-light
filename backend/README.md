# CircadianLight Backend API

FastAPI backend for personalized, biologically-aware circadian lighting recommendations.

## Quick Start

```bash
# Install dependencies
cd backend
python3 -m pip install -r requirements.txt

# Run the server
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **Base URL**: `http://localhost:8000`
- **Interactive API Docs**: `http://localhost:8000/docs`
- **Alternative Docs**: `http://localhost:8000/redoc`

## API Endpoints

### POST /api/v1/health-features

Generate a lighting recommendation based on health data.

**Request Body** (JSON):
```json
{
  "hrv_ms": 65.0,
  "sleep_hours": 7.5,
  "step_count": 8500,
  "local_hour": 14
}
```

**Response** (200 OK):
```json
{
  "recommendation_id": "rec_abc123",
  "color_temp_kelvin": 5200,
  "brightness_percent": 95,
  "reasoning": "Daytime focus: Bright, cooler light optimizes cognitive performance...",
  "generated_at": "2025-12-03T14:30:00.000Z"
}
```

### POST /api/v1/feedback

Submit user feedback on a recommendation.

**Request Body** (JSON):
```json
{
  "recommendation_id": "rec_abc123",
  "rating": 5,
  "comment": "Perfect lighting!"
}
```

**Response** (201 Created):
```json
{
  "success": true,
  "message": "Thank you for your feedback!",
  "feedback_id": "feedback_xyz789"
}
```

## Circadian Policy

The lighting recommendations use a 4-phase circadian model:

### Phase 1: Morning Ramp-Up (05:00-09:00)
- **Base**: 3500-4500K, 60-80% brightness
- **Goal**: Support natural cortisol rise and waking alertness
- **Adjustments**:
  - Poor sleep → Warmer, dimmer for gentle stimulation
  - Good sleep → Cooler, brighter for energy boost

### Phase 2: Focus (09:00-17:00)
- **Base**: 4500-5500K, 80-100% brightness
- **Goal**: Optimize cognitive performance and alertness
- **Adjustments**:
  - Low HRV → Slightly warmer to reduce stress
  - Strong HRV → Cooler, brighter for peak performance

### Phase 3: Wind-Down (17:00-21:00)
- **Base**: 2700-3200K, 40-60% brightness
- **Goal**: Reduce blue light, allow melatonin onset
- **Adjustments**:
  - Poor sleep/recovery → Extra warm and dim
  - High activity day → Additional dimming for recovery

### Phase 4: Night (21:00-05:00)
- **Base**: 1800-2400K, 10-30% brightness
- **Goal**: Preserve melatonin production, support sleep
- **Adjustments**:
  - Poor recovery → Minimal light exposure

## Health Metric Thresholds

- **Sleep Hours**:
  - Low: < 6.0 hours (triggers recovery mode)
  - Good: ≥ 8.0 hours (enables performance mode)
- **HRV (Heart Rate Variability)**:
  - Low: < 50 ms (suggests poor recovery)
  - Strong: ≥ 75 ms (indicates excellent recovery)
- **Activity Level**:
  - High: > 12,000 steps (triggers recovery support in evening)

## JSON Field Mapping

The API uses snake_case JSON fields that match the Swift iOS app's CodingKeys:

| Swift Property | JSON Field | Type |
|----------------|------------|------|
| `hrvMilliseconds` | `hrv_ms` | float |
| `sleepHours` | `sleep_hours` | float |
| `stepCount` | `step_count` | int |
| `colorTemperature` | `color_temp_kelvin` | int |
| `brightness` | `brightness_percent` | int |
| `id` | `recommendation_id` | string |
| `timestamp` | `generated_at` | ISO8601 string |
| `recommendationId` | `recommendation_id` | string |
| `feedbackId` | `feedback_id` | string |

## Project Structure

```
backend/
├── requirements.txt          # Python dependencies
├── README.md                # This file
└── app/
    ├── __init__.py
    ├── main.py              # FastAPI app entry point
    ├── models/
    │   ├── __init__.py
    │   ├── request_models.py    # Pydantic request models
    │   └── response_models.py   # Pydantic response models
    ├── services/
    │   ├── __init__.py
    │   └── circadian_policy.py  # Biologically-aware recommendation logic
    └── routers/
        ├── __init__.py
        └── lighting.py          # API endpoint handlers
```

## Development

The server runs in hot-reload mode by default, so changes to Python files will automatically restart the server.

To run without reload:
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Production Deployment

For production:
1. Update CORS origins in `app/main.py` to restrict to your iOS app's domain
2. Use a production ASGI server configuration
3. Add authentication/authorization if needed
4. Implement database storage for feedback (currently just logs to console)
5. Set up monitoring and logging

## iOS App Integration

The iOS app at `CircadianLight/Services/LightingAPIClient.swift` is already configured to connect to `http://localhost:8000`. No changes needed to the Swift code.
