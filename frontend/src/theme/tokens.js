// ─── Design Tokens — "Auburn & Espresso" warm earth theme ──

export const palette = {
  // Brand — Auburn / Terracotta (warm, grounded)
  primary: {
    50: '#FDF2ED',
    100: '#F9DDD2',
    200: '#F2BBA6',
    300: '#E89376',
    400: '#DE7755',
    500: '#CA6F4E',  // main — rich auburn
    600: '#B85A3E',
    700: '#9E4730',
    800: '#7E3725',
    900: '#5E281B',
  },
  // Accent — Ochre / Amber (warm gold)
  accent: {
    50: '#FEF8ED',
    100: '#FCEBCB',
    200: '#F9D990',
    300: '#F5C55A',
    400: '#EAB13A',
    500: '#D4A84B',  // main — warm ochre
    600: '#B88C34',
    700: '#967027',
    800: '#74561E',
    900: '#523D14',
  },
  // Secondary — Sage / Olive (earthy green)
  secondary: {
    50: '#F2F7F0',
    100: '#DAE9D4',
    200: '#B9D3AE',
    300: '#94BA87',
    400: '#7CA46E',
    500: '#7B9E74',  // main — sage
    600: '#5C8A53',
    700: '#46723E',
    800: '#35592E',
    900: '#253F20',
  },
  // Neutral — Warm espresso scale
  neutral: {
    50: '#FDFAF7',
    100: '#F5EDE6',
    150: '#EDE2D8',
    200: '#E2D4C8',
    300: '#D0BFB0',
    400: '#B09B8A',
    500: '#8A7564',
    600: '#6B5A4C',
    700: '#4F4238',
    800: '#362C24',
    850: '#28211B',
    900: '#1A1512',
  },
  // Semantic — Warm-adjusted
  error:    { light: '#F0A8A0', main: '#C75B4A', dark: '#A34436', bg: 'rgba(199,91,74,0.12)' },
  success:  { light: '#8FBC8F', main: '#5C8A53', dark: '#46723E', bg: 'rgba(92,138,83,0.12)' },
  warning:  { light: '#F5D78E', main: '#D4A84B', dark: '#B88C34', bg: 'rgba(212,168,75,0.12)' },
  info:     { light: '#A8C4D0', main: '#6B8E9C', dark: '#52727E', bg: 'rgba(107,142,156,0.12)' },
};

// ─── Shadows — Warm-toned (brown/amber undertones) ────────
export const shadows = {
  xs: '0 1px 2px rgba(79, 66, 56, 0.06)',
  sm: '0 2px 6px rgba(79, 66, 56, 0.08)',
  md: '0 4px 14px rgba(79, 66, 56, 0.1)',
  lg: '0 8px 28px rgba(79, 66, 56, 0.12)',
  xl: '0 16px 48px rgba(79, 66, 56, 0.16)',
  glow: {
    primary: `0 0 20px rgba(202, 111, 78, 0.2)`,
    error:   `0 4px 20px rgba(199, 91, 74, 0.3)`,
  },
};

// ─── Typography ──────────────────────────────────────────────
export const typography = {
  fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  fontFamilyMono: '"JetBrains Mono", "Fira Code", monospace',
  fontSize: {
    xs:  '0.6rem',
    sm:  '0.7rem',
    base:'0.825rem',
    md:  '0.925rem',
    lg:  '1.05rem',
    xl:  '1.35rem',
    '2xl':'1.6rem',
  },
  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 800,
  },
  letterSpacing: {
    tight: '-0.02em',
    normal: '-0.01em',
    wide: '0.02em',
    wider: '0.08em',
  },
};

// ─── Radii — Intentional shape tension ─────────────────────
// Sharp buttons (2px) + soft cards (16px) + pill tags (full)
export const radii = {
  none:  0,
  xs:    2,   // buttons, inputs, tags
  sm:    6,   // small surfaces
  md:    10,  // medium surfaces
  lg:    16,  // cards, dialogs
  xl:    24,  // modal, large panels
  full:  9999,
};

// ─── Gradients — Warm sunset to ochre ───────────────────────
export const gradients = {
  brand:    'linear-gradient(135deg, #CA6F4E 0%, #D4A84B 60%, #E89376 100%)',
  primary:  'linear-gradient(135deg, #CA6F4E 0%, #B85A3E 100%)',
  primaryHover: 'linear-gradient(135deg, #DE7755 0%, #CA6F4E 100%)',
  secondary:'linear-gradient(135deg, #7B9E74 0%, #94BA87 100%)',
  accent:   'linear-gradient(135deg, #D4A84B 0%, #EAB13A 100%)',
  userBubble: 'linear-gradient(135deg, #CA6F4E 0%, #B85A3E 100%)',
};

// ─── Transitions ─────────────────────────────────────────────
export const transitions = {
  fast:   'all 0.12s cubic-bezier(0.4, 0, 0.2, 1)',
  normal: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
  slow:   'all 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
};
