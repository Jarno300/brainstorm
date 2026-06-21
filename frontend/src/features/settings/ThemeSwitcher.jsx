import { useState, useRef } from 'react';
import {
  Box, IconButton, Popper, Paper, ClickAwayListener, Typography, alpha, useTheme,
} from '@mui/material';
import { Palette as PaletteIcon } from '@mui/icons-material';
import { themeDefinitions } from '../../theme';

function ThemeSwitcher({ themeId, onThemeChange }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef(null);
  const outerTheme = useTheme();
  const isDark = outerTheme.palette.mode === 'dark';

  return (
    <>
      <IconButton
        ref={anchorRef}
        onClick={() => setOpen((v) => !v)}
        size="small"
        sx={(theme) => ({
          width: 30, height: 30, borderRadius: 1,
          color: alpha(theme.palette.text.secondary, 0.55),
          transition: 'all 0.2s ease',
          '&:hover': {
            bgcolor: alpha(theme.palette.primary.main, 0.08),
            color: theme.palette.primary.light,
            borderColor: alpha(theme.palette.primary.main, 0.15),
          },
        })}
      >
        <PaletteIcon sx={{ fontSize: 15 }} />
      </IconButton>

      <Popper
        open={open}
        anchorEl={anchorRef.current}
        placement="bottom-end"
        sx={{ zIndex: 1300 }}
      >
        <ClickAwayListener onClickAway={() => setOpen(false)}>
          <Paper
            elevation={0}
            sx={(theme) => ({
              mt: 0.5,
              minWidth: 220,
              borderRadius: 1.5,
              bgcolor: theme.palette.background.paper,
              boxShadow: isDark
                ? '0 8px 32px rgba(0,0,0,0.4)'
                : '0 8px 32px rgba(0,0,0,0.1)',
              overflow: 'hidden',
              py: 0.5,
            })}
          >
            <Typography
              sx={(theme) => ({
                px: 2, py: 1,
                fontSize: '0.65rem',
                fontWeight: 700,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: alpha(theme.palette.text.secondary, 0.6),
              })}
            >
              Theme
            </Typography>

            {themeDefinitions.map((t) => {
              const isActive = themeId === t.id;
              return (
                <Box
                  key={t.id}
                  onClick={() => {
                    onThemeChange(t.id);
                    setOpen(false);
                  }}
                  sx={(theme) => ({
                    px: 2, py: 1.25,
                    display: 'flex', alignItems: 'center', gap: 1.5,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    bgcolor: isActive
                      ? alpha(theme.palette.primary.main, 0.08)
                      : 'transparent',
                    borderLeft: '2px solid',
                    borderColor: isActive
                      ? theme.palette.primary.main
                      : 'transparent',
                    '&:hover': {
                      bgcolor: isActive
                        ? alpha(theme.palette.primary.main, 0.08)
                        : alpha(theme.palette.action.hover, 0.4),
                    },
                  })}
                >
                  {/* Color swatches */}
                  <Box sx={{ display: 'flex', gap: 0.25, flexShrink: 0 }}>
                    {t.swatch.map((color, i) => (
                      <Box
                        key={i}
                        sx={{
                          width: 12, height: 12,
                          borderRadius: '2px',
                          bgcolor: color,
                          border: '1px solid',
                          borderColor: alpha('#000', 0.06),
                        }}
                      />
                    ))}
                  </Box>

                  {/* Name + description */}
                  <Box sx={{ minWidth: 0 }}>
                    <Typography
                      sx={(theme) => ({
                        fontSize: '0.78rem',
                        fontWeight: isActive ? 700 : 500,
                        color: isActive
                          ? theme.palette.text.primary
                          : alpha(theme.palette.text.primary, 0.85),
                        lineHeight: 1.3,
                      })}
                    >
                      {t.name}
                    </Typography>
                    <Typography
                      sx={(theme) => ({
                        fontSize: '0.65rem',
                        color: alpha(theme.palette.text.secondary, 0.7),
                        lineHeight: 1.3,
                        mt: 0.1,
                      })}
                    >
                      {t.description}
                    </Typography>
                  </Box>

                  {/* Active check */}
                  {isActive && (
                    <Box
                      sx={(theme) => ({
                        ml: 'auto',
                        width: 6, height: 6,
                        borderRadius: '50%',
                        bgcolor: theme.palette.primary.main,
                        flexShrink: 0,
                      })}
                    />
                  )}
                </Box>
              );
            })}
          </Paper>
        </ClickAwayListener>
      </Popper>
    </>
  );
}

export default ThemeSwitcher;
