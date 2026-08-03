import { Routes, Route, NavLink } from 'react-router-dom'
import './App.css'
import { useAuth } from './AuthContext'
import AuthForm from './AuthForm'
import MoonPage from './MoonPage'
import SearchPage from './SearchPage'
import ViewRecPage from './ViewRecPage'

export default function App() {
    const { isAuthed, logout } = useAuth()

    return (
        <div className="app">
            <header className="app-header">
                <span className="app-logo">✦</span>
                <h1 className="app-title">Venera</h1>
                <p className="app-subtitle">Real-time astronomical data</p>

                {isAuthed && (
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
                    </nav>
                )}

                {isAuthed && (
                    <button
                        className="logout-btn"
                        onClick={logout}
                        type="button"
                    >
                        Sign out
                    </button>
                )}
            </header>

            <main className="app-main">
                {!isAuthed ? (
                    <AuthForm />
                ) : (
                    <Routes>
                        <Route path="/" element={<MoonPage />} />
                        <Route path="/search" element={<SearchPage />} />
                        <Route path="/viewrec" element={<ViewRecPage />} />
                    </Routes>
                )}
            </main>

            <footer className="app-footer">
                <p>Venera &mdash; the sky, quantified</p>
            </footer>
        </div>
    )
}
