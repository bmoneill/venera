import { useState, useEffect, useRef } from 'react'
import { suggestMunicipalities, fetchCalendar } from './api'
import './CalendarPage.css'

const DEBOUNCE_MS = 200
const MIN_QUERY_LENGTH = 3

const CATEGORY_ICONS = {
    moon_phase: '🌕',
    best_view: '🔭',
}

function formatEventDate(isoString) {
    return new Date(isoString).toUTCString()
}

/**
 * CalendarPage lets users view a calendar of notable celestial events
 * (Moon phases and the best night to view each visible planet) over the
 * next month for a given observer location. The municipality field
 * offers text-completion suggestions sourced from the municipality
 * gazetteer as the user types.
 */
export default function CalendarPage() {
    const [municipalityQuery, setMunicipalityQuery] = useState('')
    const [days, setDays] = useState(30)
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
        const trimmedMunicipality = municipalityQuery.trim()
        if (!trimmedMunicipality) return

        setLoading(true)
        setError(null)
        setResult(null)
        setShowSuggestions(false)

        try {
            const data = await fetchCalendar(trimmedMunicipality, days)
            setResult(data)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="calendar-container">
            <form className="calendar-form" onSubmit={handleSubmit}>
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
                        autoFocus
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

                <select
                    className="days-select"
                    value={days}
                    onChange={(e) => setDays(Number(e.target.value))}
                    aria-label="Calendar window, in days"
                >
                    <option value={7}>Next 7 days</option>
                    <option value={14}>Next 14 days</option>
                    <option value={30}>Next 30 days</option>
                    <option value={60}>Next 60 days</option>
                    <option value={90}>Next 90 days</option>
                </select>

                <button
                    className="search-btn"
                    type="submit"
                    disabled={loading || !municipalityQuery.trim()}
                >
                    {loading ? '…' : 'Show calendar'}
                </button>
            </form>

            {loading && (
                <div className="state-card">
                    <div className="spinner" aria-label="Building calendar" />
                    <p className="state-text">Scanning the sky…</p>
                </div>
            )}

            {error && !loading && (
                <div className="state-card error-card">
                    <span className="error-icon">⚠</span>
                    <p className="state-text">Could not build the calendar</p>
                    <p className="error-detail">{error}</p>
                </div>
            )}

            {result && !loading && !error && (
                <div className="calendar-result">
                    <p className="calendar-summary">
                        Notable events over the next {result.window_days} days
                        near {result.location}
                    </p>

                    {result.events.length === 0 ? (
                        <div className="state-card">
                            <p className="state-text">
                                No notable events found in this window.
                            </p>
                        </div>
                    ) : (
                        <ul className="calendar-events">
                            {result.events.map((event, index) => (
                                <li
                                    key={`${event.time}-${index}`}
                                    className={`calendar-event calendar-event-${event.category}`}
                                >
                                    <span
                                        className="calendar-event-icon"
                                        aria-hidden="true"
                                    >
                                        {CATEGORY_ICONS[event.category] ?? '✦'}
                                    </span>
                                    <div className="calendar-event-body">
                                        <div className="calendar-event-header">
                                            <span className="calendar-event-title">
                                                {event.title}
                                            </span>
                                            <span className="calendar-event-date">
                                                {formatEventDate(event.time)}
                                            </span>
                                        </div>
                                        <p className="calendar-event-description">
                                            {event.description}
                                        </p>
                                        {event.altitude_degrees != null && (
                                            <p className="calendar-event-altaz">
                                                Altitude{' '}
                                                {event.altitude_degrees.toFixed(
                                                    1
                                                )}
                                                ° · Azimuth{' '}
                                                {event.azimuth_degrees.toFixed(
                                                    1
                                                )}
                                                °
                                            </p>
                                        )}
                                    </div>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    )
}
