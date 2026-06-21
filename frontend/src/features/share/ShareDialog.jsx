import { useState } from 'react';
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Typography, Box, TextField, IconButton, Tooltip, alpha, Alert,
} from '@mui/material';
import {
  Share as ShareIcon, ContentCopy as CopyIcon, LinkOff as RevokeIcon,
} from '@mui/icons-material';
import { enableSharing, disableSharing } from '../../api';

function ShareDialog({ open, onClose, brainstormId }) {
  const [shareUrl, setShareUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const [isShared, setIsShared] = useState(false);

  const handleEnable = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await enableSharing(brainstormId);
      setShareUrl(res.data.share_url);
      setIsShared(true);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to enable sharing');
    } finally {
      setLoading(false);
    }
  };

  const handleDisable = async () => {
    setLoading(true);
    setError('');
    try {
      await disableSharing(brainstormId);
      setShareUrl('');
      setIsShared(false);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to disable sharing');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select the text field
      const input = document.querySelector('#share-url-input');
      if (input) input.select();
    }
  };

  const handleClose = () => {
    setError('');
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5, fontWeight: 700, fontSize: '1rem' }}>
        <ShareIcon sx={(t) => ({ color: t.palette.primary.light, fontSize: 20 })} />
        Share Brainstorm
      </DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2, borderRadius: 1, fontSize: '0.8rem' }}>
            {error}
          </Alert>
        )}

        {!isShared ? (
          <Box sx={{ textAlign: 'center', py: 2 }}>
            <Typography sx={{ mb: 1, fontWeight: 600, fontSize: '0.9rem' }}>
              Create a read-only link
            </Typography>
            <Typography variant="body2" sx={(t) => ({ color: alpha(t.palette.text.secondary, 0.6), fontSize: '0.8rem', mb: 2 })}>
              Anyone with the link can view your topics and library in read-only mode.
            </Typography>
            <Button
              variant="contained"
              startIcon={<ShareIcon />}
              onClick={handleEnable}
              disabled={loading}
              sx={{ borderRadius: 1, textTransform: 'none', fontWeight: 600, px: 3 }}
            >
              {loading ? 'Creating...' : 'Generate share link'}
            </Button>
          </Box>
        ) : (
          <Box sx={{ py: 1 }}>
            <Typography sx={{ fontWeight: 600, fontSize: '0.85rem', mb: 1 }}>
              Share link
            </Typography>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <TextField
                id="share-url-input"
                fullWidth
                size="small"
                value={shareUrl}
                onClick={(e) => e.target.select()}
                readOnly
                sx={{
                  '& .MuiOutlinedInput-root': {
                    borderRadius: 1,
                    fontSize: '0.8rem',
                    fontFamily: 'monospace',
                  },
                }}
              />
              <Tooltip title={copied ? 'Copied!' : 'Copy link'} arrow>
                <IconButton
                  onClick={handleCopy}
                  size="small"
                  sx={(t) => ({
                    width: 36, height: 36, borderRadius: 1,
                    border: '1px solid', borderColor: alpha(t.palette.divider, 0.5),
                    color: copied ? t.palette.success.light : alpha(t.palette.text.secondary, 0.5),
                  })}
                >
                  <CopyIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
              <Tooltip title="Revoke link" arrow>
                <IconButton
                  onClick={handleDisable}
                  disabled={loading}
                  size="small"
                  sx={(t) => ({
                    width: 36, height: 36, borderRadius: 1,
                    border: '1px solid', borderColor: alpha(t.palette.error.main, 0.3),
                    color: alpha(t.palette.error.main, 0.6),
                    '&:hover': { bgcolor: alpha(t.palette.error.main, 0.1) },
                  })}
                >
                  <RevokeIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
            </Box>
            <Typography variant="caption" sx={(t) => ({ color: alpha(t.palette.text.secondary, 0.5), mt: 1, display: 'block', fontSize: '0.7rem' })}>
              Anyone with this link can view your knowledge map and library.
            </Typography>
          </Box>
        )}
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={handleClose} sx={{ textTransform: 'none', fontWeight: 600, fontSize: '0.8rem' }}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

export default ShareDialog;
