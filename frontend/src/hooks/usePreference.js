/**
 * usePreference
 * =============
 *
 * Small React binding over preferencesService: reads a dot-path preference,
 * re-renders when it changes (via the service's onChange subscription), and
 * exposes a setter that writes back through the service (which persists to
 * localStorage and queues a backend sync — no extra wiring needed here).
 *
 * @param {string} path dot-separated preference path, e.g. 'security.synestheticSignature'
 * @param {*} defaultValue value to use when the preference is unset
 * @returns {[any, (value: any) => void]} current value + setter
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import preferencesService from '../services/preferencesService';

export default function usePreference(path, defaultValue) {
  // Keep the default in a ref so the subscription effect depends only on `path`
  // — callers passing an inline object/array/function default won't force the
  // effect to tear down and re-subscribe on every render.
  const defaultRef = useRef(defaultValue);
  defaultRef.current = defaultValue;

  const [value, setValue] = useState(() => preferencesService.get(path, defaultValue));

  useEffect(() => {
    // Re-sync once on (re)subscribe in case the value changed between the
    // initial render and this effect running.
    setValue(preferencesService.get(path, defaultRef.current));
    const unsubscribe = preferencesService.onChange(path, (next) => setValue(next));
    return unsubscribe;
  }, [path]);

  const update = useCallback((next) => preferencesService.set(path, next), [path]);

  return [value, update];
}
