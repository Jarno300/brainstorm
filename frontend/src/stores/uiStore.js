import { create } from 'zustand';

const useUIStore = create((set, get) => ({
  // Theme
  mode: localStorage.getItem('brainstorm-theme') || 'light',
  themeId: localStorage.getItem('brainstorm-theme-id') || 'auburn',

  setMode: (mode) => {
    localStorage.setItem('brainstorm-theme', mode);
    set({ mode });
  },

  setThemeId: (themeId) => {
    localStorage.setItem('brainstorm-theme-id', themeId);
    set({ themeId });
  },

  // Sidebar
  sidebarCollapsed: localStorage.getItem('brainstorm-sidebar-collapsed') === 'true',

  toggleSidebar: () => {
    const next = !get().sidebarCollapsed;
    localStorage.setItem('brainstorm-sidebar-collapsed', next);
    set({ sidebarCollapsed: next });
  },

  // Active tab in content area
  activeTab: 'map',
  setActiveTab: (activeTab) => set({ activeTab }),
}));

export default useUIStore;
