// Open-arrival-rate acceptance test. Requires a separately installed k6 binary.
// TOKENS_FILE=/private/tokens.json RATE=10000 DURATION=30m k6 run k6_web.js
import http from 'k6/http';
import { check } from 'k6';
import { SharedArray } from 'k6/data';
import exec from 'k6/execution';
import { Rate } from 'k6/metrics';

const baseURL = (__ENV.BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const rate = Number(__ENV.RATE || 100);
const tokens = new SharedArray('test credentials', () => {
  if (!__ENV.TOKENS_FILE) throw new Error('TOKENS_FILE is required; use disposable users');
  const entries = JSON.parse(open(__ENV.TOKENS_FILE));
  if (!Array.isArray(entries) || !entries.length) throw new Error('No test credentials');
  return entries;
});
const routes = [
  '/api/v1/auth/me', '/api/v1/projects', '/api/v1/tasks?limit=20',
  '/api/v1/chat/sessions', '/api/v1/modules/registry',
];
const businessOK = new Rate('business_ok');

export const options = {
  scenarios: {
    business: {
      executor: 'constant-arrival-rate',
      rate, timeUnit: '1s', duration: __ENV.DURATION || '60s',
      preAllocatedVUs: Number(__ENV.PREALLOCATED_VUS || 100),
      maxVUs: Number(__ENV.MAX_VUS || 2000),
      gracefulStop: '20s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    business_ok: ['rate>0.99'],
    http_req_duration: ['p(95)<300', 'p(99)<1000'],
    dropped_iterations: ['count==0'],
  },
};

export default function () {
  const route = routes[exec.scenario.iterationInTest % routes.length];
  // Rotate principals even when a low-latency run needs only a few active VUs.
  const token = tokens[exec.scenario.iterationInTest % tokens.length];
  const response = http.get(baseURL + route, {
    headers: { Authorization: `Bearer ${token}`, 'User-Agent': 'CygnusX-k6-Web/1' },
    redirects: 0, timeout: '15s', tags: { name: route },
  });
  let valid = false;
  if (response.status === 200) {
    try {
      const body = response.json();
      valid = body !== null && typeof body === 'object' && !('detail' in body);
    } catch (_) { /* Invalid JSON or SPA fallback is a failure. */ }
  }
  businessOK.add(valid);
  check(response, { 'valid authenticated business response': () => valid });
}
