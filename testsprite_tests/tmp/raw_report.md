
# TestSprite AI Testing Report(MCP)

---

## 1️⃣ Document Metadata
- **Project Name:** Password_manager
- **Date:** 2025-11-28
- **Prepared by:** TestSprite AI Team

---

## 2️⃣ Requirement Validation Summary

#### Test TC001
- **Test Name:** User Registration with Email and Password Setup
- **Test Code:** [TC001_User_Registration_with_Email_and_Password_Setup.py](./TC001_User_Registration_with_Email_and_Password_Setup.py)
- **Test Error:** The registration process could not be completed because the page unexpectedly navigated back to the login screen after entering a valid email. Password input was not possible, blocking further progress. This is a critical issue preventing user registration verification. Please investigate and fix the navigation and input issues on the registration page.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0984200DC3F0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A06C4200DC3F0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/77e001c1-44c2-4d1b-b1e2-7ebf81dfbe68
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC002
- **Test Name:** Login with Password and TOTP Multi-Factor Authentication
- **Test Code:** [TC002_Login_with_Password_and_TOTP_Multi_Factor_Authentication.py](./TC002_Login_with_Password_and_TOTP_Multi_Factor_Authentication.py)
- **Test Error:** The login process with email and password followed by TOTP-based MFA could not be fully tested due to a blocking issue: after submitting valid login credentials, the page reloads to the login form without any error message or MFA challenge. This prevents verification of successful login, MFA enforcement, and zero-knowledge authentication. The issue has been reported. Task is stopped.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A02C3B00F4350000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A02C3B00F4350000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/5956a08b-23b4-4731-af58-3f86fdcc80c4
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC003
- **Test Name:** Passwordless Login using WebAuthn Passkey with Biometric Authentication
- **Test Code:** [TC003_Passwordless_Login_using_WebAuthn_Passkey_with_Biometric_Authentication.py](./TC003_Passwordless_Login_using_WebAuthn_Passkey_with_Biometric_Authentication.py)
- **Test Error:** Test failed: Unable to trigger passwordless WebAuthn login prompt using the 'Login with a Passkey' button. No biometric authentication prompt appeared, preventing further testing of passwordless login flow.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0583900043A0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0583900043A0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/792c4780-9016-4bde-acc1-6380261f1fe7
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC004
- **Test Name:** OAuth Social Login Flow with Google Provider
- **Test Code:** [TC004_OAuth_Social_Login_Flow_with_Google_Provider.py](./TC004_OAuth_Social_Login_Flow_with_Google_Provider.py)
- **Test Error:** Testing stopped due to inability to interact with the Google OAuth login button. The OAuth login process could not be initiated, preventing verification of login success and MFA enforcement.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0043A00EC0D0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0D83900EC0D0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/f38d1c90-2368-48d9-81f7-a9ef6e418fff
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC005
- **Test Name:** Master Password Key Derivation and Encryption Key Generation
- **Test Code:** [TC005_Master_Password_Key_Derivation_and_Encryption_Key_Generation.py](./TC005_Master_Password_Key_Derivation_and_Encryption_Key_Generation.py)
- **Test Error:** The master password input and login button interaction were tested multiple times. The form resets after clicking 'Login to Vault', indicating some client-side processing may occur. However, no visible client-side logs or network requests were observed to confirm that Argon2id KDF runs locally or that only a zero-knowledge hash is sent to the server. The page remains on the login form with no navigation or error messages. Due to lack of evidence from UI and network activity, the task to confirm client-side Argon2id KDF processing and zero-knowledge hash transmission cannot be completed successfully.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A06C39007C0E0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A09839007C0E0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/574eb69c-95bc-4a0c-8ff0-c2760c704fd6
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC006
- **Test Name:** Vault Item CRUD Operations with Client-Side Encryption
- **Test Code:** [TC006_Vault_Item_CRUD_Operations_with_Client_Side_Encryption.py](./TC006_Vault_Item_CRUD_Operations_with_Client_Side_Encryption.py)
- **Test Error:** Testing stopped due to critical issues: input fields do not accept text input and social login fails with a blank error page. Unable to proceed with vault item CRUD and encryption testing. Please fix these issues and retry.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A02C380014350000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A02C380014350000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/f77538ee-9799-4304-a8de-990230bae983
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC007
- **Test Name:** Password Generator Produces Secure and Strong Passwords with ML Feedback
- **Test Code:** [TC007_Password_Generator_Produces_Secure_and_Strong_Passwords_with_ML_Feedback.py](./TC007_Password_Generator_Produces_Secure_and_Strong_Passwords_with_ML_Feedback.py)
- **Test Error:** Testing stopped. The password generator interface could not be accessed or triggered from the sign-up or login pages. The button next to the password input field is missing or non-functional. Therefore, verification of cryptographically secure password generation and ML strength feedback could not be completed.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0C44A0084280000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A06C4A0084280000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/c7e27409-1405-48a2-8799-ae90fd0d75c1
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC008
- **Test Name:** Post-Quantum Cryptography Operations Using CRYSTALS-Kyber-768 Hybrid
- **Test Code:** [null](./null)
- **Test Error:** Test execution timed out after 15 minutes
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/139ba04f-808c-49cb-9d78-1761aa680af0
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC009
- **Test Name:** Fully Homomorphic Encryption for Encrypted Password Strength Checks
- **Test Code:** [TC009_Fully_Homomorphic_Encryption_for_Encrypted_Password_Strength_Checks.py](./TC009_Fully_Homomorphic_Encryption_for_Encrypted_Password_Strength_Checks.py)
- **Test Error:** Reported the website issue preventing submission of encrypted password data and server-side processing. Stopping further actions as the task cannot proceed without this functionality.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0D83C0064130000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0D83C0064130000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/8c0f1d3e-c371-4c12-b0a3-a13ab7c8c9cc
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC010
- **Test Name:** Real-Time Breach Alert via Dark Web Monitoring
- **Test Code:** [TC010_Real_Time_Breach_Alert_via_Dark_Web_Monitoring.py](./TC010_Real_Time_Breach_Alert_via_Dark_Web_Monitoring.py)
- **Test Error:** Unable to confirm real-time breach alerts and ML model functionality due to lack of valid login credentials and no public demo or test mode available. Multiple login attempts with different methods failed. Task stopped as further progress is blocked by authentication requirements.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0EC3A00DC1C0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0183B00DC1C0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/0a59db4b-1ffc-44ba-8f2f-6d7a0ccc6914
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC011
- **Test Name:** Behavioral DNA Capture and Recovery Verification
- **Test Code:** [TC011_Behavioral_DNA_Capture_and_Recovery_Verification.py](./TC011_Behavioral_DNA_Capture_and_Recovery_Verification.py)
- **Test Error:** Reported login issue blocking progression to behavioral biometrics challenges. Testing stopped as login is required to proceed.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A02C390094290000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0D8DB0094290000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/d93a11b9-ff66-4ad6-8fe4-9441065f0c0f
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC012
- **Test Name:** Session Auto-Lock and Device Trust Management
- **Test Code:** [TC012_Session_Auto_Lock_and_Device_Trust_Management.py](./TC012_Session_Auto_Lock_and_Device_Trust_Management.py)
- **Test Error:** Login attempts failed repeatedly with valid credentials. Unable to proceed with testing session auto-lock, key clearance, device trust scoring, and audit logging. Reporting this as a website issue and stopping further testing.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0EC3C00040D0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0EC3C00040D0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/8c607f7f-720b-4d2f-a2f4-279127e39cf6
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC013
- **Test Name:** Shared Folder Management with Role-Based Access Control
- **Test Code:** [TC013_Shared_Folder_Management_with_Role_Based_Access_Control.py](./TC013_Shared_Folder_Management_with_Role_Based_Access_Control.py)
- **Test Error:** Login failed repeatedly with valid credentials. The page does not navigate away from the login form and no error message is shown. Unable to proceed with testing folder creation, sharing, and role-based access management. Reporting this issue and stopping further actions.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0D8440014360000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A004450014360000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/03b78f3e-f481-426a-9edc-8a1733d0709a
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC014
- **Test Name:** Vault Data Synchronization Across Web, Mobile, Desktop, and Browser Extensions
- **Test Code:** [TC014_Vault_Data_Synchronization_Across_Web_Mobile_Desktop_and_Browser_Extensions.py](./TC014_Vault_Data_Synchronization_Across_Web_Mobile_Desktop_and_Browser_Extensions.py)
- **Test Error:** Login attempts on the web client failed using both email/password and passkey methods. The page remains stuck on the login form with no error messages or progress. This prevents any further testing of vault synchronization and UI consistency across platforms. Reporting this issue and stopping the test as the core functionality is blocked.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0983B008C000000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0983B008C000000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/3a4da485-7a2a-4a8f-bdc8-191260ef2fed
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC015
- **Test Name:** Encrypted Vault Export and Import Functionality
- **Test Code:** [TC015_Encrypted_Vault_Export_and_Import_Functionality.py](./TC015_Encrypted_Vault_Export_and_Import_Functionality.py)
- **Test Error:** Testing cannot proceed because the vault login page fails to load after login attempts, including Google login, resulting in a blank error page. The vault export and import functionality cannot be tested. Please resolve the loading issue before retrying.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0843E00BC040000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0583E00BC040000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/ac9da4cb-8f97-4124-99d5-0f91f3386aa1
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC016
- **Test Name:** Error Handling for Invalid Credentials and Network Failures
- **Test Code:** [TC016_Error_Handling_for_Invalid_Credentials_and_Network_Failures.py](./TC016_Error_Handling_for_Invalid_Credentials_and_Network_Failures.py)
- **Test Error:** Tested invalid login attempts successfully with appropriate validation and error messages. However, the system failed to simulate network disconnection during login, and no network error message was displayed. Further testing on network recovery is blocked. Reporting this issue and stopping the test.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0983A00EC2E0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_CONNECTION_CLOSED (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/analytics/events/:0:0)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0C43A00EC2E0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/65e35e54-7e84-43a7-9c9c-3242a3835abd
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC017
- **Test Name:** Guardians-Based Social Mesh Recovery Workflow
- **Test Code:** [TC017_Guardians_Based_Social_Mesh_Recovery_Workflow.py](./TC017_Guardians_Based_Social_Mesh_Recovery_Workflow.py)
- **Test Error:** The social mesh recovery test was executed through multiple recovery methods: Recovery Key, Email Recovery, and Behavioral Recovery. Initiation of recovery and sending guardian invitations were attempted, but errors and lack of confirmation of guardian acknowledgements were encountered. Behavioral Recovery was started to trigger temporal multi-day challenges, but no UI or system messages confirmed the status or required approvals for recovery completion. Thus, the test could not fully verify the entire social mesh recovery flow including guardian acknowledgements and temporal challenge responses. Further backend or UI enhancements may be needed to support full observability of these steps.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0043B00BC1B0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] styled-components: it looks like an unknown prop "active" is being sent through to the DOM, which will likely trigger a React console error. If you would like automatic filtering of unknown props, you can opt-into that behavior via `<StyleSheetManager shouldForwardProp={...}>` (connect an API like `@emotion/is-prop-valid`) or consider using transient props (`$` prefix for automatic filtering.) (at http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1189:286)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: Warning: Received `%s` for a non-boolean attribute…ite/deps/styled-components.js?v=6af68643:1144:32), metadata: Object, error: Error: Warning: Received `%s` for a non-boolean attribute `%s`.

