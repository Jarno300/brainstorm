import { create } from 'zustand';

const useAuthStore = create((set, get) => ({
  // State
  token: localStorage.getItem('brainstorm-auth-token') || null,
  user: null,
  loading: true,

  // Actions
  setToken: (token, user) => {
    localStorage.setItem('brainstorm-auth-token', token);
    set({ token, user, loading: false });
  },

  clearAuth: () => {
    localStorage.removeItem('brainstorm-auth-token');
    set({ token: null, user: null, loading: false });
  },

  setLoading: (loading) => set({ loading }),

  isLoggedIn: () => !!get().token,
}));

export default useAuthStore;
