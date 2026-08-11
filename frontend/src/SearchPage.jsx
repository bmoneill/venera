import { useState, useEffect, useRef } from 'react'
import { searchObject, suggestObjects } from './api'
import './SearchPage.css'

const DEBOUNCE_MS = 200
const MIN_QUERY_LENGTH = 1

/**
 * SearchPage lets users look up a celestial object by name,
 * from a given observer location (a municipality name or raw lat/long
 * coordinates), and displays its position: right ascension, declination,
 * altitude, azimuth, and distance. The object name field offers
 * text-completion suggestions sourced from the celestial object catalog
 * as the user types.
 */
export default function SearchPage() {
    const [query, setQuery] = useState('')
    const [coordinates, setCoordinates] = useState('')
    const [suggestions, setSuggestions] = useState([])
    const [showSuggestions, setShowSuggestions] = useState(false)
    const [highlightedIndex, setHighlightedIndex] = useState(-1)
    const [result, setResult] = useState(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [lastQuery, setLastQuery] = useState('')

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

    function handleQueryChange(event) {
        const value = event.target.value
        setQuery(value)
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
                const matches = await suggestObjects(trimmed)
                setSuggestions(matches)
                setShowSuggestions(matches.length > 0)
            } catch {
                setSuggestions([])
                setShowSuggestions(false)
            }
        }, DEBOUNCE_MS)
    }

    function selectSuggestion(suggestion) {
        setQuery(suggestion.name)
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

    async function handleSearch(e) {
        e.preventDefault()
        const trimmedName = query.trim()
        const trimmedCoordinates = coordinates.trim()
        if (!trimmedName || !trimmedCoordinates) return

        setLoading(true)
        setError(null)
        setResult(null)
        setLastQuery(trimmedName)
        setShowSuggestions(false)

        try {
            const data = await searchObject(trimmedName, trimmedCoordinates)
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
                <div className="object-field" ref={containerRef}>
                    <input
                        className="search-input"
                        type="text"
                        placeholder="e.g. Sirius, Mars, Polaris…"
                        value={query}
                        onChange={handleQueryChange}
                        onKeyDown={handleKeyDown}
                        onFocus={() =>
                            suggestions.length > 0 && setShowSuggestions(true)
                        }
                        aria-label="Celestial object name"
                        role="combobox"
                        aria-expanded={showSuggestions}
                        aria-autocomplete="list"
                        autoComplete="off"
                        autoFocus
                    />
                    {showSuggestions && (
                        <ul className="suggestions-list" role="listbox">
                            {suggestions.map((suggestion, index) => (
                                <li
                                    key={`${suggestion.name}-${index}`}
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
                                    <span className="suggestion-name">
                                        {suggestion.name}
                                    </span>
                                    <span className="suggestion-type">
                                        {suggestion.type}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
                <input
                    className="search-input"
                    type="text"
                    placeholder="Coordinates — e.g. Paris, France or 48.8566, 2.3522"
                    value={coordinates}
                    onChange={(e) => setCoordinates(e.target.value)}
                    aria-label="Observer coordinates (municipality or lat, long)"
                    required
                />
                <button
                    className="search-btn"
                    type="submit"
                    disabled={loading || !query.trim() || !coordinates.trim()}
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
                            <p className="result-location">
                                Observed from {result.location}
                            </p>
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
                                ⊙
                            </span>
                            <span className="data-label">Distance</span>
                            <span className="data-value">
                                {result.distance_km.toLocaleString(undefined, {
                                    maximumFractionDigits: 0,
                                })}
                                <span className="data-unit">km</span>
                            </span>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
