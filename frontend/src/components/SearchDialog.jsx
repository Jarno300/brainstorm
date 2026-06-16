import { useState, useCallback, useRef, useEffect } from 'react';
import {
  Dialog, DialogTitle, DialogContent, TextField, InputAdornment,
  List, ListItem, ListItemButton, ListItemText, Typography,
  Box, Chip, alpha, useTheme, IconButton, CircularProgress,
  Tabs, Tab,
} from '@mui/material';
import {
  Search as SearchIcon, Close as CloseIcon,
  Psychology as ChatIcon, Description as DocIcon,
  Folder as FolderIcon,
} from '@mui/icons-material';
import { searchAll } from '../api';
import useBrainstormStore from '../stores/brainstormStore';

export default function SearchDialog({ open, onClose }) {
  const theme = useTheme();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState(0);
  const inputRef = useRef(null);
  const debounceRef = useRef(null);

  const selectBrainstorm = useBrainstormStore((s) => s.selectBrainstorm);

  useEffect(() => {
    if (open && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
    if (!open) {
      setQuery('');
      setResults(null);
    }
  }, [open]);

  const doSearch = useCallback(async (q) => {
    if (!q || q.length < 2) {
      setResults(null);
      return;
    }
    setLoading(true);
    try {
      const res = await searchAll(q);
      setResults(res.data);
    } catch (err) {
      console.error('Search error:', err);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleChange = useCallback((e) => {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(val), 300);
  }, [doSearch]);

  const handleSelect = useCallback(async (brainstormId) => {
    onClose();
    await selectBrainstorm({ id: brainstormId });
  }, [onClose, selectBrainstorm]);

  const resultCounts = results ? {
    brainstorms: results.brainstorms?.length || 0,
    messages: results.messages?.length || 0,
    library: results.library?.length || 0,
  } : null;

  const tabItems = [
    { label: `Brainstorms (${resultCounts?.brainstorms || 0})`, icon: <ChatIcon sx={{ fontSize: 14 }} /> },
    { label: `Messages (${resultCounts?.messages || 0})`, icon: <ChatIcon sx={{ fontSize: 14 }} /> },
    { label: `Library (${resultCounts?.library || 0})`, icon: <DocIcon sx={{ fontSize: 14 }} /> },
  ];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1.5, pb: 1 }}>
        <SearchIcon sx={(theme) => ({ fontSize: 18, color: theme.palette.primary.light })} />
        <Typography sx={{ fontWeight: 700, fontSize: '0.95rem', flex: 1 }}>
          Search
        </Typography>
        <Typography sx={{ fontSize: '0.65rem', color: 'text.disabled', mr: 1 }}>
          ⌘K
        </Typography>
        <IconButton onClick={onClose} size="small" sx={{ borderRadius: 1 }}>
          <CloseIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ p: '0 !important', minHeight: 300 }}>
        <Box sx={{ px: 3, pt: 1, pb: 1.5 }}>
          <TextField
            inputRef={inputRef}
            fullWidth
            value={query}
            onChange={handleChange}
            placeholder="Search brainstorms, messages, notes..."
            variant="outlined"
            size="small"
            autoComplete="off"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  {loading ? <CircularProgress size={14} /> : <SearchIcon sx={{ fontSize: 16, color: 'text.disabled' }} />}
                </InputAdornment>
              ),
              sx: { borderRadius: 1.5, fontSize: '0.85rem' },
            }}
          />
        </Box>

        {results && (
          <>
            <Tabs
              value={tab}
              onChange={(_, v) => setTab(v)}
              sx={{ borderBottom: '1px solid', borderColor: 'divider', px: 2 }}
            >
              {tabItems.map((item, i) => (
                <Tab
                  key={i}
                  label={item.label}
                  icon={item.icon}
                  iconPosition="start"
                  sx={{
                    minHeight: 36, fontSize: '0.7rem', fontWeight: 600,
                    textTransform: 'none', gap: 0.5, px: 1.5,
                  }}
                />
              ))}
            </Tabs>

            <List sx={{ py: 0, maxHeight: 400, overflow: 'auto' }}>
              {/* Brainstorms tab */}
              {tab === 0 && results.brainstorms?.map((b) => (
                <ListItem key={b.id} disablePadding>
                  <ListItemButton onClick={() => handleSelect(b.id)} sx={{ py: 1.5, px: 3 }}>
                    <ListItemText
                      primary={
                        <Typography sx={{ fontWeight: 600, fontSize: '0.82rem' }}>
                          {b.title}
                        </Typography>
                      }
                      secondary={
                        b.summary ? (
                          <Typography sx={{ fontSize: '0.68rem', color: alpha(theme.palette.text.secondary, 0.6) }}>
                            {b.summary.slice(0, 120)}
                          </Typography>
                        ) : null
                      }
                    />
                  </ListItemButton>
                </ListItem>
              ))}

              {/* Messages tab */}
              {tab === 1 && results.messages?.map((m) => (
                <ListItem key={m.id} disablePadding>
                  <ListItemButton onClick={() => handleSelect(m.brainstorm_id)} sx={{ py: 1.5, px: 3 }}>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
                          <Chip
                            label={m.role === 'user' ? 'You' : 'AI'}
                            size="small"
                            sx={{
                              height: 16, fontSize: '0.55rem', fontWeight: 700,
                              bgcolor: m.role === 'user'
                                ? alpha(theme.palette.primary.main, 0.1)
                                : alpha(theme.palette.secondary.main, 0.1),
                              color: m.role === 'user'
                                ? theme.palette.primary.light
                                : theme.palette.secondary.light,
                            }}
                          />
                          <Typography sx={{ fontSize: '0.68rem', color: 'text.disabled' }}>
                            {m.brainstorm_title}
                          </Typography>
                        </Box>
                      }
                      secondary={
                        <Typography sx={{ fontSize: '0.7rem', color: alpha(theme.palette.text.secondary, 0.6), lineHeight: 1.5 }}>
                          {m.snippet}
                        </Typography>
                      }
                    />
                  </ListItemButton>
                </ListItem>
              ))}

              {/* Library tab */}
              {tab === 2 && results.library?.map((l) => (
                <ListItem key={l.id} disablePadding>
                  <ListItemButton onClick={() => handleSelect(l.brainstorm_id)} sx={{ py: 1.5, px: 3 }}>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
                          <FolderIcon sx={{ fontSize: 13, color: 'text.disabled' }} />
                          <Typography sx={{ fontSize: '0.78rem', fontWeight: 600 }}>
                            {l.folder_name}
                          </Typography>
                          <Typography sx={{ fontSize: '0.6rem', color: 'text.disabled' }}>
                            / {l.file_name}
                          </Typography>
                        </Box>
                      }
                      secondary={
                        <Typography sx={{ fontSize: '0.7rem', color: alpha(theme.palette.text.secondary, 0.6), lineHeight: 1.5 }}>
                          {l.snippet}
                        </Typography>
                      }
                    />
                  </ListItemButton>
                </ListItem>
              ))}

              {/* Empty state */}
              {results.total === 0 && (
                <Box sx={{ py: 6, textAlign: 'center' }}>
                  <Typography sx={{ fontSize: '0.8rem', color: 'text.disabled' }}>
                    No results for "{query}"
                  </Typography>
                </Box>
              )}
            </List>
          </>
        )}

        {!results && query.length >= 2 && !loading && (
          <Box sx={{ py: 6, textAlign: 'center' }}>
            <Typography sx={{ fontSize: '0.8rem', color: 'text.disabled' }}>
              Type to search...
            </Typography>
          </Box>
        )}
      </DialogContent>
    </Dialog>
  );
}
