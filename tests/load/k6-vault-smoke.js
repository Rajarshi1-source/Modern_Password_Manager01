// k6 load-testing smoke script.
//
// Scope note: SECUREVAULT_PRODUCTION_PLAYBOOK.md's performance section
// describes a 1,000-concurrent-user target. That is not appropriate for
// a shared GitHub-hosted runner (single vCPU/CPU-throttled, and the
// target server under test is booted on the SAME runner via
// `manage.py runserver`, a dev server not meant for production load).
// This script instead ramps to a modest ~50 VUs to produce a repeatable
// baseline and catch gross regressions (a route suddenly 10x slower, a
// new N+1 query, a crash under light concurrency) without pretending to
// be a production capacity test.
//
// Endpoints hit are both unauthenticated by design, since this workflow
// does not provision a real user/vault:
//   - GET /api/health/  - liveness/readiness probe (db, cache, migrations)
//   - GET /             - plain JSON API-root view (no DRF, no auth)
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.K6_BASE_URL || 'http://localhost:8000';

export const options = {
  scenarios: {
    ramping_smoke: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '20s', target: 10 },
        { duration: '40s', target: 50 },
        { duration: '40s', target: 50 },
        { duration: '20s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    // CI-appropriate: generous enough to tolerate a shared runner and a
    // `manage.py runserver` dev server, tight enough to catch a real
    // regression (an endpoint timing out, a crash loop under concurrency).
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<2000'],
    'http_req_duration{endpoint:health}': ['p(95)<1000'],
    'http_req_duration{endpoint:api_root}': ['p(95)<1500'],
  },
};

export default function () {
  const health = http.get(`${BASE_URL}/api/health/`, {
    tags: { endpoint: 'health' },
  });
  check(health, {
    'health status is 200': (r) => r.status === 200,
  });

  const root = http.get(`${BASE_URL}/`, {
    tags: { endpoint: 'api_root' },
  });
  check(root, {
    'api root status is 200': (r) => r.status === 200,
  });

  sleep(1);
}
