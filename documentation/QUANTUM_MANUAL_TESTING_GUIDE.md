# Quantum Password Generation - Manual Testing Guide

## Overview

This document provides step-by-step instructions for manually testing the Quantum Dice Password Generation feature.

---

## Prerequisites

1. **Backend Running**: Ensure Django backend is running on `localhost:8000`
2. **Frontend Running**: Ensure frontend is running on `localhost:5173`
3. **User Account**: Have a test user account ready
4. **API Keys (Optional)**: For premium providers:
   - `IBM_QUANTUM_TOKEN` for IBM Quantum
   - `IONQ_API_KEY` for IonQ Quantum

---

## Test Cases

### TC-001: Navigate to Password Generator

**Steps:**
1. Log in to the application
2. Navigate to Security > Password Generator

**Expected Result:**
- Password Generator page loads successfully
- Mode toggle (Standard/Quantum) is visible

**Pass Criteria:** ✅ Mode toggle displays "Standard" and "Quantum" options

---

### TC-002: Toggle to Quantum Mode

**Steps:**
1. From Password Generator page
2. Click "Quantum" mode toggle

**Expected Result:**
- Quantum mode activates
- Quantum Dice Button appears
- Pool status indicator visible (if enabled)
- Provider information displayed

**Pass Criteria:** ✅ UI updates to show quantum generation interface

---

### TC-003: Generate Quantum Password (Basic)

**Steps:**
1. Switch to Quantum mode
2. Set password length to 16
3. Enable all character types (uppercase, lowercase, numbers, symbols)
4. Click the Quantum Dice button

**Expected Result:**
- Loading animation plays
- Particle effects animate (dice spinning)
- Password is generated within 5-30 seconds
- Password displays in the password field
- "Quantum Certified" badge appears

**Pass Criteria:** ✅ Password generated, badge shows provider used

---

### TC-004: View Quantum Certificate

**Steps:**
1. Generate a quantum password (TC-003)
2. Click on the "Quantum Certified" badge

**Expected Result:**
- Certificate modal opens
- Displays:
  - Certificate ID (UUID format)
  - Provider (ANU QRNG / IBM Quantum / IonQ Quantum / Fallback)
  - Quantum Source description
  - Entropy Bits (should be length * 8 or more)
  - Generation Timestamp
  - Cryptographic Signature

**Pass Criteria:** ✅ All certificate fields populated correctly

---

### TC-005: Download Certificate

**Steps:**
1. Open certificate modal (TC-004)
2. Click "Download Certificate" button

**Expected Result:**
- JSON file downloads
- Filename format: `quantum-certificate-{id}.json`
- File contains valid JSON with all certificate fields

**Pass Criteria:** ✅ Valid JSON certificate downloads

---

### TC-006: Verify Certificate JSON Structure

**Steps:**
1. Download certificate (TC-005)
2. Open JSON file

**Expected Structure:**
```json
{
  "certificate_id": "uuid-here",
  "password_hash_prefix": "sha256:abcd1234...",
  "provider": "anu_qrng",
  "quantum_source": "vacuum_fluctuations",
  "entropy_bits": 128,
  "circuit_id": null,
  "generation_timestamp": "2026-01-16T12:00:00.000Z",
  "signature": "hmac-signature-here"
}
```

**Pass Criteria:** ✅ JSON matches expected structure

---

### TC-007: Password Length Customization

**Steps:**
1. Set length slider to 8 (minimum)
2. Generate quantum password
3. Verify password length is 8
4. Set length slider to 64
5. Generate quantum password
6. Verify password length is 64
7. Set length slider to 128 (maximum)
8. Generate quantum password
9. Verify password length is 128

**Pass Criteria:** ✅ All password lengths match slider values

---

### TC-008: Character Type Options

**Test Case A - Uppercase Only:**
1. Disable all except Uppercase
2. Generate quantum password
3. Verify: Password contains ONLY A-Z characters

**Test Case B - Numbers Only:**
1. Disable all except Numbers
2. Generate quantum password
3. Verify: Password contains ONLY 0-9 characters

**Test Case C - All Characters:**
1. Enable all options
2. Generate quantum password
3. Verify: Password may contain uppercase, lowercase, numbers, and symbols

**Pass Criteria:** ✅ Generated passwords respect character type settings

---

### TC-009: Copy Password to Clipboard

**Steps:**
1. Generate a quantum password
2. Click the "Copy" button

**Expected Result:**
- Copy success notification appears
- Password is in clipboard
- Can paste password elsewhere

**Pass Criteria:** ✅ Password copies successfully

---

### TC-010: Pool Status Display

**Steps:**
1. Switch to Quantum mode
2. Observe pool status indicator

**Expected Result:**
- Pool health displays (Good/Low/Critical)
- Available bytes shown
- Active provider indicated

**Pass Criteria:** ✅ Pool status reflects actual quantum entropy pool state

---

### TC-011: Provider Priority Testing

**Steps:**
1. Generate 10 quantum passwords
2. Note the provider for each (from certificate)

