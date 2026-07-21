import { createContext, useContext, useState } from 'react';

const TOKEN_KEY = 'venera_token';

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));

  function saveToken(t) {
    localStorage.setItem(TOKEN_KEY, t);
    setToken(t);
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
  }

  return (
    <AuthContext.Provider value={{ token, saveToken, logout, isAuthed: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
