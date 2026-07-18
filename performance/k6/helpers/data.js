/**
 * k6/helpers/data.js
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * DETERMINISTIC FAKE DATA GENERATORS FOR K6
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * WHY THIS FILE EXISTS:
 *   k6 runs in a JavaScript runtime (Goja) that does NOT have access to npm
 *   packages like Faker.js. This module reimplements the fake data generation
 *   we need using only k6 built-ins and pure JavaScript.
 *
 * KEY DESIGN PRINCIPLES:
 *
 *   1. DETERMINISTIC BY VU + ITERATION:
 *      Random data is seeded from (__VU * 1000 + __ITER) so the same VU
 *      always generates the same data for the same iteration.
 *      This makes failures reproducible — if iteration 47 of VU 12 fails,
 *      you can reproduce the exact data that caused the failure.
 *
 *   2. NO FAKER DEPENDENCY:
 *      All generators use simple arrays + modular arithmetic.
 *      Fast, no imports, no runtime overhead.
 *
 *   3. REALISTIC BUT SIMPLE:
 *      Data doesn't need to be beautiful — it needs to be structurally valid
 *      (correct types, valid formats, passes FastAPI validation).
 *
 * ─────────────────────────────────────────────────────────────────────────────
 */


// ─── Seeded Pseudo-Random Number Generator ────────────────────────────────────
//
// k6's Math.random() is not seedable. We implement a simple LCG (Linear
// Congruential Generator) so we can produce deterministic sequences.
//
// This is NOT cryptographically secure — fine for test data generation.

/**
 * Creates a seeded PRNG. Returns a function that produces floats in [0, 1).
 *
 * @param {number} seed
 * @returns {() => number}
 */
function createRNG(seed) {
  // LCG parameters from Numerical Recipes
  let s = seed >>> 0; // Ensure unsigned 32-bit integer
  return function() {
    s = (Math.imul(1664525, s) + 1013904223) >>> 0;
    return s / 4294967296; // Normalize to [0, 1)
  };
}

/**
 * Default RNG seeded per VU + iteration for deterministic test data.
 * Re-initialized at the top of each iteration by calling resetRNG().
 */
let _rng = createRNG(1);

/**
 * Reset the RNG to a deterministic seed for the current VU + iteration.
 * Call this at the start of each k6 iteration for reproducible data.
 *
 * USAGE:
 *   export default function() {
 *     resetRNG();  // ← call first
 *     const app = generateApplication();  // now deterministic
 *   }
 */
export function resetRNG() {
  // __VU is 1-based, __ITER is 0-based
  const seed = (__VU * 100_000) + __ITER;
  _rng = createRNG(seed);
}

/** Pick a random integer in [min, max] inclusive */
function randInt(min, max) {
  return Math.floor(_rng() * (max - min + 1)) + min;
}

/** Pick a random element from an array */
function randChoice(arr) {
  return arr[randInt(0, arr.length - 1)];
}

/** Generate a random alphanumeric string of given length */
function randString(length = 8) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars[randInt(0, chars.length - 1)];
  }
  return result;
}


// ─── Vocabulary Arrays ────────────────────────────────────────────────────────
//
// Small word lists that combine to make realistic-looking names.
// Kept minimal to avoid large file size — coverage > variety for load tests.

const ADJECTIVES = [
  'fast', 'secure', 'cloud', 'smart', 'micro', 'global', 'dynamic',
  'realtime', 'distributed', 'scalable', 'resilient', 'elastic',
  'unified', 'core', 'next', 'edge', 'turbo', 'atomic', 'quantum',
];

const NOUNS = [
  'api', 'service', 'worker', 'gateway', 'proxy', 'scheduler',
  'processor', 'monitor', 'notifier', 'aggregator', 'streamer',
  'indexer', 'crawler', 'pipeline', 'engine', 'hub', 'broker',
  'store', 'cache', 'router',
];

const DOCKER_IMAGES = [
  'nginx:alpine',
  'node:20-alpine',
  'python:3.11-slim',
  'redis:7-alpine',
  'postgres:16-alpine',
  'grafana/grafana:latest',
  'prom/prometheus:latest',
  'traefik:v3',
  'caddy:alpine',
  'golang:1.22-alpine',
  'openjdk:21-slim',
  'php:8.3-fpm-alpine',
];

const EMAIL_DOMAINS = [
  'example.com',
  'test.example.com',
  'example.org',
  'benchmark.example.net',
];

