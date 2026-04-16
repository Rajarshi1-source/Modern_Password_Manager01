package expo.modules.fheautofill

import android.app.assist.AssistStructure
import android.os.Build
import android.os.CancellationSignal
import android.service.autofill.AutofillService
import android.service.autofill.Dataset
import android.service.autofill.FillCallback
import android.service.autofill.FillRequest
import android.service.autofill.FillResponse
import android.service.autofill.SaveCallback
import android.service.autofill.SaveRequest
import android.view.View
import android.view.autofill.AutofillId
import android.view.autofill.AutofillValue
import android.widget.RemoteViews

/**
 * FheAutofillService — the Android AutofillService that fills login
 * fields with the decrypted plaintext held by [PendingFillStore].
 *
 * Flow:
 *   1. User focuses a password field on app A.
 *   2. Android calls [onFillRequest] with an [AssistStructure]
 *      describing A's form.
 *   3. We look up a pending entry (by package and/or domain) and
 *      produce a [FillResponse] whose [Dataset] contains one
 *      [AutofillValue] per detected field.
 *   4. If no pending entry is ready, we return an empty response;
 *      the OS simply doesn't offer a suggestion.
 *
 * We *never* persist anything on saves. `onSaveRequest` is a no-op
 * that confirms to the OS that the save has been handled.
 */
class FheAutofillService : AutofillService() {

  override fun onFillRequest(
    request: FillRequest,
    cancellationSignal: CancellationSignal,
    callback: FillCallback,
  ) {
    val ctx = request.fillContexts.lastOrNull() ?: run {
      callback.onSuccess(null)
      return
    }
    val structure = ctx.structure
    val packageName = structure.activityComponent?.packageName
    val detected = detectFields(structure)

    val entry = PendingFillStore.takeMatching(packageName, domain = null)
    if (entry == null || detected.password == null) {
      callback.onSuccess(null)
      return
    }

    try {
      val plaintext = String(entry.plaintext, Charsets.UTF_8)
      val builder = Dataset.Builder()
      val presentation = RemoteViews(this.packageName, android.R.layout.simple_list_item_1).apply {
        setTextViewText(android.R.id.text1, "Password Manager (PRE)")
      }

      builder.setValue(detected.password, AutofillValue.forText(plaintext), presentation)
      if (detected.username != null && entry.packageHint != null) {
        // The username is expected to be provided elsewhere — we
        // leave it blank here to avoid leaking guesses.
      }

      val response = FillResponse.Builder()
        .addDataset(builder.build())
        .build()
      callback.onSuccess(response)
    } finally {
      entry.plaintext.fill(0)
    }
  }

  override fun onSaveRequest(request: SaveRequest, callback: SaveCallback) {
    callback.onSuccess()
  }

  private data class DetectedFields(
    val username: AutofillId?,
    val password: AutofillId?,
  )

  private fun detectFields(structure: AssistStructure): DetectedFields {
    var username: AutofillId? = null
    var password: AutofillId? = null
    for (i in 0 until structure.windowNodeCount) {
      val wn = structure.getWindowNodeAt(i)
      val rn = wn.rootViewNode ?: continue
      val found = walk(rn)
      if (found.password != null && password == null) password = found.password
      if (found.username != null && username == null) username = found.username
    }
    return DetectedFields(username, password)
  }

  private fun walk(node: AssistStructure.ViewNode): DetectedFields {
    var username: AutofillId? = null
    var password: AutofillId? = null

    val hints = node.autofillHints
    val isPasswordByHint = hints?.any { it == View.AUTOFILL_HINT_PASSWORD } == true
    val isUsernameByHint = hints?.any {
      it == View.AUTOFILL_HINT_USERNAME || it == View.AUTOFILL_HINT_EMAIL_ADDRESS
    } == true
    val inputType = node.inputType
    val isPasswordByType = (inputType and android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD) != 0
      || (inputType and android.text.InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD) != 0

    if ((isPasswordByHint || isPasswordByType) && node.autofillId != null) {
      password = node.autofillId
    } else if (isUsernameByHint && node.autofillId != null) {
      username = node.autofillId
    }

    for (i in 0 until node.childCount) {
      val child = node.getChildAt(i)
      val inner = walk(child)
      if (inner.password != null && password == null) password = inner.password
      if (inner.username != null && username == null) username = inner.username
    }
    return DetectedFields(username, password)
  }
}
