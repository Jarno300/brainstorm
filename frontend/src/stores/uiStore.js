import { create } from 'zustand';

const safeStorage = typeof localStorage !== 'undefined' ? localStorage : null;

const useUIStore = create((set, get) => ({
  // Theme
  mode: safeStorage?.getItem('brainstorm-theme') || 'light',
  themeId: safeStorage?.getItem('brainstorm-theme-id') || 'auburn',

  setMode: (mode) => {
    safeStorage?.setItem('brainstorm-theme', mode);
    set({ mode });
  },

  setThemeId: (themeId) => {
    safeStorage?.setItem('brainstorm-theme-id', themeId);
    set({ themeId });
  },

  // Sidebar
  sidebarCollapsed: safeStorage?.getItem('brainstorm-sidebar-collapsed') === 'true',

  toggleSidebar: () => {
    const next = !get().sidebarCollapsed;
    safeStorage?.setItem('brainstorm-sidebar-collapsed', next);
    set({ sidebarCollapsed: next });
  },

  // Active tab in content area
  activeTab: 'map',
  setActiveTab: (activeTab) => set({ activeTab }),
}));

export default useUIStore;
