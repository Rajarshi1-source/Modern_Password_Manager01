/**
 * Utility function to copy text to clipboard
 * @param {string} text - The text to copy to clipboard
 * @returns {Promise} - Resolves when copying is successful, rejects on failure
 */
export const copyToClipboard = async (text) => {
  try {
    // Try to use the modern Clipboard API first
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
    
    // Fallback for older browsers or non-secure contexts
    const textArea = document.createElement('textarea');
    textArea.value = text;
    
    // Make the textarea out of viewport
    textArea.style.position = 'fixed';
    textArea.style.left = '-999999px';
    textArea.style.top = '-999999px';
    document.body.appendChild(textArea);
    
    // Select and copy
    textArea.focus();
    textArea.select();
    
    const successful = document.execCommand('copy');
    document.body.removeChild(textArea);
    
    if (!successful) {
      throw new Error('Failed to copy text');
    }
    
    return true;
  } catch (err) {
    console.error('Failed to copy text: ', err);
    throw err;
  }
};

/**
 * Reads text from clipboard
 * @returns {Promise<string>} - Resolves with clipboard text content
 */
export const readFromClipboard = async () => {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      const text = await navigator.clipboard.readText();
      return text;
    }
    throw new Error('Clipboard reading not supported in this browser/context');
  } catch (err) {
    console.error('Failed to read from clipboard: ', err);
    throw err;
  }
};
