const TOKEN_KEY = 'venera_token'

function getToken() {
    return localStorage.getItem(TOKEN_KEY)
}

async function apiFetch(path, options = {}) {
    const token = getToken()

    const headers = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {}),
    }

    const res = await fetch(path, { ...options, headers })

    if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`
        try {
            const data = await res.json()
            if (data.detail) detail = data.detail
        } catch {
            // ignore parse errors — keep the status-based message
        }
        throw new Error(detail)
    }

    return res.json()
}

export async function loginUser(email, password) {
    const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ username: email, password }),
    })

    if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`
        try {
            const data = await res.json()
            if (data.detail) detail = data.detail
        } catch {
            // ignore
        }
        throw new Error(detail)
    }

    return res.json()
}

export async function registerUser(email, password) {
    return apiFetch('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
    })
}

export async function fetchMoon() {
    return apiFetch('/api/moon')
}

export async function searchObject(name, coordinates) {
    const params = new URLSearchParams({ name, coordinates })
    return apiFetch(`/api/search?${params}`)
}

export async function suggestMunicipalities(query, limit = 8) {
    const params = new URLSearchParams({ query, limit })
    return apiFetch(`/api/municipalities?${params}`)
}

export async function fetchViewingRecommendation(name, coordinates) {
    const params = new URLSearchParams({ name, coordinates })
    return apiFetch(`/api/viewrec?${params}`)
}

export async function fetchWeather(coordinates) {
    const params = new URLSearchParams({ coordinates })
    return apiFetch(`/api/weather?${params}`)
}
