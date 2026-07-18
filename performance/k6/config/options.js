/**
 * performance/k6/config/options.js
 *
 * Shared constants and HTTP parameter builders.
 * Imported by benchmark.js and helpers/auth.js.
 *
 * Keeping this minimal — scenario stages and thresholds live in benchmark.js
 * because they are scenario-specific and change together.
 */

// ─── Base URL ─────────────────────────────────────────────────────────────────

const BASE_URL   = __ENV.BASE_URL   || 'http://localhost:8000';
const API_PREFIX = __ENV.API_PREFIX || '/api';

/**
 * Root URL for all API calls, e.g. http://localhost:8000/api
 * Used as: `${API_ROOT}/auth/login`
 */
export const API_ROOT = `${BASE_URL}${API_PREFIX}`;


// ─── HTTP Parameter Builders ──────────────────────────────────────────────────

/**
 * Standard JSON request params with optional Bearer token.
 *
 * @param {string|null} [token] - JWT access token (omit for unauthenticated requests)
 * @returns {Object} k6 http params object
 */
export function httpParams(token = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return { headers };
}

/**
 * Form-encoded request params for FastAPI's OAuth2PasswordRequestForm.
 * Used exclusively by the /auth/login endpoint.
 *
 * FastAPI's OAuth2 login expects application/x-www-form-urlencoded,
 * NOT application/json — passing JSON returns 422 Unprocessable Entity.
 *
 * @returns {Object} k6 http params object
 */
export function loginHttpParams() {
  return {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  };
}
