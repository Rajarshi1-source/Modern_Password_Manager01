package expo.modules.fheautofill

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings

/**
 * Thin launcher activity that the OS invokes when the user taps
 * "Settings" on the autofill service entry in system settings.
 *
 * Rather than present a bespoke UI we simply redirect the user
 * back into the RN settings screen (`fheAutofill://settings`),
 * which is deep-linked via `app.json` ``scheme``.
 *
 * If no deep link is registered we fall back to the launcher intent.
 */
class FheAutofillSettingsActivity : Activity() {
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    val deepLink = Intent(Intent.ACTION_VIEW, Uri.parse("myapp://fhe-autofill/settings"))
    deepLink.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    val resolved = packageManager.resolveActivity(deepLink, 0)
    if (resolved != null) {
      startActivity(deepLink)
    } else {
      val launcher = packageManager.getLaunchIntentForPackage(packageName)
      if (launcher != null) startActivity(launcher)
    }
    finish()
  }
}
