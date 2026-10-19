/**
 * Strip line breaks from a value before it is written to the console/log.
 *
 * Server- or peer-supplied strings (WebSocket messages, error text) can
 * carry CR/LF and forge extra log lines (CWE-117). The final
 * `.replace(/\n/g, '')` is the step CodeQL js/log-injection recognises.
 */
export function logSafe(value) {
  return String(value)
    .replace(/[\r\u2028\u2029\u0085\u000b\u000c]/g, '')
    .replace(/\n/g, '');
}

export default logSafe;