const FIRST_NAMES = [
  'Alice', 'Bob', 'Carol', 'Dave', 'Eve', 'Frank', 'Grace',
  'Hank', 'Iris', 'Jack', 'Kate', 'Liam', 'Mia', 'Noah',
  'Olivia', 'Paul', 'Quinn', 'Rose', 'Sam', 'Tara',
];

const LAST_NAMES = [
  'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia',
  'Miller', 'Davis', 'Wilson', 'Moore', 'Taylor', 'Anderson',
  'Thomas', 'Jackson', 'White', 'Harris', 'Martin', 'Lee',
];


// ─── User Data ────────────────────────────────────────────────────────────────

/**
 * Generate a unique user payload for registration.
 * Uses __VU + __ITER + timestamp to guarantee uniqueness across parallel VUs.
 *
 * @returns {{ username: string, email: string, password: string }}
 */
export function generateUser() {
  // Timestamp component prevents collisions between test runs
  const uid = `${__VU}_${__ITER}_${Date.now() % 1_000_000}`;
  const firstName = randChoice(FIRST_NAMES).toLowerCase();
  const lastName  = randChoice(LAST_NAMES).toLowerCase();

  return {
    username: `${firstName}_${lastName}_${uid}`,
    email:    `${firstName}.${lastName}.${uid}@${randChoice(EMAIL_DOMAINS)}`,
    password: `TestPass_${uid}_!Abc1`,  // Meets typical password complexity rules
  };
}


// ─── Application Data ─────────────────────────────────────────────────────────

/**
 * Generate a realistic application creation payload.
 * Matches your ApplicationCreate schema:
 *   name: str, image_name: str, environment: dict[str,str], container_port: int
 *
 * @returns {{ name: string, image_name: string, environment: Object, container_port: number }}
 */
export function generateApplication() {
  const adj   = randChoice(ADJECTIVES);
  const noun  = randChoice(NOUNS);
  const suffix = randString(4);

  return {
    name:           `${adj}-${noun}-${suffix}`,
    image_name:     randChoice(DOCKER_IMAGES),
    environment:    generateEnvVars(),
    container_port: randChoice([3000, 4000, 5000, 8000, 8080, 8888, 9000]),
  };
}

/**
 * Generate a dict of realistic environment variables.
 * Simulates what a developer would configure for a containerized app.
 *
 * @param {number} [count=3] - Number of env vars to generate
 * @returns {Object} key-value dict compatible with ApplicationCreate.environment
 */
export function generateEnvVars(count = 3) {
  const templates = [
    { key: 'NODE_ENV',        value: randChoice(['production', 'staging']) },
    { key: 'LOG_LEVEL',       value: randChoice(['info', 'warn', 'error', 'debug']) },
    { key: 'PORT',            value: String(randChoice([3000, 4000, 8080])) },
    { key: 'WORKERS',         value: String(randInt(1, 8)) },
    { key: 'MAX_CONNECTIONS', value: String(randInt(10, 100)) },
    { key: 'TIMEOUT',         value: String(randInt(5, 60)) },
    { key: 'CACHE_TTL',       value: String(randInt(60, 3600)) },
    { key: 'REGION',          value: randChoice(['us-east-1', 'eu-west-1', 'ap-south-1']) },
    { key: 'DEBUG',           value: randChoice(['true', 'false']) },
    { key: 'RETRY_LIMIT',     value: String(randInt(1, 5)) },
  ];

  const selected = {};
  const shuffled = [...templates].sort(() => _rng() - 0.5);
  for (let i = 0; i < Math.min(count, shuffled.length); i++) {
    selected[shuffled[i].key] = shuffled[i].value;
  }
  return selected;
}


// ─── Assertion Helpers ────────────────────────────────────────────────────────

/**
 * Checks that a response body contains the expected fields.
 * Returns a check-compatible object for use with k6's check().
 *
 * @param {string[]} fields - Field names to verify exist in the response
 * @returns {Object} check condition object
 *
 * @example
 *   check(res, hasFields(['id', 'name', 'owner_id']));
 */
export function hasFields(fields) {
  return fields.reduce((acc, field) => {
    acc[`response has field: ${field}`] = (r) => {
      try {
        const body = JSON.parse(r.body);
        return body[field] !== undefined;
      } catch {
        return false;
      }
    };
    return acc;
  }, {});
}

