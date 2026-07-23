import { useState } from 'react'
import { searchObject } from './api'
import './SearchPage.css'

/**
 * SearchPage lets authenticated users look up a celestial object by name
 * and displays its equatorial coordinates (RA and Dec).
 */
export default function SearchPage() {
    const [query, setQuery] = useState('')
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [lastQuery, setLastQuery] = useState('')

    async function handleSearch(e) {
        e.preventDefault()
        const trimmed = query.trim()
        if (!trimmed) return

        setLoading(true)
        setError(null)
        setResult(null)
        setLastQuery(trimmed)

        try {
            const data = await searchObject(trimmed)
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="search-container">
            <form className="search-form" onSubmit={handleSearch}>
                <input
                    className="search-input"
                    type="text"
                    placeholder="e.g. Sirius, Mars, Polaris…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    aria-label="Celestial object name"
                    autoFocus
                />
                <button
                    className="search-btn"
                    type="submit"
                    disabled={loading || !query.trim()}
                >
                    {loading ? '…' : 'Search'}
                </button>
            </form>

            {loading && (
                <div className="state-card">
                    <div className="spinner" aria-label="Searching" />
                    <p className="state-text">Searching the sky…</p>
                </div>
            )}

            {error && !loading && (
                <div className="state-card error-card">
                    <span className="error-icon">⚠</span>
                    <p className="state-text">
                        {error.includes('not found')
                            ? `"${lastQuery}" was not found in the catalog`
                            : 'Search failed'}
                    </p>
                    <p className="error-detail">{error}</p>
                </div>
            )}

            {result && !loading && !error && (
                <div className="result-card">
                    <div className="result-header">
                        <span className="result-icon" aria-hidden="true">
                            ✦
                        </span>
                        <div>
                            <h2 className="result-name">{result.name}</h2>
                            <p className="result-type">{result.type}</p>
                        </div>
                    </div>
                    <div className="data-grid">
                        <div className="data-cell">
                            <span className="data-icon" aria-hidden="true">
                                ↔
                            </span>
                            <span className="data-label">Right Ascension</span>
                            <span className="data-value">
                                {result.ra_hours.toFixed(4)}
                                <span className="data-unit">h</span>
                            </span>
                        </div>
                        <div className="data-cell">
                            <span className="data-icon" aria-hidden="true">
                                ↕
                            </span>
                            <span className="data-label">Declination</span>
                            <span className="data-value">
                                {result.dec_degrees.toFixed(4)}
                                <span className="data-unit">°</span>
                            </span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
