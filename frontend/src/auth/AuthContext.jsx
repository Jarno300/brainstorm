import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import api from '../api';

const AuthContext = createContext(null);

const TOKEN_KEY = 'brainstorm-auth-token';
const USER_KEY = 'brainstorm-auth-user';

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem(USER_KEY);
      return stored ? JSON.parse(stored) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(true);

  // Restore session from localStorage on mount
  useEffect(() => {
    if (token) {
      // Set the auth header on the API client
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      // Verify token is still valid
      api.get('/auth/me')
        .then((res) => {
          setUser(res.data);
          localStorage.setItem(USER_KEY, JSON.stringify(res.data));
        })
        .catch(() => {
          // Token expired or invalid — clear session
          setToken(null);
          setUser(null);
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
          delete api.defaults.headers.common['Authorization'];
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    const data = res.data;
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify({ id: data.user_id, email: data.email, tier: data.tier }));
    api.defaults.headers.common['Authorization'] = `Bearer ${data.token}`;
    setToken(data.token);
    setUser({ id: data.user_id, email: data.email, tier: data.tier });
    return data;
  }, []);

  const register = useCallback(async (email, password) => {
    const res = await api.post('/auth/register', { email, password });
    const data = res.data;
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify({ id: data.user_id, email: data.email, tier: data.tier }));
    api.defaults.headers.common['Authorization'] = `Bearer ${data.token}`;
    setToken(data.token);
    setUser({ id: data.user_id, email: data.email, tier: data.tier });
    return data;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    delete api.defaults.headers.common['Authorization'];
    setToken(null);
    setUser(null);
  }, []);

  const value = { token, user, loading, login, register, logout };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;
