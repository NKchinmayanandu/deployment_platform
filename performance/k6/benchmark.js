/**
 * performance/k6/benchmark.js
 *
 * Single k6 file containing ALL test scenarios and API flows.
 * Select which scenario to run via the SCENARIO environment variable.
 *
 * Usage:
 *   k6 run --env SCENARIO=smoke k6/benchmark.js
 *   k6 run --env SCENARIO=load  k6/benchmark.js --out json=reports/raw/load.json
 *   k6 run --env SCENARIO=stress k6/benchmark.js
 *   k6 run --env SCENARIO=spike  k6/benchmark.js
 *   k6 run --env SCENARIO=soak   k6/benchmark.js
 *
 * Or use the Makefile shortcuts:
 *   make smoke | make load | make stress | make spike | make soak
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { API_ROOT, httpParams, loginHttpParams } from './config/options.js';
import { getToken, invalidateToken, registerUser } from './helpers/auth.js';
import { resetRNG, generateApplication, parseBody, thinkTime, getOwnedAppId } from './helpers/data.js';

// ─── Config ───────────────────────────────────────────────────────────────────

const SCENARIO    = (__ENV.SCENARIO || 'smoke').toLowerCase();
const TOTAL_USERS = parseInt(__ENV.SEED_USERS || '10000', 10);
// Each user owns this many apps in the seeded DB (seeder assigns apps sequentially)
const APPS_PER_USER = 5;

// ─── Scenario Stage Definitions ───────────────────────────────────────────────

const STAGES = {
  smoke: [
    { duration: '30s', target: 2 },
    { duration: '1m',  target: 2 },
    { duration: '15s', target: 0 },
  ],
  load: [
    { duration: '1m',  target: 0  },   // start from 0
    { duration: '2m',  target: 50  },  // ramp to 50
    { duration: '5m',  target: 50  },  // hold
    { duration: '2m',  target: 100 },  // ramp to 100
    { duration: '5m',  target: 100 },  // hold at target
    { duration: '3m',  target: 0   },  // ramp down
  ],
  stress: [
    { duration: '2m',  target: 100  },
    { duration: '3m',  target: 300  },
    { duration: '3m',  target: 600  },
    { duration: '3m',  target: 1000 },
    { duration: '5m',  target: 1000 },
    { duration: '5m',  target: 0   },  // recovery
  ],
  spike: [
    { duration: '1m',  target: 10   },  // baseline
    { duration: '10s', target: 500  },  // spike!
    { duration: '3m',  target: 500  },  // hold spike
    { duration: '10s', target: 10   },  // drop
    { duration: '3m',  target: 10   },  // recovery check
    { duration: '30s', target: 0    },
  ],
  soak: [
    { duration: '5m',  target: 50 },    // ramp
    { duration: '50m', target: 50 },    // long steady state — watch for memory/latency drift
    { duration: '5m',  target: 0  },
  ],
};

// ─── Thresholds ───────────────────────────────────────────────────────────────

const THRESHOLDS = {
  smoke: {
    http_req_failed:   ['rate<0.001'],
    http_req_duration: ['p(95)<300'],
    checks:            ['rate>0.99'],
  },
  load: {
    http_req_failed:   ['rate<0.01'],
    http_req_duration: ['p(50)<200', 'p(95)<500', 'p(99)<1000'],
    checks:            ['rate>0.80'],
    http_reqs:         ['rate>20'],
  },
  stress: {
    http_req_failed:   ['rate<0.15'],
    http_req_duration: ['p(99)<5000'],
    checks:            ['rate>0.50'],
  },
  spike: {
    http_req_failed:   ['rate<0.10'],
    http_req_duration: ['p(95)<3000'],
    checks:            ['rate>0.60'],
  },
  soak: {
    http_req_failed:   ['rate<0.005'],
    http_req_duration: ['p(95)<600'],
    checks:            ['rate>0.90'],
  },
};

// ─── k6 Options (selected by SCENARIO env var) ────────────────────────────────

if (!STAGES[SCENARIO]) {
  throw new Error(`Unknown SCENARIO: "${SCENARIO}". Valid: smoke, load, stress, spike, soak`);
}

export const options = {
  stages:      STAGES[SCENARIO],
  thresholds:  THRESHOLDS[SCENARIO],
  gracefulStop: '30s',
  userAgent:   'DeploymentPlatform-k6/1.0',
};


// ─────────────────────────────────────────────────────────────────────────────
// API FLOW FUNCTIONS
// Each function exercises one area of your API.
// The default export composes them for a realistic user journey.
// ─────────────────────────────────────────────────────────────────────────────

// ── Health Check ──────────────────────────────────────────────────────────────

function checkHealth() {
  const res = http.get(`${__ENV.BASE_URL || 'http://localhost:8000'}/health`, {
    tags: { endpoint: 'health' },
  });
  check(res, {
    'health: status 200':   (r) => r.status === 200,
    'health: body ok':      (r) => r.body.includes('healthy'),
  });
}

// ── Auth Flow ─────────────────────────────────────────────────────────────────

/**
 * Smoke-only: exercises register → login → /me in sequence.
 * For load/stress/soak: we use seeded users (getToken) to avoid bcrypt overhead.
 */
