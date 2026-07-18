/**
 * k6/helpers/auth.js
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * JWT TOKEN MANAGEMENT & LOGIN HELPER
 * ─────────────────────────────────────────────────────────────────────────────
 *
 * WHY THIS FILE EXISTS:
 *   Naively calling the /auth/login endpoint at the start of every k6 iteration
 *   pollutes your latency metrics. If login takes 80ms, that 80ms shows up in
 *   your p95/p99 for every other endpoint — making it impossible to isolate
 *   where the actual bottleneck is.
 *
 *   This module solves that with two strategies:
 *
 *   1. PER-VU TOKEN CACHING (default):
 *      Each Virtual User logs in ONCE in setup() and caches its token in a
 *      VU-local variable. Subsequent iterations reuse the token.
 *      Token refresh only happens if the API returns 401.
 *
 *   2. SHARED TOKEN POOL (optional, for extreme VU counts):
 *      Pre-generate N tokens in setup() and distribute them across VUs.
 *      Used when you have 5000 VUs but only seeded 10,000 users — you don't
 *      want 5000 concurrent register calls inflating your baseline.
 *
 * ARCHITECTURE NOTE:
 *   k6 does NOT share memory between VUs by default.
 *   The __VU global gives each VU a unique integer ID (1-based).
 *   We use __VU to pick a deterministic user from the seeded dataset so
 *   each VU always hits a different user (no thundering-herd on one account).
 *
 * ─────────────────────────────────────────────────────────────────────────────
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { API_ROOT, loginHttpParams, httpParams } from '../config/options.js';


// ─── Token Cache (VU-local) ───────────────────────────────────────────────────
//
// k6 VU memory is isolated — this variable is private to each VU instance.
// It persists across iterations for the lifetime of the VU.

let _cachedToken = null;         // Bearer token string
let _cachedUserId = null;        // Numeric user ID (for building URLs)
let _cachedUsername = null;      // Username (for logging / debugging)
let _tokenExpiresAt = 0;         // Epoch ms — refresh token before this time


// ─── Constants ────────────────────────────────────────────────────────────────

// How many ms before token expiry to proactively refresh.
// Your ACCESS_TOKEN_EXPIRE_MINUTES=120 in .env.benchmark → 7200s.
// Refresh 60s before expiry to avoid 401s mid-test.
const TOKEN_REFRESH_BUFFER_MS = 60_000;

// Benchmark JWT lifetime (must match ACCESS_TOKEN_EXPIRE_MINUTES in .env.benchmark)
const TOKEN_LIFETIME_MS = 120 * 60 * 1000; // 120 minutes in ms


// ─── Deterministic User Selection ────────────────────────────────────────────
//
// Maps a VU number to a seeded user in the database.
// The seeder generates users with predictable usernames: bench_user_1, bench_user_2, etc.
//
// WHY DETERMINISTIC?
//   - Prevents multiple VUs from hitting the same account (lock contention)
//   - Makes test results reproducible across runs
//   - Avoids "thundering herd" on a single test account

/**
 * Returns login credentials for this VU based on the total seeded user count.
 *
 * The seeder creates users with username pattern: bench_user_{n}
 * and a consistent password: BenchPass_{n}!
 *
 * @param {number} [totalSeededUsers=10000] - Must match SEED_USERS in seeder config
 * @returns {{ username: string, password: string, userIndex: number }}
 */
export function getVUCredentials(totalSeededUsers = 10_000) {
  // __VU is 1-based. Map it to 1..totalSeededUsers cyclically.
  // Cycling allows tests with more VUs than seeded users (e.g. stress test with 5000 VUs, 10000 users)
  const userIndex = ((__VU - 1) % totalSeededUsers) + 1;

  return {
    username: `bench_user_${userIndex}`,
    email: `bench_user_${userIndex}@example.com`,
    password: `BenchPass_${userIndex}!`,
    userIndex,
  };
}


// ─── Core Login Function ──────────────────────────────────────────────────────

/**
 * Performs a login request and returns the access token.
 *
 * YOUR API: POST /api/auth/login expects application/x-www-form-urlencoded
 * (FastAPI OAuth2PasswordRequestForm standard).
 *
 * On failure, this function fails the check (which increments the check failure
 * counter) and returns null. Calling code should handle null gracefully.
 *
 * @param {string} username
 * @param {string} password
 * @param {Object} [tags={}] - k6 metric tags to attach to this request
 * @returns {string|null} JWT access token or null on failure
 */
