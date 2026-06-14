import { useRef, useEffect, useState, useCallback } from 'react';
import { Box, Typography, TextField, IconButton, CircularProgress, alpha, Avatar, Collapse, Alert, Tooltip, Snackbar } from '@mui/material';
import { Send as SendIcon, Person as PersonIcon, SmartToy as BotIcon, AutoAwesome, ContentCopy as CopyIcon } from '@mui/icons-material';

function ThinkingText() {
    const letters = ['T', 'h', 'i', 'n', 'k', 'i', 'n', 'g'];

    return (
        <Box
            sx={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 0.05,
                '@keyframes letterWave': {
                    '0%, 80%, 100%': { transform: 'translateY(0)', opacity: 0.45 },
                    '40%': { transform: 'translateY(-3px)', opacity: 1 },
                },
            }}
        >
            {letters.map((letter, index) => (
                <Box
                    key={`${letter}-${index}`}
                    component="span"
                    sx={(theme) => ({
                        display: 'inline-block',
                        minWidth: letter === ' ' ? 4 : 'auto',
                        animation: 'letterWave 1.2s ease-in-out infinite',
                        animationDelay: `${index * 0.08}s`,
                        color: theme.palette.primary.light,
                    })}
                >
                    {letter}
                </Box>
            ))}
        </Box>
    );
}

