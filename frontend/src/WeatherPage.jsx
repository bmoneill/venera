import { useState, useEffect, useRef } from 'react'
import { suggestMunicipalities, fetchWeather } from './api'
import './WeatherPage.css'

const DEBOUNCE_MS = 200
const MIN_MUNICIPALITY_QUERY_LENGTH = 3

/**
 * WeatherPage lets users look up current weather conditions
 * (via Open-Meteo) for an observer location — a municipality name or raw
 * lat/long coordinates — to help judge whether the sky will be clear
 * enough for stargazing. The municipality field offers text-completion
 * suggestions sourced from the municipality gazetteer as the user types.
 */
export default function WeatherPage() {
    const [coordinates, setCoordinates] = useState('')
    const [municipalitySuggestions, setMunicipalitySuggestions] = useState([])
    const [showMunicipalitySuggestions, setShowMunicipalitySuggestions] =
        useState(false)
    const [municipalityHighlightedIndex, setMunicipalityHighlightedIndex] =
        useState(-1)
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const municipalityDebounceRef = useRef(null)
    const municipalityContainerRef = useRef(null)

    useEffect(() => {
        function handleClickOutside(event) {
            if (
                municipalityContainerRef.current &&
                !municipalityContainerRef.current.contains(event.target)
            ) {
                setShowMunicipalitySuggestions(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () =>
            document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    useEffect(() => {
        return () => {
            if (municipalityDebounceRef.current)
                clearTimeout(municipalityDebounceRef.current)
        }
    }, [])

    function handleCoordinatesChange(event) {
        const value = event.target.value
        setCoordinates(value)
        setMunicipalityHighlightedIndex(-1)

        if (municipalityDebounceRef.current)
            clearTimeout(municipalityDebounceRef.current)

        const trimmed = value.trim()
        if (trimmed.length < MIN_MUNICIPALITY_QUERY_LENGTH) {
            setMunicipalitySuggestions([])
            setShowMunicipalitySuggestions(false)
            return
        }

        municipalityDebounceRef.current = setTimeout(async () => {
            try {
                const matches = await suggestMunicipalities(trimmed)
                setMunicipalitySuggestions(matches)
                setShowMunicipalitySuggestions(matches.length > 0)
            } catch {
                setMunicipalitySuggestions([])
                setShowMunicipalitySuggestions(false)
            }
        }, DEBOUNCE_MS)
    }

    function selectMunicipalitySuggestion(suggestion) {
        setCoordinates(suggestion.label)
        setMunicipalitySuggestions([])
        setShowMunicipalitySuggestions(false)
        setMunicipalityHighlightedIndex(-1)
    }

    function handleMunicipalityKeyDown(event) {
        if (
            !showMunicipalitySuggestions ||
            municipalitySuggestions.length === 0
        )
            return

        if (event.key === 'ArrowDown') {
            event.preventDefault()
            setMunicipalityHighlightedIndex(
                (i) => (i + 1) % municipalitySuggestions.length
            )
        } else if (event.key === 'ArrowUp') {
            event.preventDefault()
            setMunicipalityHighlightedIndex(
                (i) =>
                    (i - 1 + municipalitySuggestions.length) %
                    municipalitySuggestions.length
            )
        } else if (event.key === 'Enter') {
            if (municipalityHighlightedIndex >= 0) {
                event.preventDefault()
                selectMunicipalitySuggestion(
                    municipalitySuggestions[municipalityHighlightedIndex]
                )
            }
        } else if (event.key === 'Escape') {
            setShowMunicipalitySuggestions(false)
        }
    }

    async function handleSubmit(event) {
        event.preventDefault()
        const trimmedCoordinates = coordinates.trim()
        if (!trimmedCoordinates) return

        setLoading(true)
        setError(null)
        setResult(null)
        setShowMunicipalitySuggestions(false)

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
                <div
                    className="municipality-field"
                    ref={municipalityContainerRef}
                >
                    <input
                        className="search-input"
                        type="text"
                        placeholder="Coordinates — e.g. Paris, France or 48.8566, 2.3522"
                        value={coordinates}
                        onChange={handleCoordinatesChange}
                        onKeyDown={handleMunicipalityKeyDown}
                        onFocus={() =>
                            municipalitySuggestions.length > 0 &&
                            setShowMunicipalitySuggestions(true)
                        }
                        aria-label="Observer coordinates (municipality or lat, long)"
                        role="combobox"
                        aria-expanded={showMunicipalitySuggestions}
                        aria-autocomplete="list"
                        autoComplete="off"
                        autoFocus
                        required
                    />
                    {showMunicipalitySuggestions && (
                        <ul className="suggestions-list" role="listbox">
                            {municipalitySuggestions.map(
                                (suggestion, index) => (
                                    <li
                                        key={`${suggestion.label}-${index}`}
                                        role="option"
                                        aria-selected={
                                            index ===
                                            municipalityHighlightedIndex
                                        }
                                        className={
                                            'suggestion-item' +
                                            (index ===
                                            municipalityHighlightedIndex
                                                ? ' highlighted'
                                                : '')
                                        }
                                        onMouseDown={() =>
                                            selectMunicipalitySuggestion(
                                                suggestion
                                            )
                                        }
                                        onMouseEnter={() =>
                                            setMunicipalityHighlightedIndex(
                                                index
                                            )
                                        }
                                    >
                                        {suggestion.label}
                                    </li>
                                )
                            )}
                        </ul>
                    )}
                </div>
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