export function login(username, password, tags = {}) {
  const url = `${API_ROOT}/auth/login`;

  // FastAPI OAuth2PasswordRequestForm requires form encoding, not JSON
  const payload = `username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`;

  const res = http.post(url, payload, {
    ...loginHttpParams(),
    tags: { endpoint: 'login', ...tags },
  });

  const ok = check(res, {
    'login: status 200': (r) => r.status === 200,
    'login: has access_token': (r) => {
      try {
        return JSON.parse(r.body).access_token !== undefined;
      } catch {
        return false;
      }
    },
  });

  if (!ok || res.status !== 200) {
    console.error(
      `[auth.js] Login failed for '${username}': ` +
      `HTTP ${res.status} — ${res.body?.substring(0, 200)}`
    );
    return null;
  }

  const body = JSON.parse(res.body);
  return body.access_token;
}


// ─── Token Cache Interface ────────────────────────────────────────────────────

/**
 * Returns a valid JWT token for this VU, logging in if necessary.
 *
 * This is the PRIMARY function that scenario workflows should call.
 * It handles:
 *   - First-time login (token not yet acquired)
 *   - Proactive token refresh (before expiry)
 *   - Reactive token refresh (on 401 response — see refreshOnUnauthorized)
 *
 * @param {number} [totalSeededUsers=10000]
 * @returns {{ token: string, userId: number, username: string } | null}
 */
export function getToken(totalSeededUsers = 10_000) {
  const now = Date.now();
  const needsRefresh = (
    _cachedToken === null ||
    now >= (_tokenExpiresAt - TOKEN_REFRESH_BUFFER_MS)
  );

  if (needsRefresh) {
    const creds = getVUCredentials(totalSeededUsers);
    const token = login(creds.email, creds.password);

    if (!token) {
      return null;
    }

    _cachedToken = token;
    _cachedUsername = creds.username;
    _cachedUserId = creds.userIndex; // seeded userId ≈ userIndex (1-based sequential)
    _tokenExpiresAt = now + TOKEN_LIFETIME_MS;
  }

  return {
    token: _cachedToken,
    userId: _cachedUserId,
    username: _cachedUsername,
  };
}

/**
 * Force-clears the cached token for this VU.
 * Call this after receiving a 401 to force a re-login on the next getToken() call.
 *
 * USAGE:
 *   const res = http.get(url, httpParams(auth.token));
 *   if (res.status === 401) {
 *     invalidateToken();
 *     return; // Skip remainder of iteration — next iteration will re-login
 *   }
 */
export function invalidateToken() {
  _cachedToken = null;
  _cachedUserId = null;
  _cachedUsername = null;
  _tokenExpiresAt = 0;
}

/**
 * Convenience wrapper: checks a response for 401 and invalidates the cache.
 * Returns true if the token was invalidated (caller should abort iteration).
 *
 * @param {Object} res - k6 http response object
 * @returns {boolean} true if 401 was detected and token was cleared
 */
export function refreshOnUnauthorized(res) {
  if (res.status === 401) {
    console.warn(`[auth.js] 401 received by VU ${__VU} — invalidating token`);
    invalidateToken();
    return true;
  }
  return false;
}


// ─── Registration Helper ──────────────────────────────────────────────────────

/**
 * Registers a new user with a unique username (uses __VU + __ITER for uniqueness).
 *
 * Used by the smoke test and auth_flow.js to test the register endpoint.
 * NOT used during normal load tests (we use seeded users for those).
 *
 * WHY NOT USE REGISTRATION FOR LOAD TESTS?
 *   Bcrypt password hashing is CPU-intensive. Registering thousands of users
 *   during a load test would peg CPU on the auth service, masking the real
 *   performance characteristics of your application endpoints.
 *
 * @param {Object} [overrides={}] - Override any user fields
 * @returns {{ res: Response, username: string, email: string, password: string } | null}
 */