/**
 * Safely parse a JSON response body. Returns null if parsing fails.
 * Logs the raw body on failure to aid debugging.
 *
 * @param {Object} res - k6 http response
 * @returns {Object|null}
 */
export function parseBody(res) {
  try {
    return JSON.parse(res.body);
  } catch (e) {
    console.error(
      `[data.js] Failed to parse JSON response. ` +
      `Status: ${res.status}, Body (first 300 chars): ${res.body?.substring(0, 300)}`
    );
    return null;
  }
}

/**
 * Extract the error detail message from a FastAPI error response.
 * FastAPI returns: { "detail": "message" } for 4xx errors.
 *
 * @param {Object} res - k6 http response
 * @returns {string}
 */
export function getErrorDetail(res) {
  const body = parseBody(res);
  if (!body) return `HTTP ${res.status} (unparseable body)`;
  return body.detail || body.message || `HTTP ${res.status}`;
}


// ─── Timing Helpers ───────────────────────────────────────────────────────────

/**
 * Returns a random think time (sleep duration) in seconds.
 * Simulates human pause between actions for realistic load patterns.
 *
 * WHY THINK TIME?
 *   Without think time, k6 VUs hammer the API as fast as possible.
 *   This creates an unrealistic "machine gun" traffic pattern.
 *   Real users pause between actions — think time makes the test
 *   represent a realistic concurrent user count, not max RPS.
 *
 * @param {number} [minMs=200] - Minimum pause in milliseconds
 * @param {number} [maxMs=1000] - Maximum pause in milliseconds
 * @returns {number} seconds (as required by k6's sleep())
 */
export function thinkTime(minMs = 200, maxMs = 1000) {
  return randInt(minMs, maxMs) / 1000;
}

/**
 * Short think time — between actions within the same user flow.
 * @returns {number} seconds
 */
export function quickPause() {
  return thinkTime(100, 300);
}

/**
 * Long think time — simulates user reading results before acting.
 * @returns {number} seconds
 */
export function readPause() {
  return thinkTime(500, 2000);
}


// ─── URL Builders ─────────────────────────────────────────────────────────────

/**
 * Build a URL with query parameters.
 * k6's http module doesn't have a URL builder, so we do it manually.
 *
 * @param {string} base - Base URL
 * @param {Object} [params={}] - Query parameters
 * @returns {string}
 *
 * @example
 *   buildUrl('http://localhost:8000/api/items', { page: 1, limit: 20 })
 *   → 'http://localhost:8000/api/items?page=1&limit=20'
 */
export function buildUrl(base, params = {}) {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== null);
  if (entries.length === 0) return base;
  const qs = entries.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&');
  return `${base}?${qs}`;
}


// ─── Seeded Data Selectors ────────────────────────────────────────────────────
//
// These functions select IDs from the seeded dataset.
// Used when workflows need to reference existing resources
// (e.g., "get the status of application #42").

/**
 * Returns a random application ID from within the seeded range.
 * Used by deployment workflows to pick an existing app to deploy.
 *
 * IMPORTANT: totalSeededApps must match SEED_APPS in seeder config.
 * Default is 50,000 — adjust if you used SEED_APPS=2000 (seed-small).
 *
 * @param {number} [totalSeededApps=50000]
 * @returns {number} Application ID (1-based)
 */
export function randomSeededAppId(totalSeededApps = 50_000) {
  // Deterministic for this VU+iteration — no race conditions
  return ((__VU * 997 + __ITER * 31) % totalSeededApps) + 1;
}

/**
 * Returns the app ID "owned" by the current VU's user.
 * Since each user has multiple applications, this picks apps 1-5 per user.
 *
 * WHY THIS PATTERN?
 *   Ensures the VU's authenticated user actually owns the app they're
 *   trying to deploy — avoids 403 Forbidden errors in load tests.
 *
 *   The seeder assigns apps to users in sequential order:
 *   user 1 → apps 1..5, user 2 → apps 6..10, etc. (APPS_PER_USER = 5)
 *
 * @param {number} [appsPerUser=5] - Must match seeder's distribution
 * @returns {number} Application ID
 */
export function getOwnedAppId(appsPerUser = 5) {
  // _cachedUserId is set by auth.js getToken()
  // We import it indirectly via the convention that VU N owns apps (N-1)*5+1 .. N*5
  const vuIndex = __VU; // 1-based
  const appOffset = randInt(1, appsPerUser);
  return (vuIndex - 1) * appsPerUser + appOffset;
}
