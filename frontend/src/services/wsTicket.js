import api from './api';

/**
 * Fetch a short-lived, single-use WebSocket ticket.
 *
 * The long-lived auth token authenticates THIS request via the Authorization
 * header (never a URL); the returned ticket is what goes in the ws:// URL, so
 * the token stays out of server access logs and browser history. Tickets are
 * single-use and expire within seconds, so fetch one immediately before each
 * connect attempt.
 *
 * @returns {Promise<string>} the opaque ticket
 */
export async function getWsTicket() {
  const { data } = await api.post('/auth/ws-ticket/');
  return data.ticket;
}

export default getWsTicket;
