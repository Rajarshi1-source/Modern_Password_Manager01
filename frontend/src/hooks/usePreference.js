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
import { useState, useEffect, useCallback } from 'react';
import preferencesService from '../services/preferencesService';

export default function usePreference(path, defaultValue) {
  const [value, setValue] = useState(() => preferencesService.get(path, defaultValue));

  useEffect(() => {
    // Re-sync once on (re)subscribe in case the value changed between the
    // initial render and this effect running.
    setValue(preferencesService.get(path, defaultValue));
    const unsubscribe = preferencesService.onChange(path, (next) => setValue(next));
    return unsubscribe;
  }, [path, defaultValue]);

  const update = useCallback((next) => preferencesService.set(path, next), [path]);

  return [value, update];
}
