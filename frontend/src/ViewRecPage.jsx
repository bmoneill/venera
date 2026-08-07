import { useState, useEffect, useRef } from 'react'
import { suggestMunicipalities, fetchViewingRecommendation } from './api'
import './ViewRecPage.css'

const DEBOUNCE_MS = 200
const MIN_QUERY_LENGTH = 2

/**
 * ViewRecPage lets users find the soonest time a celestial
 * object will be in clear view from their municipality. The municipality
 * field offers text-completion suggestions sourced from the municipality
 * gazetteer as the user types.
 */
export default function ViewRecPage() {
    const [objectName, setObjectName] = useState('')
    const [municipalityQuery, setMunicipalityQuery] = useState('')
    const [suggestions, setSuggestions] = useState([])
    const [showSuggestions, setShowSuggestions] = useState(false)
    const [highlightedIndex, setHighlightedIndex] = useState(-1)
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)

    const debounceRef = useRef(null)
    const containerRef = useRef(null)

    useEffect(() => {
        function handleClickOutside(event) {
            if (
                containerRef.current &&
                !containerRef.current.contains(event.target)
            ) {
                setShowSuggestions(false)
            }
        }
        document.addEventListener('mousedown', handleClickOutside)
        return () =>
            document.removeEventListener('mousedown', handleClickOutside)
    }, [])

    useEffect(() => {
        return () => {
            if (debounceRef.current) clearTimeout(debounceRef.current)
        }
    }, [])

    function handleMunicipalityChange(event) {
        const value = event.target.value
        setMunicipalityQuery(value)
        setHighlightedIndex(-1)

        if (debounceRef.current) clearTimeout(debounceRef.current)

        const trimmed = value.trim()
        if (trimmed.length < MIN_QUERY_LENGTH) {
            setSuggestions([])
            setShowSuggestions(false)
            return
        }

        debounceRef.current = setTimeout(async () => {
            try {
                const matches = await suggestMunicipalities(trimmed)
                setSuggestions(matches)
                setShowSuggestions(matches.length > 0)
            } catch {
                setSuggestions([])
                setShowSuggestions(false)
            }
        }, DEBOUNCE_MS)
    }

    function selectSuggestion(suggestion) {
        setMunicipalityQuery(suggestion.label)
        setSuggestions([])
        setShowSuggestions(false)
        setHighlightedIndex(-1)
    }

    function handleKeyDown(event) {
        if (!showSuggestions || suggestions.length === 0) return

        if (event.key === 'ArrowDown') {
            event.preventDefault()
            setHighlightedIndex((i) => (i + 1) % suggestions.length)
        } else if (event.key === 'ArrowUp') {
            event.preventDefault()
            setHighlightedIndex(
                (i) => (i - 1 + suggestions.length) % suggestions.length
            )
        } else if (event.key === 'Enter') {
            if (highlightedIndex >= 0) {
                event.preventDefault()
                selectSuggestion(suggestions[highlightedIndex])
            }
        } else if (event.key === 'Escape') {
            setShowSuggestions(false)
        }
    }

    async function handleSubmit(event) {
        event.preventDefault()
        const trimmedName = objectName.trim()
        const trimmedMunicipality = municipalityQuery.trim()
        if (!trimmedName || !trimmedMunicipality) return

        setLoading(true)
        setError(null)
        setResult(null)
        setShowSuggestions(false)

        try {
            const data = await fetchViewingRecommendation(
                trimmedName,
                trimmedMunicipality
            )
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="viewrec-container">
            <form className="viewrec-form" onSubmit={handleSubmit}>
                <input
                    className="search-input"
                    type="text"
                    placeholder="e.g. Mars, Sirius, Moon…"
                    value={objectName}
                    onChange={(e) => setObjectName(e.target.value)}
                    aria-label="Celestial object name"
                    autoFocus
                />

                <div className="municipality-field" ref={containerRef}>
                    <input
                        className="search-input"
                        type="text"
                        placeholder="Your municipality — e.g. Paris, France"
                        value={municipalityQuery}
                        onChange={handleMunicipalityChange}
                        onKeyDown={handleKeyDown}
                        onFocus={() =>
                            suggestions.length > 0 && setShowSuggestions(true)
                        }
                        aria-label="Municipality"
                        role="combobox"
                        aria-expanded={showSuggestions}
                        aria-autocomplete="list"
                        autoComplete="off"
                    />
                    {showSuggestions && (
                        <ul className="suggestions-list" role="listbox">
                            {suggestions.map((suggestion, index) => (
                                <li
                                    key={`${suggestion.label}-${index}`}
                                    role="option"
                                    aria-selected={index === highlightedIndex}
                                    className={
                                        'suggestion-item' +
                                        (index === highlightedIndex
                                            ? ' highlighted'
                                            : '')
                                    }
                                    onMouseDown={() =>
                                        selectSuggestion(suggestion)
                                    }
                                    onMouseEnter={() =>
                                        setHighlightedIndex(index)
                                    }
                                >
                                    {suggestion.label}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>

                <button
                    className="search-btn"
                    type="submit"
                    disabled={
                        loading ||
                        !objectName.trim() ||
                        !municipalityQuery.trim()
                    }
                >
                    {loading ? '…' : 'Find best time'}
                </button>
            </form>

            {loading && (
                <div className="state-card">
                    <div className="spinner" aria-label="Calculating" />
                    <p className="state-text">Scanning the sky…</p>
                </div>
            )}

            {error && !loading && (
                <div className="state-card error-card">
                    <span className="error-icon">⚠</span>
                    <p className="state-text">
                        Could not compute a recommendation
                    </p>
                    <p className="error-detail">{error}</p>
                </div>
            )}

            {result && !loading && !error && (
                <div
                    className={
                        'result-card' + (result.visible ? '' : ' not-visible')
                    }
                >
                    <div className="result-header">
                        <span className="result-icon" aria-hidden="true">
                            {result.visible ? '🕐' : '✖'}
                        </span>
                        <div>
                            <h2 className="result-name">{result.name}</h2>
                            <p className="result-type">{result.type}</p>
                            <p className="result-location">
                                Observed from {result.location}
                            </p>
                        </div>
                    </div>

                    <p className="viewrec-message">{result.message}</p>

                    {result.visible && (
                        <div className="data-grid">
                            <div className="data-cell">
                                <span className="data-icon" aria-hidden="true">
                                    🕐
                                </span>
                                <span className="data-label">
                                    Best Time (UTC)
                                </span>
                                <span className="data-value viewrec-time">
                                    {new Date(result.time).toUTCString()}
                                </span>
                            </div>
                            <div className="data-cell">
                                <span className="data-icon" aria-hidden="true">
                                    ▲
                                </span>
                                <span className="data-label">Altitude</span>
                                <span className="data-value">
                                    {result.altitude_degrees.toFixed(2)}
                                    <span className="data-unit">°</span>
                                </span>
                            </div>
                            <div className="data-cell">
                                <span className="data-icon" aria-hidden="true">
                                    ◎
                                </span>
                                <span className="data-label">Azimuth</span>
                                <span className="data-value">
                                    {result.azimuth_degrees.toFixed(2)}
                                    <span className="data-unit">°</span>
                                </span>
                            </div>
                            <div className="data-cell">
                                <span className="data-icon" aria-hidden="true">
                                    ☀
                                </span>
                                <span className="data-label">Sun Altitude</span>
                                <span className="data-value">
                                    {result.sun_altitude_degrees.toFixed(2)}
                                    <span className="data-unit">°</span>
                                </span>
                            </div>
                            {result.cloud_cover_pct != null && (
                                <div className="data-cell">
                                    <span
                                        className="data-icon"
                                        aria-hidden="true"
                                    >
                                        ☁
                                    </span>
                                    <span className="data-label">
                                        Cloud Cover
                                    </span>
                                    <span className="data-value">
                                        {result.cloud_cover_pct.toFixed(0)}
                                        <span className="data-unit">%</span>
                                    </span>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}
