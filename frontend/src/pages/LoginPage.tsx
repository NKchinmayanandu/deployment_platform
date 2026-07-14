import { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { Navigate } from 'react-router-dom';
import { Rocket, AlertCircle } from 'lucide-react';

export function LoginPage() {
  const { user, isLoading, login, register } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (isLoading) return null;
  if (user) return <Navigate to="/applications" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === 'login') {
        await login(email, password);
      } else {
        await register(email, password);
      }
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (mode === 'login' ? 'Invalid credentials.' : 'Registration failed.');
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-canvas flex flex-col">
      {/* Top bar */}
      <header className="h-16 flex items-center px-8 border-b border-hairline">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-md bg-primary flex items-center justify-center">
            <Rocket size={14} className="text-white" />
          </div>
          <span className="text-[15px] font-semibold text-ink tracking-tight">Deploy</span>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center px-4 py-20">
        <div className="w-full max-w-sm">
          <div className="mb-8">
            <h1 className="text-[36px] font-normal tracking-[-0.72px] leading-[1.2] text-ink">
              {mode === 'login' ? 'Sign in' : 'Create account'}
            </h1>
            <p className="text-body-sm text-muted mt-2">
              {mode === 'login'
                ? 'Welcome back to your deployment platform.'
                : 'Start deploying your applications.'}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="email" className="section-label">
                Email
              </label>
              <input
                id="email"
                type="email"
                className="input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="password" className="section-label">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-semantic-error text-body-sm">
                <AlertCircle size={14} />
                <span>{error}</span>
              </div>
            )}

            <button
              type="submit"
              className="btn-primary w-full mt-1 h-11"
              disabled={submitting}
            >
              {submitting
                ? mode === 'login'
                  ? 'Signing in…'
                  : 'Creating account…'
                : mode === 'login'
                ? 'Sign in'
                : 'Create account'}
            </button>
          </form>

          <div className="mt-6 text-center">
            <span className="text-body-sm text-muted">
              {mode === 'login' ? "Don't have an account? " : 'Already have an account? '}
            </span>
            <button
              className="text-body-sm text-ink font-medium hover:text-primary transition-colors"
              onClick={() => {
                setMode(mode === 'login' ? 'register' : 'login');
                setError(null);
              }}
            >
              {mode === 'login' ? 'Create one' : 'Sign in'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
