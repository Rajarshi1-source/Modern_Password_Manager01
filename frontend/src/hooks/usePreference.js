import { useCallback, useSyncExternalStore } from 'react';
import preferencesService from '../services/preferencesService';

/**
 * usePreference
 * =============
 *
 * Small React binding over preferencesService: reads a dot-path preference,
 * re-renders when it changes (via the service's onChange subscription), and
 * exposes a setter that writes back through the service (which persists to
 * localStorage and queues a backend sync — no extra wiring needed here).
 *
 * Built on useSyncExternalStore so the value is read from the store *during
 * render*: switching `path` returns the new key's value immediately (no stale
 * snapshot for a render), and the subscription only depends on `path` (an
 * unstable `defaultValue` never forces a re-subscribe).
 *
 * @param {string} path dot-separated preference path, e.g. 'security.synestheticSignature'
 * @param {*} defaultValue value to use when the preference is unset
 * @returns {[any, (value: any) => void]} current value + setter
 */
export default function usePreference(path, defaultValue) {
  const subscribe = useCallback(
    (onStoreChange) => preferencesService.onChange(path, onStoreChange),
    [path],
  );

  const getSnapshot = useCallback(
    () => preferencesService.get(path, defaultValue),
    [path, defaultValue],
  );

  const value = useSyncExternalStore(subscribe, getSnapshot);

  const update = useCallback((next) => preferencesService.set(path, next), [path]);

  return [value, update];
}
