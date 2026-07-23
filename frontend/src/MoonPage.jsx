import { useState, useEffect } from 'react'
import { fetchMoon } from './api'

const FIELDS = [
    { key: 'ra_hours', label: 'Right Ascension', unit: 'h', icon: '↔' },
    { key: 'dec_degrees', label: 'Declination', unit: '°', icon: '↕' },
    { key: 'altitude_degrees', label: 'Altitude', unit: '°', icon: '▲' },
    { key: 'azimuth_degrees', label: 'Azimuth', unit: '°', icon: '◎' },
    { key: 'distance_km', label: 'Distance', unit: 'km', icon: '⊙' },
    { key: 'phase_pct', label: 'Phase', unit: '%', icon: '◑' },
]

function formatValue(key, raw) {
    if (raw === undefined || raw === null) return '—'
    const n = parseFloat(raw)
    if (isNaN(n)) return String(raw)
    if (key === 'distance_km')
        return n.toLocaleString(undefined, { maximumFractionDigits: 0 })
    if (key === 'ra_hours') return n.toFixed(4)
    return n.toFixed(2)
}

/**
 * MoonPage displays the Moon's current position and phase data.
 */
export default function MoonPage() {
    const [moon, setMoon] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    useEffect(() => {
        let cancelled = false
        setLoading(true)
        setError(null)

        fetchMoon()
            .then((data) => {
                if (!cancelled) {
                    setMoon(data)
                    setLoading(false)
                }
            })
            .catch((err) => {
                if (!cancelled) {
                    setError(err.message)
                    setLoading(false)
                }
            })

        return () => {
            cancelled = true
        }
    }, [])

    return (
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
                                    : 'Current position'}
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
    )
}
