/**
 * Guardian links carry their bearer token in the URL fragment, which browsers
 * do not send to any server. This module takes it off the address bar as soon
 * as the page loads, so it stays out of browser history and out of what analytics
 * and Sentry read from window.location. main.jsx imports it first because both
 * read the location while they start, and these routes load lazily, after them.
 */
const LINK_PATHS = ['/recovery/guardian-approve', '/recovery/guardian-invite'];
// secrets.token_urlsafe(32) on the server. Other fragments are ordinary anchors,
// such as the app's skip link.
const LINK_TOKEN = /^[A-Za-z0-9_-]{43}$/;

let token = '';

const hasLinkFragment = () => LINK_PATHS.includes(window.location.pathname)
  && LINK_TOKEN.test(window.location.hash.slice(1));

export function captureLinkToken() {
  if (!hasLinkFragment()) return;
  token = window.location.hash.slice(1);
  const { pathname, search } = window.location;
  window.history.replaceState(window.history.state, '', `${pathname}${search}`);
}

/** The token from the link that opened this page; empty after a reload. */
export const linkToken = () => token;

captureLinkToken();

// A second link opened in the same tab changes only the fragment, so nothing
// reloads, and the page would go on answering the first link.
window.addEventListener('hashchange', () => {
  if (hasLinkFragment()) window.location.reload();
});
