import { useState, useRef, useCallback } from 'react';
import {
  Box, IconButton, Popper, Paper, ClickAwayListener, Typography, alpha, useTheme, Divider,
} from '@mui/material';
import { Settings as SettingsIcon, Add as AddIcon, CheckCircle as CheckIcon } from '@mui/icons-material';

const BUILT_IN_MODELS = [
  { id: 'ollama/llama3.2:1b',         label: 'Ollama · llama3.2:1b',         provider: 'ollama' },
  { id: 'openai/gpt-4o-mini',         label: 'OpenAI · gpt-4o-mini',         provider: 'openai' },
  { id: 'anthropic/claude-3-5-sonnet-latest', label: 'Anthropic · claude-3-5-sonnet-latest', provider: 'anthropic' },
];

function loadCustomModels() {
  try {
    return JSON.parse(localStorage.getItem('brainstorm-custom-models') || '[]');
  } catch {
    return [];
  }
}

function saveCustomModels(models) {
  localStorage.setItem('brainstorm-custom-models', JSON.stringify(models));
}

function ModelSwitcher({ currentModel, onModelChange, onAddModel }) {
  const [open, setOpen] = useState(false);
  const [customModels, setCustomModels] = useState(loadCustomModels);
  const anchorRef = useRef(null);
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  const refreshCustomModels = useCallback(() => {
    setCustomModels(loadCustomModels());
  }, []);

  const allModels = [
    ...BUILT_IN_MODELS,
    ...customModels.map((m) => ({
      id: `${m.provider}/${m.modelName}`,
      label: m.displayName || `${m.provider} · ${m.modelName}`,
      provider: m.provider,
      isCustom: true,
    })),
  ];

  const handleSelect = (modelId) => {
    onModelChange(modelId);
    setOpen(false);
  };

  const handleAddClick = () => {
    setOpen(false);
    // Small delay so the popper closes before modal opens
    setTimeout(() => {
      onAddModel(refreshCustomModels);
    }, 100);
  };

  return (
    <>
      <IconButton
        ref={anchorRef}
        onClick={() => setOpen((v) => !v)}
        size="small"
        sx={(t) => ({
          width: 30, height: 30, borderRadius: 1,
          border: '1px solid',
          borderColor: alpha(t.palette.divider, 0.6),
          color: alpha(t.palette.text.secondary, 0.55),
          transition: 'all 0.2s ease',
          '&:hover': {
            bgcolor: alpha(t.palette.primary.main, 0.08),
            color: t.palette.primary.light,
            borderColor: alpha(t.palette.primary.main, 0.15),
          },
        })}
      >
        <SettingsIcon sx={{ fontSize: 15 }} />
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
            sx={(t) => ({
              mt: 0.5,
              minWidth: 260,
              borderRadius: 1.5,
              border: '1px solid',
              borderColor: alpha(t.palette.divider, 0.6),
              bgcolor: t.palette.background.paper,
              boxShadow: isDark
                ? '0 8px 32px rgba(0,0,0,0.4)'
                : '0 8px 32px rgba(0,0,0,0.1)',
              overflow: 'hidden',
              py: 0.5,
            })}
          >
            <Typography
              sx={(t) => ({
                px: 2, py: 1,
                fontSize: '0.65rem',
                fontWeight: 700,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: alpha(t.palette.text.secondary, 0.6),
              })}
            >
              Model
            </Typography>

            {allModels.map((m, i) => {
              const isActive = currentModel === m.id;
              return (
                <Box
                  key={m.id}
                  onClick={() => handleSelect(m.id)}
                  sx={(t) => ({
                    px: 2, py: 1.25,
                    display: 'flex', alignItems: 'center', gap: 1.5,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                    bgcolor: isActive
                      ? alpha(t.palette.primary.main, 0.08)
                      : 'transparent',
                    borderLeft: '2px solid',
                    borderColor: isActive
                      ? t.palette.primary.main
                      : 'transparent',
                    '&:hover': {
                      bgcolor: isActive
                        ? alpha(t.palette.primary.main, 0.08)
                        : alpha(t.palette.action.hover, 0.4),
                    },
                  })}
                >
                  {/* Provider icon */}
                  <Box
                    sx={(t) => ({
                      width: 22, height: 22, borderRadius: 0.5,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: '0.6rem',
                      fontWeight: 700,
                      bgcolor: isActive
                        ? alpha(t.palette.primary.main, 0.12)
                        : alpha(t.palette.action.hover, 0.3),
                      color: isActive
                        ? t.palette.primary.light
                        : alpha(t.palette.text.secondary, 0.6),
                      flexShrink: 0,
                    })}
                  >
                    {m.provider.charAt(0).toUpperCase()}
                  </Box>

                  {/* Name */}
                  <Typography
                    sx={(t) => ({
                      flex: 1,
                      fontSize: '0.78rem',
                      fontWeight: isActive ? 700 : 500,
                      color: isActive
                        ? t.palette.text.primary
                        : alpha(t.palette.text.primary, 0.85),
                      lineHeight: 1.3,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    })}
                  >
                    {m.label}
                  </Typography>

                  {/* Active indicator */}
                  {isActive && (
                    <CheckIcon
                      sx={(t) => ({
                        fontSize: 14,
                        color: t.palette.primary.light,
                        flexShrink: 0,
                      })}
                    />
                  )}
                </Box>
              );
            })}

            <Divider sx={(t) => ({ mx: 2, my: 0.5, borderColor: alpha(t.palette.divider, 0.5) })} />

            {/* Add Model */}
            <Box
              onClick={handleAddClick}
              sx={(t) => ({
                px: 2, py: 1.25,
                display: 'flex', alignItems: 'center', gap: 1.5,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                color: alpha(t.palette.primary.light, 0.8),
                '&:hover': {
                  bgcolor: alpha(t.palette.primary.main, 0.06),
                  color: t.palette.primary.light,
                },
              })}
            >
              <AddIcon sx={{ fontSize: 18, flexShrink: 0 }} />
              <Typography
                sx={{
                  fontSize: '0.78rem',
                  fontWeight: 600,
                  lineHeight: 1.3,
                }}
              >
                Add model
              </Typography>
            </Box>
          </Paper>
        </ClickAwayListener>
      </Popper>
    </>
  );
}

export { BUILT_IN_MODELS, loadCustomModels, saveCustomModels };
export default ModelSwitcher;
