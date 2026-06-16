import { describe, it, expect } from 'vitest';
import { createAppTheme } from '../theme/createAppTheme';

describe('createAppTheme', () => {
  it('returns a valid MUI theme for light mode', () => {
    const theme = createAppTheme('light', 'auburn');
    expect(theme).toBeDefined();
    expect(theme.palette.mode).toBe('light');
    expect(theme.palette.primary).toBeDefined();
    expect(theme.palette.secondary).toBeDefined();
    expect(theme.typography.fontFamily).toBeDefined();
  });

  it('returns a valid MUI theme for dark mode', () => {
    const theme = createAppTheme('dark', 'auburn');
    expect(theme).toBeDefined();
    expect(theme.palette.mode).toBe('dark');
  });

  it('supports named themes', () => {
    const theme = createAppTheme('dark', 'emerald');
    expect(theme).toBeDefined();
    expect(theme.palette.primary).toBeDefined();
  });

  it('falls back gracefully for unknown theme ids', () => {
    const theme = createAppTheme('light', 'nonexistent-theme');
    expect(theme).toBeDefined();
    expect(theme.palette.primary).toBeDefined();
  });
});
