import { Routes, Route, NavLink } from 'react-router-dom'
import './App.css'
import CalendarPage from './CalendarPage'
import MoonPage from './MoonPage'
import SearchPage from './SearchPage'
import ViewRecPage from './ViewRecPage'
import WeatherPage from './WeatherPage'

export default function App() {
    return (
        <div className="app">
            <header className="app-header">
                <span className="app-logo">✦</span>
                <h1 className="app-title">Venera</h1>
                <p className="app-subtitle">Real-time astronomical data</p>

                <nav className="app-nav">
                    <NavLink
                        to="/"
                        end
                        className={({ isActive }) =>
                            'nav-link' + (isActive ? ' active' : '')
                        }
                    >
                        🌕 Moon
                    </NavLink>
                    <NavLink
                        to="/search"
                        className={({ isActive }) =>
                            'nav-link' + (isActive ? ' active' : '')
                        }
                    >
                        🔭 Search
                    </NavLink>
                    <NavLink
                        to="/viewrec"
                        className={({ isActive }) =>
                            'nav-link' + (isActive ? ' active' : '')
                        }
                    >
                        🕐 When to View
                    </NavLink>
                    <NavLink
                        to="/weather"
                        className={({ isActive }) =>
                            'nav-link' + (isActive ? ' active' : '')
                        }
                    >
                        ☁ Weather
                    </NavLink>
                    <NavLink
                        to="/calendar"
                        className={({ isActive }) =>
                            'nav-link' + (isActive ? ' active' : '')
                        }
                    >
                        🗓 Calendar
                    </NavLink>
                </nav>
            </header>

            <main className="app-main">
                <Routes>
                    <Route path="/" element={<MoonPage />} />
                    <Route path="/search" element={<SearchPage />} />
                    <Route path="/viewrec" element={<ViewRecPage />} />
                    <Route path="/weather" element={<WeatherPage />} />
                    <Route path="/calendar" element={<CalendarPage />} />
                </Routes>
            </main>

            <footer className="app-footer">
                <p>Venera &mdash; the sky, quantified</p>
            </footer>
        </div>
    )
}
