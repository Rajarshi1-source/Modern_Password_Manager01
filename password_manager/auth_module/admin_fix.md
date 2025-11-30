# Admin.py Fixes Required

## Issues Found:

### 1. BehavioralBiometricsAdmin
- `'typing_patterns'` → Should be `'keystroke_dynamics'`
- `'login_frequency_pattern'` → Does NOT exist (remove)
- `'mouse_movement_patterns'` → EXISTS (keep)

### 2. GuardianApprovalAdmin
- `'approved_at'` → Should be `'responded_at'`
- `'created_at'` → Should be `'requested_at'`
- `'requires_video_call'` → Model doesn't have this field (use method instead)

### 3. PasskeyRecoverySetupAdmin
- `'kyber_public_key_encrypted'` → Does NOT exist (remove)

### 4. RecoveryAttemptAdmin
- Score fields (`device_recognition_score`, `behavioral_match_score`, etc.) → Do NOT exist (remove)
- `'forensic_log'` → Does NOT exist (remove)

### 5. RecoveryGuardianAdmin
- `'kyber_public_key'` → Should be `'guardian_public_key'`

### 6. RecoveryShardAdmin
- `'status'` → Does NOT exist (remove from list_display and list_filter)

### 7. TemporalChallengeAdmin
- `'scheduled_for'` → Does NOT exist, use `'expected_response_time_window_start'` instead
- `'is_correct'` → Should be `'response_correct'`
- `'responded_at'` → Should be `'response_received_at'`

