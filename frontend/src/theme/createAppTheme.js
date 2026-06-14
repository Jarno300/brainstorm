import { createTheme, alpha } from '@mui/material';
import {
  palette as defaultPalette,
  shadows as defaultShadows,
  typography,
  radii,
  gradients as defaultGradients,
} from './tokens';
import { getThemeById } from './themes';

// ─── Theme Factory — supports multiple visual themes ───────
export function createAppTheme(mode, themeId) {
  const isDark = mode === 'dark';

  // Resolve theme overrides (fall back to base tokens for 'auburn')
  const themeDef = getThemeById(themeId);
  const p = themeDef?.palette || defaultPalette;
  const g = themeDef?.gradients || defaultGradients;
  const s = themeDef?.shadows || defaultShadows;

  // ── Surface colors ─────────────────────────────────────
  const background = isDark
    ? {
        default: p.neutral[900],
        paper:   p.neutral[800],
        elevated: p.neutral[850],
      }
    : {
        default: p.neutral[100],
        paper:   '#FFFFFF',
        elevated: p.neutral[150],
      };

  const text = isDark
    ? {
        primary:   p.neutral[100],
        secondary: p.neutral[400],
        disabled:  p.neutral[600],
      }
    : {
        primary:   p.neutral[900],
        secondary: p.neutral[500],
        disabled:  p.neutral[400],
      };

  const divider = isDark
    ? alpha(p.neutral[400], 0.12)
    : alpha(p.neutral[400], 0.18);

  // Use primary[900] as text-primary fallback for light mode
  // if neutral[900] exists; otherwise fallback to #0B0D14
  const textPrimaryLight = p.neutral[900] || '#0B0D14';

  // ── Build MUI theme ────────────────────────────────────
  return createTheme({
    palette: {
      mode,
      primary: {
        main: p.primary[500],
        light: p.primary[300],
        dark: p.primary[600],
        contrastText: '#FFFFFF',
      },
      secondary: {
        main: p.secondary[500],
        light: p.secondary[300],
        dark: p.secondary[600],
      },
      error:   { main: p.error.main,    light: p.error.light,   dark: p.error.dark },
      success: { main: p.success.main,  light: p.success.light, dark: p.success.dark },
      warning: { main: p.warning.main,  light: p.warning.light, dark: p.warning.dark },
      info:    { main: p.info.main,     light: p.info.light,    dark: p.info.dark },
      background,
      text,
      divider,
      gradients: g,
      shadows: s,
      tokens: { radii, typography: typography.fontSize },
    },

    typography: {
      fontFamily: typography.fontFamily,
      fontFamilyMonospace: typography.fontFamilyMono,
      h5: {
        fontWeight: typography.fontWeight.extrabold,
        letterSpacing: typography.letterSpacing.tight,
        fontSize: typography.fontSize.xl,
      },
      h6: {
        fontWeight: typography.fontWeight.bold,
        letterSpacing: typography.letterSpacing.normal,
        fontSize: typography.fontSize.lg,
      },
      subtitle1: {
        fontWeight: typography.fontWeight.semibold,
        fontSize: typography.fontSize.md,
        letterSpacing: typography.letterSpacing.normal,
      },
      subtitle2: {
        fontWeight: typography.fontWeight.semibold,
        fontSize: typography.fontSize.base,
        letterSpacing: typography.letterSpacing.normal,
      },
      body1: {
        fontWeight: typography.fontWeight.normal,
        fontSize: typography.fontSize.md,
        lineHeight: 1.65,
      },
      body2: {
        fontWeight: typography.fontWeight.normal,
        fontSize: typography.fontSize.base,
        lineHeight: 1.6,
        color: text.secondary,
      },
      caption: {
        fontWeight: typography.fontWeight.medium,
        fontSize: typography.fontSize.sm,
        letterSpacing: typography.letterSpacing.wide,
        color: text.disabled,
      },
      overline: {
        fontWeight: typography.fontWeight.bold,
        fontSize: typography.fontSize.xs,
        letterSpacing: typography.letterSpacing.wider,
        textTransform: 'uppercase',
      },
    },

    shape: { borderRadius: radii.sm },

    components: {
      MuiCssBaseline: {
        styleOverrides: {
          body: {
            scrollbarWidth: 'thin',
            scrollbarColor: isDark
              ? `${alpha(p.primary[400], 0.25)} transparent`
              : `${alpha(p.primary[400], 0.2)} transparent`,
          },
        },
      },

      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: radii.xs,
            textTransform: 'none',
            fontWeight: typography.fontWeight.semibold,
            fontSize: typography.fontSize.base,
            padding: '8px 20px',
            borderWidth: '1.5px',
          },
          containedPrimary: {
            boxShadow: s.sm,
            '&:hover': { boxShadow: s.md },
          },
          outlined: { borderWidth: '1.5px' },
        },
      },

      MuiPaper: {
        styleOverrides: {
          root: { borderRadius: radii.lg },
        },
      },

      MuiDialog: {
        styleOverrides: {
          paper: {
            background: isDark ? p.neutral[800] : '#FFFFFF',
            border: `1.5px solid ${alpha(p.primary[500], isDark ? 0.15 : 0.2)}`,
            borderRadius: `${radii.xl}px !important`,
            boxShadow: isDark
              ? `0 25px 60px rgba(0,0,0,0.6), 0 0 0 1px ${alpha(p.primary[500], 0.08)}`
              : `0 25px 60px rgba(0,0,0,0.1), 0 0 0 1px ${alpha(p.primary[500], 0.1)}`,
          },
        },
      },

      MuiOutlinedInput: {
        styleOverrides: {
          root: { borderRadius: radii.xs },
          notchedOutline: { borderWidth: '1.5px' },
        },
      },

      MuiChip: {
        styleOverrides: {
          root: { borderRadius: radii.xs },
          label: { fontWeight: typography.fontWeight.semibold },
        },
      },

      MuiTabs: {
        styleOverrides: {
          indicator: {
            height: '100%',
            borderRadius: radii.sm,
            backgroundColor: isDark
              ? alpha(p.primary[500], 0.2)
              : alpha(p.primary[500], 0.1),
          },
        },
      },

      MuiTab: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: typography.fontWeight.medium,
            fontSize: typography.fontSize.base,
            minHeight: 40,
            borderRadius: radii.sm,
            zIndex: 1,
            '&.Mui-selected': {
              fontWeight: typography.fontWeight.bold,
              color: isDark ? p.primary[200] : p.primary[600],
            },
          },
        },
      },

      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            borderRadius: radii.xs,
            fontSize: typography.fontSize.sm,
            fontWeight: typography.fontWeight.medium,
            backgroundColor: isDark ? p.neutral[700] : p.neutral[800],
            color: isDark ? p.neutral[100] : p.neutral[50],
            padding: '6px 12px',
          },
          arrow: {
            color: isDark ? p.neutral[700] : p.neutral[800],
          },
        },
      },

      MuiAccordion: {
        styleOverrides: {
          root: {
            borderRadius: `${radii.md}px !important`,
            border: `1px solid ${divider}`,
            '&:before': { display: 'none' },
          },
        },
      },

      MuiMenu: {
        styleOverrides: {
          paper: {
            borderRadius: radii.sm,
            border: `1px solid ${divider}`,
          },
        },
      },

      MuiAlert: {
        styleOverrides: {
          root: { borderRadius: radii.sm },
          standardError:   { backgroundColor: p.error.bg,   color: isDark ? p.error.light : p.error.dark },
          standardSuccess: { backgroundColor: p.success.bg, color: isDark ? p.success.light : p.success.dark },
          standardWarning: { backgroundColor: p.warning.bg, color: isDark ? p.warning.light : p.warning.dark },
          standardInfo:    { backgroundColor: p.info.bg,    color: isDark ? p.info.light : p.info.dark },
        },
      },

      MuiSnackbarContent: {
        styleOverrides: {
          root: { borderRadius: radii.xs },
        },
      },
    },
  });
}
