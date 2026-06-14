import { useState } from 'react';
import {
  Box, Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Button, Typography, alpha, Alert,
} from '@mui/material';
import { Psychology as BrainIcon } from '@mui/icons-material';
import { useAuth } from './AuthContext';

function RegisterDialog({ open, onSwitchToLogin }) {
  const { register } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);
    try {
      await register(email, password);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} maxWidth="xs" fullWidth>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogTitle sx={{ textAlign: 'center', pt: 4, pb: 1 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1.5 }}>
            <Box sx={(theme) => ({
              width: 48, height: 48, borderRadius: 2.5,
              background: theme.palette.gradients.primary,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: (t) => `0 4px 16px ${alpha(t.palette.primary.main, 0.3)}`,
            })}>
              <BrainIcon sx={{ color: '#fff', fontSize: 24 }} />
            </Box>
            <Typography sx={{ fontWeight: 700, fontSize: '1.1rem' }}>
              Create your account
            </Typography>
            <Typography variant="body2" sx={(theme) => ({
              color: alpha(theme.palette.text.secondary, 0.6),
              fontSize: '0.8rem',
            })}>
              Start brainstorming with AI
            </Typography>
          </Box>
        </DialogTitle>
        <DialogContent sx={{ pb: 1 }}>
          {error && (
            <Alert severity="error" sx={{ mb: 2, borderRadius: 1, fontSize: '0.8rem' }}>
              {error}
            </Alert>
          )}
          <TextField
            fullWidth
            size="small"
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 1 } }}
            disabled={loading}
            autoFocus
          />
          <TextField
            fullWidth
            size="small"
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            sx={{ mb: 2, '& .MuiOutlinedInput-root': { borderRadius: 1 } }}
            disabled={loading}
          />
          <TextField
            fullWidth
            size="small"
            label="Confirm password"
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            sx={{ '& .MuiOutlinedInput-root': { borderRadius: 1 } }}
            disabled={loading}
          />
        </DialogContent>
        <DialogActions sx={{ flexDirection: 'column', px: 3, pb: 3, gap: 1 }}>
          <Button
            type="submit"
            variant="contained"
            fullWidth
            disabled={loading || !email || !password || !confirm}
            sx={{
              borderRadius: 1, textTransform: 'none', fontWeight: 700,
              py: 1.2, fontSize: '0.85rem',
            }}
          >
            {loading ? 'Creating account...' : 'Create account'}
          </Button>
          <Button
            fullWidth
            onClick={onSwitchToLogin}
            disabled={loading}
            sx={{
              textTransform: 'none', fontWeight: 600, fontSize: '0.8rem',
              color: (t) => alpha(t.palette.text.secondary, 0.6),
              '&:hover': { bgcolor: 'transparent', color: 'text.primary' },
            }}
          >
            Already have an account? Sign in
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}

export default RegisterDialog;
