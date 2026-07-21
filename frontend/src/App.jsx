import { useState, useEffect } from "react";
import "./App.css";
import { useAuth } from "./AuthContext";
import AuthForm from "./AuthForm";
import { fetchMoon } from "./api";

const FIELDS = [
  { key: "ra_hours", label: "Right Ascension", unit: "h", icon: "↔" },
  { key: "dec_degrees", label: "Declination", unit: "°", icon: "↕" },
  { key: "altitude_degrees", label: "Altitude", unit: "°", icon: "▲" },
  { key: "azimuth_degrees", label: "Azimuth", unit: "°", icon: "◎" },
  { key: "distance_km", label: "Distance", unit: "km", icon: "⊙" },
  { key: "phase_pct", label: "Phase", unit: "%", icon: "◑" },
];

function formatValue(key, raw) {
  if (raw === undefined || raw === null) return "—";
  const n = parseFloat(raw);
  if (isNaN(n)) return String(raw);
  if (key === "distance_km")
    return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (key === "ra_hours") return n.toFixed(4);
  return n.toFixed(2);
}

export default function App() {
  const { isAuthed, logout } = useAuth();
  const [moon, setMoon] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isAuthed) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchMoon()
      .then((data) => {
        if (!cancelled) {
          setMoon(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [isAuthed]);

  return (
    <div className="app">
      <header className="app-header">
        <span className="app-logo">✦</span>
        <h1 className="app-title">Venera</h1>
        <p className="app-subtitle">Real-time astronomical data</p>
        {isAuthed && (
          <button className="logout-btn" onClick={logout} type="button">
            Sign out
          </button>
        )}
      </header>

      <main className="app-main">
        {!isAuthed ? (
          <AuthForm />
        ) : (
          <>
            {loading && (
              <div className="state-card">
                <div className="spinner" aria-label="Loading" />
                <p className="state-text">Acquiring lunar position…</p>
              </div>
            )}

            {error && (
              <div className="state-card error-card">
                <span className="error-icon">⚠</span>
                <p className="state-text">Failed to fetch moon data</p>
                <p className="error-detail">{error}</p>
              </div>
            )}

            {moon && !loading && !error && (
              <div className="moon-card">
                <div className="moon-card-header">
                  <span className="moon-icon">🌕</span>
                  <div>
                    <h2 className="moon-title">The Moon</h2>
                    <p className="moon-timestamp">
                      {moon.timestamp
                        ? new Date(moon.timestamp).toUTCString()
                        : "Current position"}
                    </p>
                  </div>
                </div>

                <div className="data-grid">
                  {FIELDS.map(({ key, label, unit, icon }) => (
                    <div className="data-cell" key={key}>
                      <span className="data-icon" aria-hidden="true">
                        {icon}
                      </span>
                      <span className="data-label">{label}</span>
                      <span className="data-value">
                        {formatValue(key, moon[key])}
                        <span className="data-unit">{unit}</span>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>

      <footer className="app-footer">
        <p>Venera &mdash; the sky, quantified</p>
      </footer>
    </div>
  );
}