export function registerUser(overrides = {}) {
  const url = `${API_ROOT}/auth/register`;

  // __VU (1-based VU number) + __ITER (0-based iteration count) gives a unique combination
  const uniqueId = `${__VU}_${__ITER}_${Date.now()}`;
  const username = overrides.username || `test_user_${uniqueId}`;
  const email    = overrides.email    || `test_${uniqueId}@example.com`;
  const password = overrides.password || `TestPass_${uniqueId}!`;

  const payload = JSON.stringify({ username, email, password });

  const res = http.post(url, payload, {
    ...httpParams(),
    tags: { endpoint: 'register' },
  });

  const ok = check(res, {
    'register: status 201': (r) => r.status === 201,
    'register: returns user id': (r) => {
      try {
        return JSON.parse(r.body).id !== undefined;
      } catch {
        return false;
      }
    },
  });

  if (!ok) {
    console.error(
      `[auth.js] Registration failed for '${username}': ` +
      `HTTP ${res.status} — ${res.body?.substring(0, 200)}`
    );
    return null;
  }

  return { res, username, email, password };
}


// ─── /me Endpoint Helper ──────────────────────────────────────────────────────

/**
 * Calls GET /auth/me to validate the current token and fetch user info.
 * Useful in smoke tests to verify the full auth lifecycle.
 *
 * @param {string} token - JWT access token
 * @returns {Object|null} Parsed user object or null on failure
 */
export function getMe(token) {
  const url = `${API_ROOT}/auth/me`;

  const res = http.get(url, {
    ...httpParams(token),
    tags: { endpoint: 'me' },
  });

  const ok = check(res, {
    'me: status 200': (r) => r.status === 200,
    'me: has username': (r) => {
      try {
        return JSON.parse(r.body).username !== undefined;
      } catch {
        return false;
      }
    },
  });

  if (!ok) {
    refreshOnUnauthorized(res);
    return null;
  }

  return JSON.parse(res.body);
}


// ─── Shared Token Pool (for extreme VU counts) ────────────────────────────────
//
// WHEN TO USE THIS:
//   When you have more VUs than the seeder can reasonably support for login.
//   Example: stress test with 5000 VUs hitting register simultaneously = CPU explosion.
//
//   Instead, pre-generate N tokens in the k6 setup() function and share them
//   via k6's SharedArray. Each VU picks a token by its __VU index.
//
// HOW TO USE:
//   In your scenario's setup() function:
//     import { buildSharedTokenPool } from '../helpers/auth.js';
//     export function setup() {
//       return { tokens: buildSharedTokenPool(200) };  // 200 pre-generated tokens
//     }
//
//   In your default/scenario function:
//     export default function(data) {
//       const token = pickTokenFromPool(data.tokens);
//       // use token...
//     }

/**
 * Generates a pool of tokens by logging in as N different seeded users.
 * Run this in k6 setup() — it executes once before any VU starts.
 *
 * @param {number} poolSize - Number of unique tokens to pre-generate
 * @param {number} [totalSeededUsers=10000]
 * @returns {string[]} Array of valid JWT tokens
 */
export function buildSharedTokenPool(poolSize, totalSeededUsers = 10_000) {
  console.log(`[auth.js] Building token pool of ${poolSize} tokens...`);
  const tokens = [];

  for (let i = 1; i <= poolSize; i++) {
    const userIndex = ((i - 1) % totalSeededUsers) + 1;
    const username = `bench_user_${userIndex}`;
    const email = `bench_user_${userIndex}@example.com`;
    const password = `BenchPass_${userIndex}!`;

    const token = login(email, password);
    if (token) {
      tokens.push(token);
    } else {
      console.warn(`[auth.js] Failed to get token for user ${userIndex}, skipping`);
    }

    // Brief pause every 50 logins to avoid overwhelming the auth endpoint
    if (i % 50 === 0) {
      sleep(0.5);
      console.log(`  ... ${i}/${poolSize} tokens acquired`);
    }
  }

  console.log(`[auth.js] Token pool ready: ${tokens.length} tokens`);
  return tokens;
}

/**
 * Picks a token from a pre-built pool by VU number.
 * Cycles through the pool if there are more VUs than tokens.
 *
 * @param {string[]} tokens - Token pool from buildSharedTokenPool()
 * @returns {string} A JWT token
 */
export function pickTokenFromPool(tokens) {
  if (!tokens || tokens.length === 0) {
    console.error('[auth.js] Token pool is empty!');
    return null;
  }
  const idx = (__VU - 1) % tokens.length;
  return tokens[idx];
}
