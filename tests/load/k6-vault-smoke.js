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
//   - GET /             - project-level api_root (password_manager/urls.py):
//                         a plain JsonResponse behind @require_http_methods,
//                         no DRF and no auth, so it returns 200 with no JWT.
//                         Not GET /api/: api.urls.api_root is a DRF @api_view
//                         with no permission_classes of its own, so it inherits
//                         REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']
//                         (IsAuthenticated in settings/base.py) and returns 401
//                         to this unauthenticated smoke test. That 401 is also
//                         throttled, and each DRF rejection writes an ErrorLog
//                         row via custom_exception_handler. /api/health/ already
//                         covers the mounted /api/ prefix.
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
    //
    // `checks` (CodeRabbit, PR #515): http_req_failed only counts a
    // request as "failed" for network-level/5xx-class errors k6 itself
    // flags -- a 204 or a redirect back from either endpoint still reads
    // as a k6 "success" to http_req_failed even though the `check()`
    // calls below (asserting status === 200) would fail. Without this
    // threshold, every status check on /  and /api/health/ could be
    // failing every request and the smoke test would still pass. This
    // stays non-blocking like the rest of the thresholds above --
    // exercise-and-report, not a hard merge gate.
    checks: ['rate>0.95'],
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
