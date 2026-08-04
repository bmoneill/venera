import { useState } from 'react'
import { fetchWeather } from './api'
import './WeatherPage.css'

/**
 * WeatherPage lets authenticated users look up current weather conditions
 * (via Open-Meteo) for an observer location — a municipality name or raw
 * lat/long coordinates — to help judge whether the sky will be clear
 * enough for stargazing.
 */
export default function WeatherPage() {
    const [coordinates, setCoordinates] = useState('')
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    async function handleSubmit(event) {
        event.preventDefault()
        const trimmedCoordinates = coordinates.trim()
        if (!trimmedCoordinates) return

        setLoading(true)
        setError(null)
        setResult(null)

        try {
            const data = await fetchWeather(trimmedCoordinates)
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="weather-container">
            <form className="weather-form" onSubmit={handleSubmit}>
                <input
                    className="search-input"
                    type="text"
                    placeholder="Coordinates — e.g. Paris, France or 48.8566, 2.3522"
                    value={coordinates}
                    onChange={(e) => setCoordinates(e.target.value)}
                    aria-label="Observer coordinates (municipality or lat, long)"
                    autoFocus
                    required
                />
                <button
                    className="search-btn"
                    type="submit"
                    disabled={loading || !coordinates.trim()}
                >
                    {loading ? '…' : 'Check weather'}
                </button>
            </form>

            {loading && (
                <div className="state-card">
                    <div className="spinner" aria-label="Loading weather" />
                    <p className="state-text">Checking the sky…</p>
                </div>
            )}

            {error && !loading && (
                <div className="state-card error-card">
                    <span className="error-icon">⚠</span>
                    <p className="state-text">Could not fetch weather</p>
                    <p className="error-detail">{error}</p>
                </div>
            )}

            {result && !loading && !error && (
                <div className="result-card">
                    <div className="result-header">
                        <span className="result-icon" aria-hidden="true">
                            ☁
                        </span>
                        <div>
                            <h2 className="result-name">
                                {result.description}
                            </h2>
                            <p className="result-type">
                                {result.is_day ? 'Daytime' : 'Nighttime'}
                            </p>
                            <p className="result-location">
                                Observed from {result.location}
                            </p>
                        </div>
                    </div>
                    <div className="data-grid">
                        <div className="data-cell">
                            <span className="data-icon" aria-hidden="true">
                                🌡
                            </span>
                            <span className="data-label">Temperature</span>
                            <span className="data-value">
                                {result.temperature_c.toFixed(1)}
                                <span className="data-unit">°C</span>
                            </span>
                        </div>
                        <div className="data-cell">
                            <span className="data-icon" aria-hidden="true">
                                🤔
                            </span>
                            <span className="data-label">Feels Like</span>
                            <span className="data-value">
                                {result.apparent_temperature_c.toFixed(1)}
                                <span className="data-unit">°C</span>
                            </span>
                        </div>
                        <div className="data-cell">
                            <span className="data-icon" aria-hidden="true">
                                ☁
                            </span>
                            <span className="data-label">Cloud Cover</span>
                            <span className="data-value">
                                {result.cloud_cover_pct.toFixed(0)}
                                <span className="data-unit">%</span>
                            </span>
                        </div>
                        <div className="data-cell">
                            <span className="data-icon" aria-hidden="true">
                                💧
                            </span>
                            <span className="data-label">Humidity</span>
                            <span className="data-value">
                                {result.humidity_pct.toFixed(0)}
                                <span className="data-unit">%</span>
                            </span>
                        </div>
                        <div className="data-cell">
                            <span className="data-icon" aria-hidden="true">
                                🌧
                            </span>
                            <span className="data-label">Precipitation</span>
                            <span className="data-value">
                                {result.precipitation_mm.toFixed(1)}
                                <span className="data-unit">mm</span>
                            </span>
                        </div>
                        <div className="data-cell">
                            <span className="data-icon" aria-hidden="true">
                                🌬
                            </span>
                            <span className="data-label">Wind Speed</span>
                            <span className="data-value">
                                {result.wind_speed_kmh.toFixed(1)}
                                <span className="data-unit">km/h</span>
                            </span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