If you want to write it to the DOM…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] Warning: Received `%s` for a non-boolean attribute `%s`.

If you want to write it to the DOM, pass a string instead: %s="%s" or %s={value.toString()}.%s true active active true active 
    at button
    at O2 (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1198:6)
    at div
    at O2 (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1198:6)
    at div
    at O2 (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1198:6)
    at div
    at O2 (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1198:6)
    at PasswordRecovery (http://localhost:5173/src/Components/auth/PasswordRecovery.jsx:213:20)
    at RenderedRoute (http://localhost:5173/node_modules/.vite/deps/react-router-dom.js?v=6af68643:6002:26)
    at Routes (http://localhost:5173/node_modules/.vite/deps/react-router-dom.js?v=6af68643:6792:3)
    at Suspense
    at BehavioralProvider (http://localhost:5173/src/contexts/BehavioralContext.jsx:35:38)
    at AccessibilityProvider (http://localhost:5173/src/contexts/AccessibilityContext.jsx:20:41)
    at ErrorBoundary (http://localhost:5173/src/Components/common/ErrorBoundary.jsx:163:5)
    at App (http://localhost:5173/src/App.jsx:778:88)
    at AuthProvider (http://localhost:5173/src/hooks/useAuth.jsx:122:32)
    at Router (http://localhost:5173/node_modules/.vite/deps/react-router-dom.js?v=6af68643:6735:13)
    at BrowserRouter (http://localhost:5173/node_modules/.vite/deps/react-router-dom.js?v=6af68643:9844:3)
    at ot (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1144:32) (at http://localhost:5173/src/services/errorTracker.js:62:32)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0AC3A00BC1B0000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/password-recovery:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] styled-components: it looks like an unknown prop "active" is being sent through to the DOM, which will likely trigger a React console error. If you would like automatic filtering of unknown props, you can opt-into that behavior via `<StyleSheetManager shouldForwardProp={...}>` (connect an API like `@emotion/is-prop-valid`) or consider using transient props (`$` prefix for automatic filtering.) (at http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1189:286)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: Warning: Received `%s` for a non-boolean attribute…ite/deps/styled-components.js?v=6af68643:1144:32), metadata: Object, error: Error: Warning: Received `%s` for a non-boolean attribute `%s`.

If you want to write it to the DOM…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] Warning: Received `%s` for a non-boolean attribute `%s`.

If you want to write it to the DOM, pass a string instead: %s="%s" or %s={value.toString()}.%s true active active true active 
    at button
    at O2 (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1198:6)
    at div
    at O2 (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1198:6)
    at div
    at O2 (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1198:6)
    at div
    at O2 (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1198:6)
    at PasswordRecovery (http://localhost:5173/src/Components/auth/PasswordRecovery.jsx:213:20)
    at RenderedRoute (http://localhost:5173/node_modules/.vite/deps/react-router-dom.js?v=6af68643:6002:26)
    at Routes (http://localhost:5173/node_modules/.vite/deps/react-router-dom.js?v=6af68643:6792:3)
    at Suspense
    at BehavioralProvider (http://localhost:5173/src/contexts/BehavioralContext.jsx:35:38)
    at AccessibilityProvider (http://localhost:5173/src/contexts/AccessibilityContext.jsx:20:41)
    at ErrorBoundary (http://localhost:5173/src/Components/common/ErrorBoundary.jsx:163:5)
    at App (http://localhost:5173/src/App.jsx:778:88)
    at AuthProvider (http://localhost:5173/src/hooks/useAuth.jsx:122:32)
    at Router (http://localhost:5173/node_modules/.vite/deps/react-router-dom.js?v=6af68643:6735:13)
    at BrowserRouter (http://localhost:5173/node_modules/.vite/deps/react-router-dom.js?v=6af68643:9844:3)
    at ot (http://localhost:5173/node_modules/.vite/deps/styled-components.js?v=6af68643:1144:32) (at http://localhost:5173/src/services/errorTracker.js:62:32)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/b4ce181e-c490-48c0-9156-7b0c74412a87
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC018
- **Test Name:** Security Dashboard Breach Alerts and Device Management
- **Test Code:** [TC018_Security_Dashboard_Breach_Alerts_and_Device_Management.py](./TC018_Security_Dashboard_Breach_Alerts_and_Device_Management.py)
- **Test Error:** Reported login failure issue preventing access to security dashboard. Cannot proceed with breach alert and device session management validation without successful login.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0583B005C290000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0583B005C290000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/5990ce94-3c1a-480f-ac66-70b882ec3d37
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC019
- **Test Name:** API Endpoint Verifies Encrypted Blob Handling and Metadata Only Queries
- **Test Code:** [TC019_API_Endpoint_Verifies_Encrypted_Blob_Handling_and_Metadata_Only_Queries.py](./TC019_API_Endpoint_Verifies_Encrypted_Blob_Handling_and_Metadata_Only_Queries.py)
- **Test Error:** Login to Vault button does not work as expected; login does not proceed and no error message is shown. Cannot test API endpoints for encrypted vault blobs or metadata-only queries. Stopping test.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0D83A0044390000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/analytics/events/:0:0)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0D83A0044390000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/b1fa9bbd-7288-4557-9f6a-05caddfb168f
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---

#### Test TC020
- **Test Name:** Performance Benchmark: Cache Hit Rate and API Latency Improvements
- **Test Code:** [TC020_Performance_Benchmark_Cache_Hit_Rate_and_API_Latency_Improvements.py](./TC020_Performance_Benchmark_Cache_Hit_Rate_and_API_Latency_Improvements.py)
- **Test Error:** Stopped testing due to login button being disabled despite valid credentials. Unable to proceed with caching and compression performance validation.
Browser Console Logs:
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0043B006C130000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [GroupMarkerNotSet(crbug.com/242999)!:A0D83A006C130000]Automatic fallback to software WebGL has been deprecated. Please use the --enable-unsafe-swiftshader flag to opt in to lower security guarantees for trusted content. (at http://localhost:5173/:0:0)
[WARNING] [Kyber] ⚠️ Kyber WASM not available: No Kyber implementation available (at http://localhost:5173/src/services/quantum/kyberService.js:131:14)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[WARNING] [Kyber] ⚠️ Using classical ECC fallback - NOT quantum-resistant! (at http://localhost:5173/src/App.jsx:801:20)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error, metadata: Object, error: Error: [A/B Testing] Failed to fetch experiments: AxiosError: Network Error
    at console.error (h…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [A/B Testing] Failed to fetch experiments: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/ab-testing/:0:0)
[WARNING] Failed to report error to backend: AxiosError (at http://localhost:5173/src/services/errorTracker.js:194:14)
[ERROR] Failed to load resource: net::ERR_SSL_PROTOCOL_ERROR (at https://127.0.0.1:8000/api/performance/frontend/:0:0)
[ERROR] [ErrorTracker] WARNING: {context: ConsoleError, message: [Analytics] Failed to send data: AxiosError: Network Error, metadata: Object, error: Error: [Analytics] Failed to send data: AxiosError: Network Error
    at console.error (http://loca…} (at http://localhost:5173/src/services/errorTracker.js:116:11)
[ERROR] [Analytics] Failed to send data: AxiosError (at http://localhost:5173/src/services/errorTracker.js:62:32)
- **Test Visualization and Result:** https://www.testsprite.com/dashboard/mcp/tests/9dbfa971-8827-419d-b267-34ea16b5df55/83c1ca32-7eab-40c0-b50b-bf45f5ba75c8
- **Status:** ❌ Failed
- **Analysis / Findings:** {{TODO:AI_ANALYSIS}}.
---


## 3️⃣ Coverage & Matching Metrics

- **0.00** of tests passed

| Requirement        | Total Tests | ✅ Passed | ❌ Failed  |
|--------------------|-------------|-----------|------------|
| ...                | ...         | ...       | ...        |
---


## 4️⃣ Key Gaps / Risks
{AI_GNERATED_KET_GAPS_AND_RISKS}
---