**Expected Behavior:**
- ANU QRNG should be primary (if no API outages)
- IBM Quantum used if configured and ANU fails
- IonQ Quantum used if configured and others fail
- Fallback only if all quantum sources unavailable

**Pass Criteria:** ✅ Provider follows priority: ANU > IBM > IonQ > Fallback

---

### TC-012: Error Handling - Network Failure

**Steps:**
1. Disconnect from network / Block API requests
2. Attempt to generate quantum password

**Expected Result:**
- Error message displays
- UI does not crash
- User can retry after reconnecting

**Pass Criteria:** ✅ Graceful error handling

---

### TC-013: Error Handling - API Timeout

**Steps:**
1. If possible, simulate slow API response
2. Attempt to generate quantum password
3. Wait for timeout

**Expected Result:**
- Loading indicator shows during wait
- Timeout error message appears after reasonable time
- Fallback to cryptographic RNG may occur

**Pass Criteria:** ✅ Application handles timeouts gracefully

---

### TC-014: Multiple Password Generation

**Steps:**
1. Generate 5 passwords in sequence
2. Record each password

**Expected Result:**
- All 5 passwords are unique
- Each has its own certificate
- Performance remains acceptable

**Pass Criteria:** ✅ All passwords unique, no duplicates

---

### TC-015: Certificate Listing (API)

**Steps:**
1. Generate 3 quantum passwords with `save_certificate: true`
2. Navigate to Security settings or use API:
   - `GET /api/security/quantum/certificates/`

**Expected Result:**
- All 3 certificates appear in the list
- Ordered by generation timestamp (newest first)
- Contains essential details

**Pass Criteria:** ✅ Certificates saved and retrievable

---

### TC-016: Certificate Retrieval (API)

**Steps:**
1. Get a certificate ID from TC-015
2. Call API: `GET /api/security/quantum/certificate/{id}/`

**Expected Result:**
- Full certificate details returned
- Matches the generated certificate

**Pass Criteria:** ✅ Individual certificate retrievable by ID

---

### TC-017: Raw Random Bytes Endpoint

**Steps:**
1. Call API: `GET /api/security/quantum/random-bytes/?count=32&format=hex`

**Expected Result:**
- Returns 64 hex characters (32 bytes)
- Provider field indicates source

**Steps:**
2. Call API: `GET /api/security/quantum/random-bytes/?count=32&format=base64`

**Expected Result:**
- Returns base64 encoded string
- ~44 characters for 32 bytes

**Pass Criteria:** ✅ Both hex and base64 formats work correctly

---

### TC-018: Pool Status Endpoint

**Steps:**
1. Call API: `GET /api/security/quantum/pool-status/`

**Expected Result:**
```json
{
  "success": true,
  "pool": {
    "total_bytes_available": <number>,
    "batch_count": <number>,
    "health": "good|low|critical",
    "min_pool_size": 1024,
    "max_pool_size": 4096
  },
  "providers": {
    "anu_qrng": { "available": true, "description": "...", "source": "..." },
    "ibm_quantum": { "available": false, "description": "...", "source": "..." },
    "ionq_quantum": { "available": false, "description": "...", "source": "..." }
  }
}
```

**Pass Criteria:** ✅ Pool status and provider availability returned

---

### TC-019: Authentication Required

**Steps:**
1. Log out of the application
2. Try to call quantum API endpoints without authentication

**Expected Result:**
- All endpoints return 401 Unauthorized
- No quantum passwords generated without auth

**Pass Criteria:** ✅ All endpoints require authentication

---

### TC-020: Mobile Responsiveness

**Steps:**
1. Open Password Generator on mobile device or browser dev tools mobile view
2. Switch to Quantum mode
3. Generate password
4. View certificate

**Expected Result:**
- All UI elements accessible on mobile
- Quantum dice button clickable
- Certificate modal readable
- No horizontal scrolling

**Pass Criteria:** ✅ Feature fully functional on mobile

---

## Performance Benchmarks

| Metric | Target | Actual |
|--------|--------|--------|
| Password generation (ANU) | < 5s | ____ |
| Password generation (Fallback) | < 1s | ____ |
| Certificate modal load | < 500ms | ____ |
| Pool status fetch | < 2s | ____ |
| Certificate download | < 1s | ____ |

---

## Test Environment

| Component | Version |
|-----------|---------|
| Browser | Chrome ___ / Firefox ___ / Safari ___ |
| OS | Windows / macOS / Linux |
| Backend | Django 5.0 |
| Frontend | React 18 / Vite |
| Test Date | __________ |
| Tester | __________ |

---

## Test Summary

| Category | Passed | Failed | Blocked | Total |
|----------|--------|--------|---------|-------|
| Basic Functionality | __ | __ | __ | 10 |
| API Endpoints | __ | __ | __ | 6 |
| Error Handling | __ | __ | __ | 2 |
| Security | __ | __ | __ | 1 |
| Responsiveness | __ | __ | __ | 1 |
| **Total** | __ | __ | __ | **20** |

---

## Known Issues / Notes

1. _____________________________________________
2. _____________________________________________
3. _____________________________________________

---

## Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Tester | | | |
| Developer | | | |
| Reviewer | | | |
