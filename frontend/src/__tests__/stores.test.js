import { describe, it, expect, beforeEach } from 'vitest';

// Reset localStorage between tests
beforeEach(() => {
  localStorage.clear();
});

describe('UI Store', () => {
  it('initializes with light theme', async () => {
    const { default: useUIStore } = await import('../stores/uiStore');
    const state = useUIStore.getState();
    expect(state.mode).toBe('light');
    expect(state.themeId).toBe('auburn');
    expect(state.activeTab).toBe('map');
  });

  it('toggles dark mode and persists', async () => {
    const { default: useUIStore } = await import('../stores/uiStore');
    useUIStore.getState().setMode('dark');
    expect(useUIStore.getState().mode).toBe('dark');
    expect(localStorage.getItem('brainstorm-theme')).toBe('dark');
  });

  it('toggles sidebar collapse', async () => {
    const { default: useUIStore } = await import('../stores/uiStore');
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);
  });
});

describe('Chat Store', () => {
  it('initializes with empty messages', async () => {
    const { default: useChatStore } = await import('../stores/chatStore');
    const state = useChatStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.sending).toBe(false);
    expect(state.chatError).toBe('');
  });

  it('clear resets everything', async () => {
    const { default: useChatStore } = await import('../stores/chatStore');
    useChatStore.setState({ messages: [{ id: '1' }], sending: true, chatError: 'oh no' });
    useChatStore.getState().clear();
    const state = useChatStore.getState();
    expect(state.messages).toEqual([]);
    expect(state.sending).toBe(false);
    expect(state.chatError).toBe('');
  });
});
