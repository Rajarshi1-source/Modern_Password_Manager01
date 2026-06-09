# 🧬 Epigenetic Password Adaptation

## Overview

The Epigenetic Password Adaptation feature uses reinforcement learning and behavioral biometrics to suggest password modifications that are easier for you to remember and type, while maintaining strong security.

## Privacy Guarantees

| Guarantee | Description |
|-----------|-------------|
| **Zero-knowledge (v2)** | The raw password never leaves the device. The client sends only a keyed HMAC fingerprint + coarse features (length bucket, bucketized timings) and masked previews; the server rejects any plaintext field (HTTP 422). |
| **Client-side suggestions** | Suggestions are generated in the browser from a downloaded preference model — the server never scores a raw password. |
| **No raw keystrokes stored** | Only aggregated timing metrics |
| **Differential privacy** | All metrics have ε-DP protection (ε=0.5) |
| **Opt-in by default** | Feature must be explicitly enabled |
| **Transparent** | Full visibility into what data is collected |
| **GDPR compliant** | Export and delete your data anytime |

## Getting Started

### 1. Enable Typing Pattern Capture

```javascript
// Frontend
import { adaptivePasswordService } from './services/adaptivePasswordService';

// Enable with consent
await adaptivePasswordService.enable({
  frequencyDays: 30,
  allowCentralized: true,
  allowFederated: false,
});
```

### 2. Use Typing Pattern Input

```jsx
import { TypingPatternCapture } from './Components/security/TypingPatternCapture';

<TypingPatternCapture
  inputRef={passwordInputRef}
  enabled={userHasConsented}
  onPatternCaptured={handlePattern}
  // Zero-knowledge v2: inject a keyed-fingerprint fn; the raw password is used
  // only locally to derive the fingerprint and is never transmitted.
  fingerprint={(pw) => cryptoService.passwordFingerprint(pw, perUserSalt)}
/>
```

### 3. Review Suggestions

After 10+ typing sessions, the system will suggest adaptations:

```jsx
<AdaptivePasswordSuggestion
  adaptation={suggestion}
  onAccept={handleAccept}
  onReject={handleReject}
/>
```

## API Reference

### Configuration Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/config/` | GET | Get configuration |
| `/adaptive/enable/` | POST | Enable with consent |
| `/adaptive/disable/` | POST | Disable feature |

### Typing Session

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/record-session/` | POST | Record typing session (v2: keyed fingerprint + coarse features; raw password rejected) |

### Adaptation

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/preference-model/` | GET | Download the learned preference model (client generates suggestions locally) |
| `/adaptive/suggest/` | POST | **Deprecated (HTTP 410)** — server-side suggestion removed; use the preference-model pull instead |
| `/adaptive/apply/` | POST | Apply adaptation (v2: original/adapted fingerprints + substitution classes + masked previews; raw passwords rejected) |
| `/adaptive/rollback/` | POST | Rollback to previous |

### Profile & History

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/profile/` | GET | Get typing profile |
| `/adaptive/history/` | GET | Get adaptation history |
| `/adaptive/stats/` | GET | Get evolution stats |

### Feedback

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/feedback/` | POST | Submit feedback |
| `/adaptive/feedback/{id}/` | GET | Get feedback for adaptation |

### Data Management (GDPR)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/adaptive/data/` | DELETE | Delete all data |
| `/adaptive/export/` | GET | Export all data |

## Configuration

Settings in `settings.py`:

```python
ADAPTIVE_PASSWORD = {
    'ENABLED': True,
    'DEFAULT_OPT_IN': False,
    'SUGGESTION_FREQUENCY_DAYS': 30,
    'DIFFERENTIAL_PRIVACY_EPSILON': 0.5,
    'AUTO_APPLY_THRESHOLD': 0.9,
    'MAX_ROLLBACK_DEPTH': 10,
}
```

## Security

- All password data is encrypted end-to-end
- Suggestions are RL-powered with confidence scores
- Full rollback support for all changes
- Differential privacy on all aggregated metrics
