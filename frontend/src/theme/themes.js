// ─── Theme Registry — "Auburn & Espresso" ─────────────────

// Each theme defines overrides for the base tokens.
// Auburn & Espresso is the default (defined in tokens.js).

export const themeDefinitions = [
  {
    id: 'auburn',
    name: 'Auburn & Espresso',
    description: 'Warm earth tones with terracotta and sage',
    swatch: ['#CA6F4E', '#7B9E74', '#D4A84B'],
  },
  {
    id: 'indigo',
    name: 'Indigo Dream',
    description: 'Cool indigo with violet accents',
    swatch: ['#6366F1', '#8B5CF6', '#06B6D4'],
    palette: {
      primary: {
        50: '#EEF2FF', 100: '#E0E7FF', 200: '#C7D2FE', 300: '#A5B4FC',
        400: '#818CF8', 500: '#6366F1', 600: '#4F46E5', 700: '#4338CA',
        800: '#3730A3', 900: '#312E81',
      },
      accent: {
        50: '#F5F3FF', 100: '#EDE9FE', 200: '#DDD6FE', 300: '#C4B5FD',
        400: '#A78BFA', 500: '#8B5CF6', 600: '#7C3AED', 700: '#6D28D9',
        800: '#5B21B6', 900: '#4C1D95',
      },
      secondary: {
        50: '#ECFEFF', 100: '#CFFAFE', 200: '#A5F3FC', 300: '#67E8F9',
        400: '#22D3EE', 500: '#06B6D4', 600: '#0891B2', 700: '#0E7490',
        800: '#155E75', 900: '#164E63',
      },
      neutral: {
        50: '#F8F9FA', 100: '#F1F3F5', 150: '#EAECF0', 200: '#E2E5EA',
        300: '#CBD0D8', 400: '#9BA3B2', 500: '#6B7385', 600: '#4D5566',
        700: '#383F4E', 800: '#1A1D28', 850: '#141722', 900: '#0B0D14',
      },
      error:   { light: '#FCA5A5', main: '#EF4444', dark: '#DC2626', bg: 'rgba(239,68,68,0.12)' },
      success: { light: '#6EE7B7', main: '#10B981', dark: '#059669', bg: 'rgba(16,185,129,0.12)' },
      warning: { light: '#FCD34D', main: '#F59E0B', dark: '#D97706', bg: 'rgba(245,158,11,0.12)' },
      info:    { light: '#93C5FD', main: '#3B82F6', dark: '#2563EB', bg: 'rgba(59,130,246,0.12)' },
    },
    gradients: {
      brand:     'linear-gradient(135deg, #6366F1 0%, #8B5CF6 50%, #A78BFA 100%)',
      primary:   'linear-gradient(135deg, #6366F1 0%, #4F46E5 100%)',
      primaryHover: 'linear-gradient(135deg, #818CF8 0%, #6366F1 100%)',
      secondary: 'linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%)',
      accent:    'linear-gradient(135deg, #A78BFA 0%, #6366F1 100%)',
      userBubble:'linear-gradient(135deg, #6366F1 0%, #7C3AED 100%)',
    },
    shadows: {
      xs: '0 1px 2px rgba(0,0,0,0.04)',
      sm: '0 2px 8px rgba(0,0,0,0.06)',
      md: '0 4px 16px rgba(0,0,0,0.08)',
      lg: '0 8px 28px rgba(0,0,0,0.12)',
      xl: '0 16px 48px rgba(0,0,0,0.16)',
      glow: {
        primary: '0 0 24px rgba(99,102,241,0.15)',
        error:   '0 4px 20px rgba(239,68,68,0.3)',
      },
    },
  },
  {
    id: 'jade',
    name: 'Midnight Jade',
    description: 'Deep teal and emerald tones',
    swatch: ['#2D8A6E', '#3BA99B', '#5B8C7B'],
    palette: {
      primary: {
        50: '#EDF9F5', 100: '#D1EFE4', 200: '#A8DFCE', 300: '#6FC9B0',
        400: '#3BA99B', 500: '#2D8A6E', 600: '#237058', 700: '#1C5A46',
        800: '#154535', 900: '#0E3024',
      },
      accent: {
        50: '#F0FDF9', 100: '#CCFBF1', 200: '#99F6E4', 300: '#5EEAD4',
        400: '#2DD4BF', 500: '#14B8A6', 600: '#0D9488', 700: '#0F766E',
        800: '#115E59', 900: '#134E4A',
      },
      secondary: {
        50: '#F0FDF4', 100: '#DCFCE7', 200: '#BBF7D0', 300: '#86EFAC',
        400: '#4ADE80', 500: '#5B8C7B', 600: '#3A7A64', 700: '#2D634F',
        800: '#214B3C', 900: '#163329',
      },
      neutral: {
        50: '#F6F9F8', 100: '#EBF0EE', 150: '#DEE5E2', 200: '#CDD6D2',
        300: '#B0BFB9', 400: '#8A9E96', 500: '#6A7D75', 600: '#53635C',
        700: '#3D4A45', 800: '#2A3430', 850: '#1F2724', 900: '#141A18',
      },
      error:   { light: '#F0A8A0', main: '#C75B4A', dark: '#A34436', bg: 'rgba(199,91,74,0.12)' },
      success: { light: '#8FBC8F', main: '#5C8A53', dark: '#46723E', bg: 'rgba(92,138,83,0.12)' },
      warning: { light: '#F5D78E', main: '#D4A84B', dark: '#B88C34', bg: 'rgba(212,168,75,0.12)' },
      info:    { light: '#A8C4D0', main: '#5A8A9C', dark: '#42707E', bg: 'rgba(90,138,156,0.12)' },
    },
    gradients: {
      brand:     'linear-gradient(135deg, #2D8A6E 0%, #3BA99B 50%, #5B8C7B 100%)',
      primary:   'linear-gradient(135deg, #2D8A6E 0%, #237058 100%)',
      primaryHover: 'linear-gradient(135deg, #3BA99B 0%, #2D8A6E 100%)',
      secondary: 'linear-gradient(135deg, #5B8C7B 0%, #86EFAC 100%)',
      accent:    'linear-gradient(135deg, #3BA99B 0%, #2DD4BF 100%)',
      userBubble:'linear-gradient(135deg, #2D8A6E 0%, #237058 100%)',
    },
    shadows: {
      xs: '0 1px 2px rgba(42, 52, 48, 0.06)',
      sm: '0 2px 6px rgba(42, 52, 48, 0.08)',
      md: '0 4px 14px rgba(42, 52, 48, 0.1)',
      lg: '0 8px 28px rgba(42, 52, 48, 0.12)',
      xl: '0 16px 48px rgba(42, 52, 48, 0.16)',
      glow: {
        primary: '0 0 20px rgba(45, 138, 110, 0.2)',
        error:   '0 4px 20px rgba(199, 91, 74, 0.3)',
      },
    },
  },
  {
    id: 'rose',
    name: 'Rose Quartz',
    description: 'Soft rose and blush tones',
    swatch: ['#D47A9E', '#C49BA5', '#E8A4B8'],
    palette: {
      primary: {
        50: '#FDF2F6', 100: '#FCE4EC', 200: '#F8C9DA', 300: '#F2A4C0',
        400: '#E884A8', 500: '#D47A9E', 600: '#B85A7E', 700: '#9A4565',
        800: '#7C354F', 900: '#5E2539',
      },
      accent: {
        50: '#FFF5F7', 100: '#FDE8ED', 200: '#FBD0DB', 300: '#F7B0C3',
        400: '#E8A4B8', 500: '#D490A8', 600: '#B8758E', 700: '#9A5D74',
        800: '#7C475B', 900: '#5E3242',
      },
      secondary: {
        50: '#FDF5F7', 100: '#F9E8EC', 200: '#F0D0D9', 300: '#E0B0BE',
        400: '#C49BA5', 500: '#B08794', 600: '#96707C', 700: '#7A5B65',
        800: '#5F464E', 900: '#433138',
      },
      neutral: {
        50: '#FDF9F8', 100: '#F7EFED', 150: '#EFE3E0', 200: '#E3D4D0',
        300: '#D0BDB8', 400: '#B09B96', 500: '#8A7570', 600: '#6B5A56',
        700: '#4F423F', 800: '#362C2A', 850: '#28211F', 900: '#1A1514',
      },
      error:   { light: '#F0A8A0', main: '#C75B4A', dark: '#A34436', bg: 'rgba(199,91,74,0.12)' },
      success: { light: '#A8C4A8', main: '#6B8C6B', dark: '#527252', bg: 'rgba(107,140,107,0.12)' },
      warning: { light: '#F5D78E', main: '#D4A84B', dark: '#B88C34', bg: 'rgba(212,168,75,0.12)' },
      info:    { light: '#B8CCD4', main: '#7A9AAA', dark: '#5E7A8A', bg: 'rgba(122,154,170,0.12)' },
    },
    gradients: {
      brand:     'linear-gradient(135deg, #D47A9E 0%, #E8A4B8 50%, #C49BA5 100%)',
      primary:   'linear-gradient(135deg, #D47A9E 0%, #B85A7E 100%)',
      primaryHover: 'linear-gradient(135deg, #E884A8 0%, #D47A9E 100%)',
      secondary: 'linear-gradient(135deg, #C49BA5 0%, #E0B0BE 100%)',
      accent:    'linear-gradient(135deg, #E8A4B8 0%, #D490A8 100%)',
      userBubble:'linear-gradient(135deg, #D47A9E 0%, #B85A7E 100%)',
    },
    shadows: {
      xs: '0 1px 2px rgba(54, 44, 42, 0.06)',
      sm: '0 2px 6px rgba(54, 44, 42, 0.08)',
      md: '0 4px 14px rgba(54, 44, 42, 0.1)',
      lg: '0 8px 28px rgba(54, 44, 42, 0.12)',
      xl: '0 16px 48px rgba(54, 44, 42, 0.16)',
      glow: {
        primary: '0 0 20px rgba(212, 122, 158, 0.2)',
        error:   '0 4px 20px rgba(199, 91, 74, 0.3)',
      },
    },
  },
];

export function getThemeById(id) {
  return themeDefinitions.find(t => t.id === id) || themeDefinitions[0];
}