function runAuthFlow() {
  group('auth', () => {
    // Register a new unique user
    const registration = registerUser();
    if (!registration) return;
    sleep(thinkTime(100, 300));

    // Login with the newly registered user
    const loginUrl = `${API_ROOT}/auth/login`;
    const payload  = `username=${encodeURIComponent(registration.email)}&password=${encodeURIComponent(registration.password)}`;
    const loginRes = http.post(loginUrl, payload, {
      ...loginHttpParams(),
      tags: { endpoint: 'login' },
    });
    const loginOk = check(loginRes, {
      'login: status 200':       (r) => r.status === 200,
      'login: has access_token': (r) => {
        try { return !!JSON.parse(r.body).access_token; } catch { return false; }
      },
    });
    if (!loginOk) return;
    sleep(thinkTime(100, 300));

    // Verify token works via /me
    const token  = JSON.parse(loginRes.body).access_token;
    const meRes  = http.get(`${API_ROOT}/auth/me`, {
      ...httpParams(token),
      tags: { endpoint: 'me' },
    });
    check(meRes, {
      'me: status 200':   (r) => r.status === 200,
      'me: has username': (r) => {
        try { return !!JSON.parse(r.body).username; } catch { return false; }
      },
    });
  });
}

// ── Application Flow ──────────────────────────────────────────────────────────

/**
 * Create → List → Get → Delete an application.
 * Uses the VU's seeded user token — no extra login overhead.
 */
function runApplicationFlow(token) {
  group('applications', () => {
    // 1. Create application
    const appData = generateApplication();
    const createRes = http.post(
      `${API_ROOT}/applications/`,
      JSON.stringify(appData),
      { ...httpParams(token), tags: { endpoint: 'create_app' } }
    );
    const created = check(createRes, {
      'create_app: status 201':   (r) => r.status === 201,
      'create_app: returns id':   (r) => {
        try { return !!JSON.parse(r.body).id; } catch { return false; }
      },
    });
    if (!created) { refreshIfUnauthorized(createRes); return; }
    sleep(thinkTime(100, 300));

    const newApp = parseBody(createRes);

    // 2. List applications (paginated in production — just list here)
    const listRes = http.get(`${API_ROOT}/applications/`, {
      ...httpParams(token),
      tags: { endpoint: 'list_apps' },
    });
    check(listRes, {
      'list_apps: status 200':      (r) => r.status === 200,
      'list_apps: returns array':   (r) => {
        try { return Array.isArray(JSON.parse(r.body)); } catch { return false; }
      },
    });
    sleep(thinkTime(100, 200));

    // 3. Get specific application
    if (newApp && newApp.id) {
      const getRes = http.get(`${API_ROOT}/applications/${newApp.id}`, {
        ...httpParams(token),
        tags: { endpoint: 'get_app' },
      });
      check(getRes, {
        'get_app: status 200':   (r) => r.status === 200,
        'get_app: correct id':   (r) => {
          try { return JSON.parse(r.body).id === newApp.id; } catch { return false; }
        },
      });
      sleep(thinkTime(100, 300));

      // 4. Delete the application we just created (keep DB clean during soak)
      const delRes = http.del(`${API_ROOT}/applications/${newApp.id}`, null, {
        ...httpParams(token),
        tags: { endpoint: 'delete_app' },
      });
      check(delRes, {
        'delete_app: status 204': (r) => r.status === 204,
      });
    }
  });
}

// ── Deployment Flow ───────────────────────────────────────────────────────────

/**
 * Exercises the full deployment lifecycle against a seeded application.
 *
 * Uses getOwnedAppId() to pick an app that belongs to this VU's user,
 * avoiding 403 errors. The seeder assigns apps to users in sequential blocks:
 *   user 1 → app IDs 1..5, user 2 → app IDs 6..10, etc.
 *
 * NOTE: deploy/stop/restart enqueue ARQ background jobs — the API returns
 * 202 Accepted immediately. We check status separately.
 */
