/**
 * Auth Store
 * ===========
 * Global authentication state with JWT persistence using Zustand.
 * Manages login, logout, registration, and token lifecycle.
 */

import { create } from 'zustand';

const TOKEN_KEY = 'ca-auth-token';
const USER_KEY = 'ca-auth-user';

/**
 * Parse a JWT to extract the payload (without verification — 
 * verification happens server-side).
 */
function parseJwt(token) {
  try {
    const base64 = token.split('.')[1];
    const json = atob(base64.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(json);
  } catch {
    return null;
  }
}

function isTokenExpired(token) {
  const payload = parseJwt(token);
  if (!payload?.exp) return true;
  // Add 30s buffer
  return Date.now() >= (payload.exp * 1000) - 30000;
}

function loadPersistedAuth() {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const userJson = localStorage.getItem(USER_KEY);
    
    if (token && userJson && !isTokenExpired(token)) {
      return {
        token,
        user: JSON.parse(userJson),
        isAuthenticated: true,
      };
    }
    
    // Clear stale data
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }
  
  return { token: null, user: null, isAuthenticated: false };
}

const initialAuth = loadPersistedAuth();

const useAuthStore = create((set, get) => ({
  // State
  token: initialAuth.token,
  user: initialAuth.user,
  isAuthenticated: initialAuth.isAuthenticated,
  isLoading: false,

  // ─── Actions ──────────────────────────────────────────────

  /**
   * Set auth state after successful login/registration.
   */
  setAuth: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({
      token,
      user,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  /**
   * Clear auth state (logout).
   */
  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({
      token: null,
      user: null,
      isAuthenticated: false,
      isLoading: false,
    });
  },

  /**
   * Set loading state during auth operations.
   */
  setLoading: (loading) => set({ isLoading: loading }),

  /**
   * Check if the current token is still valid.
   */
  checkTokenValidity: () => {
    const { token } = get();
    if (token && isTokenExpired(token)) {
      get().logout();
      return false;
    }
    return !!token;
  },

  /**
   * Get the Authorization header value.
   */
  getAuthHeader: () => {
    const { token } = get();
    return token ? `Bearer ${token}` : null;
  },
}));

export default useAuthStore;
