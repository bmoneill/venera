import { useState } from 'react';
import { useAuth } from './AuthContext';
import { loginUser, registerUser } from './api';
import './AuthForm.css';

export default function AuthForm() {
  const { saveToken } = useAuth();
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  function switchMode(next) {
    setMode(next);
    setError(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const data =
        mode === 'login'
          ? await loginUser(email, password)
          : await registerUser(email, password);
      saveToken(data.access_token);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-card">
      <div className="auth-tabs">
        <button
          type="button"
          className={`auth-tab${mode === 'login' ? ' active' : ''}`}
          onClick={() => switchMode('login')}
        >
          Sign In
        </button>
        <button
          type="button"
          className={`auth-tab${mode === 'register' ? ' active' : ''}`}
          onClick={() => switchMode('register')}
        >
          Register
        </button>
      </div>

      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <label className="auth-label" htmlFor="auth-email">
          Email
        </label>
        <input
          id="auth-email"
          className="auth-input"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />

        <label className="auth-label" htmlFor="auth-password">
          Password
        </label>
        <input
          id="auth-password"
          className="auth-input"
          type="password"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && <p className="auth-error">{error}</p>}

        <button type="submit" className="auth-submit" disabled={loading}>
          {loading ? 'Please wait…' : mode === 'login' ? 'Sign In' : 'Create Account'}
        </button>
      </form>
    </div>
  );
}