function runDeploymentFlow(token) {
  group('deployments', () => {
    const appId = getOwnedAppId(APPS_PER_USER);

    // 1. Get current status
    const statusRes = http.get(`${API_ROOT}/deployments/${appId}/status`, {
      ...httpParams(token),
      tags: { endpoint: 'deployment_status' },
    });
    check(statusRes, {
      'deployment_status: 200 or 404': (r) => [200, 404].includes(r.status),
    });
    sleep(thinkTime(200, 500));

    // 2. Trigger a deploy
    const deployRes = http.post(`${API_ROOT}/deployments/${appId}/deploy`, null, {
      ...httpParams(token),
      tags: { endpoint: 'deploy' },
    });
    check(deployRes, {
      'deploy: 202 accepted': (r) => r.status === 202,
      'deploy: queued msg':   (r) => {
        try { return !!JSON.parse(r.body).message; } catch { return false; }
      },
    });
    if (refreshIfUnauthorized(deployRes)) return;
    sleep(thinkTime(300, 800));

    // 3. Poll status (simulates frontend checking)
    const pollRes = http.get(`${API_ROOT}/deployments/${appId}/status`, {
      ...httpParams(token),
      tags: { endpoint: 'deployment_status_poll' },
    });
    check(pollRes, {
      'status poll: 200 or 404': (r) => [200, 404].includes(r.status),
    });
    sleep(thinkTime(200, 400));

    // 4. Get logs
    const logsRes = http.get(`${API_ROOT}/deployments/${appId}/logs`, {
      ...httpParams(token),
      tags: { endpoint: 'logs' },
    });
    check(logsRes, {
      // 200 if container is running, 404 if not deployed yet — both valid
      'logs: 200 or 404 or 500': (r) => [200, 404, 500].includes(r.status),
    });
    sleep(thinkTime(200, 400));

    // 5. Stop the deployment (load/stress tests only — skip in smoke to avoid noise)
    if (SCENARIO !== 'smoke') {
      const stopRes = http.post(`${API_ROOT}/deployments/${appId}/stop`, null, {
        ...httpParams(token),
        tags: { endpoint: 'stop' },
      });
      check(stopRes, {
        'stop: 200 or 404': (r) => [200, 404].includes(r.status),
      });
      sleep(thinkTime(200, 500));

      // 6. Restart
      const restartRes = http.post(`${API_ROOT}/deployments/${appId}/restart`, null, {
        ...httpParams(token),
        tags: { endpoint: 'restart' },
      });
      check(restartRes, {
        'restart: 200 or 404': (r) => [200, 404].includes(r.status),
      });
    }
  });
}

// ─── Helper ───────────────────────────────────────────────────────────────────

function refreshIfUnauthorized(res) {
  if (res.status === 401) {
    invalidateToken();
    return true;
  }
  return false;
}


// ─────────────────────────────────────────────────────────────────────────────
// SETUP (runs once before any VU starts)
// ─────────────────────────────────────────────────────────────────────────────

export function setup() {
  // Verify the app is up before running any scenario
  const res = http.get(`${__ENV.BASE_URL || 'http://localhost:8000'}/health`);
  if (res.status !== 200) {
    throw new Error(
      `Health check failed (HTTP ${res.status}). ` +
      `Is FastAPI running? Run: make app-start`
    );
  }
  console.log(`[setup] App is healthy. Running scenario: ${SCENARIO.toUpperCase()}`);
  return { scenario: SCENARIO };
}


// ─────────────────────────────────────────────────────────────────────────────
// DEFAULT EXPORT — main VU loop
// ─────────────────────────────────────────────────────────────────────────────

export default function(data) {
  // Reset the deterministic RNG at the start of each iteration
  // so the same VU+iteration always generates the same data.
  resetRNG();

  // Smoke test: run a full auth lifecycle (register + login + me)
  // Other scenarios: use seeded users (no bcrypt overhead on the hot path)
  if (SCENARIO === 'smoke') {
    checkHealth();
    sleep(thinkTime(100, 200));
    runAuthFlow();
    return; // Smoke test: auth flow is sufficient for correctness validation
  }

  // For load/stress/spike/soak — use pre-seeded users
  // getToken() logs in once per VU and caches the JWT
  const auth = getToken(TOTAL_USERS);
  if (!auth) {
    // Login failed — skip this iteration, don't fail the whole test
    console.warn(`[VU ${__VU}] Could not acquire token, skipping iteration`);
    sleep(1);
    return;
  }

  const { token } = auth;

  // 1. Health (lightweight — always include for baseline comparison)
  checkHealth();
  sleep(thinkTime(50, 150));

  // 2. Application CRUD — tests DB read/write performance
  runApplicationFlow(token);
  sleep(thinkTime(200, 500));

  // 3. Deployment lifecycle — tests DB + ARQ queue integration
  runDeploymentFlow(token);

  // Think time between iterations — simulates real user pacing
  sleep(thinkTime(500, 1500));
}
