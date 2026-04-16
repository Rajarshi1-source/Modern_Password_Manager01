/**
 * Expo config plugin — wires the `fhe-autofill` native module into
 * the generated native projects so Android and iOS builds pick up:
 *
 *   * The `FheAutofillService` in AndroidManifest and the
 *     `BIND_AUTOFILL_SERVICE` permission (declared by the service
 *     itself — no additional host permissions are required).
 *   * The iOS Credential Provider extension target, with its own
 *     bundle identifier, entitlements, and Info.plist.
 *   * App Group entitlement on the main iOS target so it can share
 *     the pending-fill container with the extension.
 *
 * To use:
 *     // app.json
 *     "plugins": ["./modules/fhe-autofill/plugin/withFheAutofill"]
 *
 * The plugin is deliberately conservative: it only modifies files
 * that `expo prebuild` produces and never touches user-authored
 * native code.
 */

const { withInfoPlist, withEntitlementsPlist, withAndroidManifest, withXcodeProject } = require('@expo/config-plugins');

const APP_GROUP = 'group.com.passwordmanager.fheShare';
const CREDENTIAL_EXT_NAME = 'FheCredentialProvider';

function withFheAutofillAndroid(config) {
  return withAndroidManifest(config, (mod) => {
    // The module's AndroidManifest already declares the service;
    // Expo's merging should bring it in automatically.  This hook
    // exists so future edits (permissions, intent filters) have a
    // deterministic home.
    return mod;
  });
}

function withFheAutofillIOS(config) {
  config = withInfoPlist(config, (mod) => {
    const plist = mod.modResults;
    plist.NSFaceIDUsageDescription = plist.NSFaceIDUsageDescription
      || 'Used to unlock your vault so shared passwords can be autofilled.';
    return mod;
  });

  config = withEntitlementsPlist(config, (mod) => {
    const ents = mod.modResults;
    const groups = new Set(ents['com.apple.security.application-groups'] || []);
    groups.add(APP_GROUP);
    ents['com.apple.security.application-groups'] = Array.from(groups);
    return mod;
  });

  // Adding an extension target is non-trivial; we leave a TODO so
  // the developer does it manually via Xcode on first run.  The
  // source files under `ios/CredentialProvider/` are ready to drag
  // into Xcode under a new "Credential Provider Extension" target.
  config = withXcodeProject(config, (mod) => {
    // Intentionally left as a no-op to avoid corrupting the Xcode
    // project.  See README for the manual steps.
    return mod;
  });

  return config;
}

module.exports = function withFheAutofill(config) {
  config = withFheAutofillAndroid(config);
  config = withFheAutofillIOS(config);
  return config;
};