function ChatTab({ messages, onSendMessage, sending, errorMessage }) {
    const [input, setInput] = useState('');
    const [copiedId, setCopiedId] = useState(null);
    const bottomRef = useRef(null);
    const inputRef = useRef(null);
    const [showCopySnackbar, setShowCopySnackbar] = useState(false);

    const handleCopy = useCallback(async (content, msgId) => {
        try {
            await navigator.clipboard.writeText(content);
            setCopiedId(msgId);
            setShowCopySnackbar(true);
            setTimeout(() => setCopiedId(null), 2000);
        } catch (err) {
            console.error('Failed to copy:', err);
        }
    }, []);

    useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages]);

    useEffect(() => {
        if (!sending && !errorMessage) inputRef.current?.focus();
    }, [sending, errorMessage]);

    const handleSend = () => {
        const val = input.trim();
        if (!val || sending) return;
        onSendMessage(val);
        setInput('');
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', position: 'relative' }}>
            {/* ── Messages ─────────────────────────────────────────── */}
            <Box sx={{
                flex: 1, overflow: 'auto', px: { xs: 2, md: 4 }, py: 3,
                display: 'flex', flexDirection: 'column', gap: 2.5,
                '& > :first-of-type': { mt: 'auto' },
            }}>
                {messages.length === 0 ? (
                    <Box sx={{
                        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                        py: 8, gap: 2, flex: 1,
                    }}>
                        <Box sx={(theme) => ({
                            width: 72, height: 72, borderRadius: 3.5,
                            background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.18)} 0%, ${alpha(theme.palette.primary.light, 0.1)} 100%)`,
                            border: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.15),
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            animation: 'subtleFloat 3s ease-in-out infinite',
                        })}>
                            <AutoAwesome sx={(theme) => ({ fontSize: 28, color: alpha(theme.palette.primary.light, 0.6) })} />
                        </Box>
                        <Box sx={{ textAlign: 'center', maxWidth: 280 }}>
                            <Typography sx={(theme) => ({
                                fontWeight: 600, color: alpha(theme.palette.text.primary, 0.8),
                                mb: 0.5, fontSize: '0.95rem',
                            })}>
                                Start a conversation
                            </Typography>
                            <Typography variant="body2" sx={(theme) => ({
                                color: alpha(theme.palette.text.secondary, 0.65), lineHeight: 1.6,
                            })}>
                                Send a message to begin brainstorming with AI.
                            </Typography>
                        </Box>
                    </Box>
                ) : (
                    messages.map((msg, i) => {
                        const isUser = msg.role === 'user';
                        const isThinking = msg.role === 'assistant' && msg.isThinking;
                        return (
                            <Box key={msg.id || i} className="message-bubble"
                                sx={{
                                    display: 'flex', gap: 1.5,
                                    flexDirection: isUser ? 'row-reverse' : 'row',
                                    alignItems: 'flex-start',
                                    maxWidth: '85%',
                                    alignSelf: isUser ? 'flex-end' : 'flex-start',
                                }}>
                                {/* ── Avatar ─────────────────────────────────── */}
                                <Avatar sx={(theme) => ({
                                    width: 30, height: 30, borderRadius: 2,
                                    bgcolor: isUser ? alpha(theme.palette.primary.main, 0.5) : 'transparent',
                                    border: isUser ? 'none' : '1px solid',
                                    borderColor: alpha(theme.palette.divider, 0.6),
                                    flexShrink: 0,
                                })}>
                                    {isUser
                                        ? <PersonIcon sx={(theme) => ({ fontSize: 16, color: alpha(theme.palette.text.primary, 0.85) })} />
                                        : <BotIcon sx={(theme) => ({ fontSize: 16, color: alpha(theme.palette.primary.light, 0.7) })} />
                                    }
                                </Avatar>

                                {/* ── Bubble ──────────────────────────────────── */}
                                <Box className="message-bubble-content" sx={(theme) => ({
                                    px: 2.5, py: 1.75,
                                    borderRadius: 2,
                                    border: isUser ? 'none' : '1px solid',
                                    borderColor: isUser ? 'none' : alpha(theme.palette.divider, 0.5),
                                    position: 'relative',
                                    boxShadow: isUser
                                        ? `0 4px 20px ${alpha(theme.palette.primary.main, 0.25)}`
                                        : 'none',
                                    '&:hover .copy-btn': { opacity: 1, transform: 'scale(1)' },
                                    ...(isUser ? {
                                        background: theme.palette.gradients.userBubble,
                                        borderBottomRightRadius: 4,
                                    } : {
                                        bgcolor: alpha(theme.palette.background.paper, 0.4),
                                        borderBottomLeftRadius: 4,
                                    }),
                                })}>
                                    {isThinking ? (
                                        <Box sx={(theme) => ({
                                            fontSize: '0.875rem',
                                            lineHeight: 1.7,
                                            color: theme.palette.text.primary,
                                            whiteSpace: 'pre-wrap',
                                            wordBreak: 'break-word',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 0.3,
                                        })}>
                                            <ThinkingText />
                                        </Box>
                                    ) : (
                                        <Typography sx={(theme) => ({
                                            fontSize: '0.875rem',
                                            lineHeight: 1.7,
                                            color: isUser ? '#FFFFFF' : theme.palette.text.primary,
                                            whiteSpace: 'pre-wrap',
                                            wordBreak: 'break-word',
                                        })}>
                                            {msg.content}
                                        </Typography>
                                    )}
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 0.75 }}>
                                        <Typography sx={(theme) => ({
                                            fontSize: '0.6rem',
                                            color: isUser ? alpha('#FFFFFF', 0.65) : alpha(theme.palette.text.secondary, 0.7),
                                            fontWeight: 500,
                                        })}>
                                            {isThinking ? 'now' : formatMessageTime(msg.created_at)}
                                        </Typography>
                                        {!isThinking && (
                                            <Tooltip title={copiedId === msg.id ? 'Copied!' : 'Copy message'} arrow>
                                                <IconButton
                                                    className="copy-btn"
                                                    size="small"
                                                    onClick={() => handleCopy(msg.content, msg.id)}
                                                    sx={(theme) => ({
                                                        width: 22,
                                                        height: 22,
                                                        borderRadius: 1,
                                                        opacity: 0,
                                                        transform: 'scale(0.8)',
                                                        transition: 'all 0.15s ease',
                                                        color: isUser ? alpha('#FFFFFF', 0.55) : alpha(theme.palette.text.secondary, 0.45),
                                                        '&:hover': {
                                                            bgcolor: isUser ? alpha('#FFFFFF', 0.15) : alpha(theme.palette.primary.main, 0.15),
                                                            color: isUser ? '#FFF' : theme.palette.primary.light,
                                                        },
                                                    })}
                                                    aria-label="Copy message"
                                                >
                                                    <CopyIcon sx={{ fontSize: 11 }} />
                                                </IconButton>
                                            </Tooltip>
                                        )}
                                    </Box>
                                </Box>
                            </Box>
                        );
                    })
                )}

                {/* ── Error ──────────────────────────────────────────── */}
                <Collapse in={Boolean(errorMessage)}>
                    <Alert severity="error" variant="filled"
                        sx={(theme) => ({
                            borderRadius: 2,
                            bgcolor: alpha(theme.palette.error.main, 0.15),
                            color: theme.palette.error.light,
                            border: '1px solid',
                            borderColor: alpha(theme.palette.error.main, 0.25),
                            '& .MuiAlert-icon': { color: theme.palette.error.light },
                            fontSize: '0.8rem',
                        })}>
                        {errorMessage}
                    </Alert>
                </Collapse>

                <div ref={bottomRef} />
            </Box>

            {/* ── Input Area ────────────────────────────────────────── */}
            <Box sx={(theme) => ({
                px: { xs: 2, md: 4 }, py: 2,
                borderTop: '1px solid', borderColor: alpha(theme.palette.divider, 0.6),
                bgcolor: alpha(theme.palette.background.default, 0.5),
                position: 'relative',
                '&::before': {
                    content: '""', position: 'absolute', top: 0, left: '10%', right: '10%',
                    height: '1px',
                    background: `linear-gradient(90deg, transparent, ${alpha(theme.palette.primary.main, 0.12)}, transparent)`,
                },
            })}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-end' }}>
                    <TextField
                        inputRef={inputRef}
                        fullWidth
                        multiline
                        maxRows={6}
                        placeholder="Type your message..."
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        disabled={sending}
                        variant="outlined"
                        slotProps={{
                            input: {
                                sx: (theme) => ({
                                    borderRadius: 1.5,
                                    bgcolor: alpha(theme.palette.background.paper, theme.palette.mode === 'dark' ? 0.6 : 0.5),
                                    border: '1px solid',
                                    borderColor: alpha(theme.palette.divider, 0.6),
                                    fontSize: '0.85rem',
                                    lineHeight: 1.6,
                                    color: theme.palette.text.primary,
                                    py: 1,
                                    transition: 'all 0.2s ease',
                                    '&:hover': {
                                        borderColor: alpha(theme.palette.primary.main, 0.2),
                                    },
                                    '&.Mui-focused': {
                                        borderColor: theme.palette.primary.main,
                                        boxShadow: `0 0 0 3px ${alpha(theme.palette.primary.main, 0.1)}`,
                                    },
                                    '& fieldset': { border: 'none' },
                                    '& textarea': {
                                        padding: '8px 16px !important',
                                        '&::placeholder': { color: alpha(theme.palette.text.secondary, 0.5), opacity: 1 },
                                    },
                                }),
                            },
                        }}
                    />
                    <IconButton onClick={handleSend} disabled={!input.trim() || sending}
                        sx={(theme) => ({
                            width: 44, height: 44, borderRadius: 1.5,
                            background: input.trim() && !sending
                                ? theme.palette.gradients.userBubble
                                : alpha(theme.palette.action.disabled, 0.1),
                            color: input.trim() && !sending ? '#fff' : alpha(theme.palette.text.disabled, 0.4),
                            boxShadow: input.trim() && !sending
                                ? `0 4px 16px ${alpha(theme.palette.primary.main, 0.3)}`
                                : 'none',
                            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                            '&:hover': input.trim() && !sending ? {
                                boxShadow: `0 6px 24px ${alpha(theme.palette.primary.main, 0.45)}`,
                                transform: 'translateY(-1px)',
                            } : {},
                            '&:active': input.trim() && !sending ? { transform: 'translateY(0)' } : {},
                            '&.Mui-disabled': {
                                background: alpha(theme.palette.action.disabled, 0.1),
                                color: alpha(theme.palette.text.disabled, 0.3),
                            },
                        })}>
                        {sending ? <CircularProgress size={18} sx={(theme) => ({ color: theme.palette.primary.light })} /> : <SendIcon sx={{ fontSize: 18 }} />}
                    </IconButton>
                </Box>
            </Box>

            {/* ── Keyboard shortcut hint ──────────────────────── */}
            <Box sx={{
                textAlign: 'center',
                pb: 0.25,
            }}>
                <Typography
                    sx={(theme) => ({
                        fontSize: '0.6rem',
                        color: alpha(theme.palette.text.secondary, 0.5),
                        fontWeight: 500,
                        letterSpacing: '0.02em',
                    })}
                >
                    ↵ Enter to send · ⇧↵ new line
                </Typography>
            </Box>

            {/* ── Copy snackbar ────────────────────────────────── */}
            <Snackbar
                open={showCopySnackbar}
                autoHideDuration={2000}
                onClose={() => setShowCopySnackbar(false)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
                sx={{ bottom: '80px !important' }}
            >
                <Alert
                    severity="success"
                    variant="filled"
                    sx={{
                        borderRadius: 2,
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        bgcolor: (theme) => alpha(theme.palette.success.main, 0.2),
                        color: 'success.light',
                        backdropFilter: 'blur(12px)',
                        border: '1px solid',
                        borderColor: (theme) => alpha(theme.palette.success.main, 0.3),
                        '& .MuiAlert-icon': { color: 'success.light' },
                    }}
                >
                    Copied to clipboard
                </Alert>
            </Snackbar>
        </Box>
    );
}

function formatMessageTime(createdAt) {
    if (!createdAt) return 'now';
    const date = new Date(createdAt);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const isYesterday = date.toDateString() === yesterday.toDateString();
    const time = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (isToday) return time;
    if (isYesterday) return `Yesterday ${time}`;
    return `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${time}`;
}

export default ChatTab;