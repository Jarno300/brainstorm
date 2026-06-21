import { useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Button, Typography, alpha, Box, MenuItem, Select, FormControl, InputLabel,
} from '@mui/material';
import { saveCustomModels, loadCustomModels } from './ModelSwitcher';
import { updateProviderSettings } from '../../api';

const PROVIDERS = [
  { value: 'ollama',    label: 'Ollama',    defaultUrl: 'http://localhost:11434', needsKey: false },
  { value: 'openai',    label: 'OpenAI',    defaultUrl: 'https://api.openai.com/v1', needsKey: true },
  { value: 'anthropic', label: 'Anthropic', defaultUrl: 'https://api.anthropic.com', needsKey: true },
];

const EXAMPLE_MODELS = {
  ollama:    { placeholder: 'e.g. llama3.2:1b, mistral, codellama' },
  openai:    { placeholder: 'e.g. gpt-4, gpt-4o, gpt-4o-mini' },
  anthropic: { placeholder: 'e.g. claude-3-5-sonnet-latest, claude-opus-4-20250514' },
};

function AddModelModal({ open, onClose, onSaved }) {
  const [provider, setProvider] = useState('openai');
  const [modelName, setModelName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState('');
  const [errors, setErrors] = useState({});

  // Reset form when opening
  const handleEnter = () => {
    setProvider('openai');
    setModelName('');
    setDisplayName('');
    setApiKey('');
    setBaseUrl('');
    setErrors({});
  };

  const handleClose = () => {
    setErrors({});
    onClose();
  };

  const selectedProvider = PROVIDERS.find((p) => p.value === provider);

  const validate = () => {
    const e = {};
    if (!modelName.trim()) e.modelName = 'Model name is required';
    if (selectedProvider?.needsKey && !apiKey.trim()) e.apiKey = 'API key is required';
    if (!baseUrl.trim()) e.baseUrl = 'Base URL is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;

    const newModel = {
      provider,
      modelName: modelName.trim(),
      displayName: displayName.trim() || `${selectedProvider.label} · ${modelName.trim()}`,
      apiKey: apiKey.trim(),
      baseUrl: baseUrl.trim(),
      addedAt: new Date().toISOString(),
    };

    const existing = loadCustomModels();
    // Avoid duplicates
    const dup = existing.find(
      (m) => m.provider === newModel.provider && m.modelName === newModel.modelName,
    );
    if (dup) {
      setErrors({ modelName: 'This model already exists in your list' });
      return;
    }

    // Save to backend (API key + base URL for this provider)
    try {
      await updateProviderSettings(provider, {
        api_key: newModel.apiKey || undefined,
        base_url: newModel.baseUrl || undefined,
      });
    } catch (err) {
      console.error('Failed to save provider settings to backend:', err);
      // Continue anyway — local storage still works
    }

    saveCustomModels([...existing, newModel]);
    onSaved?.();
    handleClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      TransitionProps={{ onEnter: handleEnter }}
      maxWidth="xs"
      fullWidth
    >
      <DialogTitle
        sx={{
          fontWeight: 700, fontSize: '1.05rem', pb: 1,
          display: 'flex', alignItems: 'center', gap: 1,
        }}
      >
        Add Model
      </DialogTitle>

      <DialogContent sx={{ pb: 1 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5, mt: 0.5 }}>
          {/* Provider */}
          <FormControl size="small" fullWidth>
            <InputLabel sx={{ fontSize: '0.825rem' }}>Provider</InputLabel>
            <Select
              value={provider}
              label="Provider"
              onChange={(e) => {
                const p = e.target.value;
                setProvider(p);
                const prov = PROVIDERS.find((pr) => pr.value === p);
                setBaseUrl(prov?.defaultUrl || '');
                setApiKey('');
              }}
              sx={{ borderRadius: 1, fontSize: '0.825rem' }}
            >
              {PROVIDERS.map((p) => (
                <MenuItem key={p.value} value={p.value} sx={{ fontSize: '0.825rem' }}>
                  {p.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {/* Model name */}
          <TextField
            size="small"
            label="Model name"
            placeholder={EXAMPLE_MODELS[provider]?.placeholder || 'Model name'}
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            error={Boolean(errors.modelName)}
            helperText={errors.modelName}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1 } }}
          />

          {/* Display name */}
          <TextField
            size="small"
            label="Display label (optional)"
            placeholder={`${selectedProvider?.label || 'Provider'} · ${modelName || 'model'}`}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1 } }}
          />

          {/* API Key */}
          {selectedProvider?.needsKey && (
            <TextField
              size="small"
              label="API key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              error={Boolean(errors.apiKey)}
              helperText={errors.apiKey || 'Stored locally in your browser'}
              sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1 } }}
            />
          )}

          {/* Base URL */}
          <TextField
            size="small"
            label="Base URL"
            placeholder={selectedProvider?.defaultUrl || 'http://localhost:11434'}
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            error={Boolean(errors.baseUrl)}
            helperText={errors.baseUrl}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1 } }}
          />
        </Box>

        <Typography
          sx={(theme) => ({
            mt: 2,
            fontSize: '0.7rem',
            color: alpha(theme.palette.text.secondary, 0.6),
            lineHeight: 1.5,
          })}
        >
          API keys are stored securely on the server and are sent directly
          to the AI provider when making requests. Never shared with third parties.
        </Typography>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2.5, gap: 1 }}>
        <Button
          onClick={handleClose}
          sx={(t) => ({
            color: alpha(t.palette.text.primary, 0.6),
            textTransform: 'none', fontWeight: 600, borderRadius: 1,
            px: 2.5, py: 1, fontSize: '0.85rem',
            '&:hover': { bgcolor: alpha(t.palette.action.hover, 0.5), color: t.palette.text.primary },
          })}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          sx={{
            borderRadius: 1, textTransform: 'none', fontWeight: 700,
            px: 2.5, py: 1, fontSize: '0.85rem',
          }}
        >
          Add Model
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default AddModelModal;
