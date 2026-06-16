import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Box, Typography } from '@mui/material';

/**
 * Renders markdown content.
 *
 * variant: 'tooltip' (dark bg, light text) | 'card' (light bg, dark text)
 */
export default function MarkdownRenderer({ content, variant = 'tooltip' }) {
    if (!content) return null;

    const isTooltip = variant === 'tooltip';

    const c = isTooltip
        ? {
            h1: '#fff', h2: '#fff', h3: 'rgba(255,255,255,0.9)',
            p: 'rgba(255,255,255,0.85)', strong: 'rgba(255,255,255,0.95)',
            em: 'rgba(255,255,255,0.8)', li: 'rgba(255,255,255,0.8)',
            code: 'rgba(255,255,255,0.9)', codeBg: 'rgba(255,255,255,0.08)',
            preBg: 'rgba(0,0,0,0.3)', preFg: 'rgba(255,255,255,0.85)',
            link: 'rgba(100,180,255,0.9)', blockquote: 'rgba(255,255,255,0.7)',
            blockquoteBorder: 'rgba(255,255,255,0.15)',
            th: 'rgba(255,255,255,0.9)', thBorder: 'rgba(255,255,255,0.15)',
            td: 'rgba(255,255,255,0.75)', hr: 'rgba(255,255,255,0.08)',
        }
        : {
            h1: 'text.primary', h2: 'text.primary', h3: 'text.primary',
            p: 'text.secondary', strong: 'text.primary',
            em: 'text.secondary', li: 'text.secondary',
            code: 'text.primary', codeBg: 'rgba(0,0,0,0.06)',
            preBg: 'rgba(0,0,0,0.04)', preFg: 'text.secondary',
            link: 'primary.main', blockquote: 'text.secondary',
            blockquoteBorder: 'rgba(0,0,0,0.12)',
            th: 'text.primary', thBorder: 'rgba(0,0,0,0.08)',
            td: 'text.secondary', hr: 'rgba(0,0,0,0.08)',
        };

    const fs = (tooltipSize, cardSize) => isTooltip ? tooltipSize : cardSize;

    return (
        <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
                h1: ({ children, ...props }) => (
                    <Typography component="h1" sx={{
                        fontSize: fs('0.78rem', '0.85rem'), fontWeight: 700,
                        color: c.h1, mb: 0.5, mt: 1, lineHeight: 1.4,
                    }} {...props}>{children}</Typography>
                ),
                h2: ({ children, ...props }) => (
                    <Typography component="h2" sx={{
                        fontSize: fs('0.73rem', '0.8rem'), fontWeight: 700,
                        color: c.h2, mb: 0.4, mt: 0.75, lineHeight: 1.4,
                    }} {...props}>{children}</Typography>
                ),
                h3: ({ children, ...props }) => (
                    <Typography component="h3" sx={{
                        fontSize: fs('0.69rem', '0.75rem'), fontWeight: 600,
                        color: c.h3, mb: 0.3, mt: 0.5, lineHeight: 1.4,
                    }} {...props}>{children}</Typography>
                ),
                p: ({ children, ...props }) => (
                    <Typography component="p" sx={{
                        fontSize: fs('0.68rem', '0.7rem'), lineHeight: 1.6,
                        color: c.p, mb: 0.5, '&:last-child': { mb: 0 },
                    }} {...props}>{children}</Typography>
                ),
                strong: ({ children }) => (
                    <Box component="span" sx={{ fontWeight: 600, color: c.strong }}>{children}</Box>
                ),
                em: ({ children }) => (
                    <Box component="span" sx={{ fontStyle: 'italic', color: c.em }}>{children}</Box>
                ),
                ul: ({ children, ...props }) => (
                    <Box component="ul" sx={{ pl: 2, mb: 0.5, mt: 0 }} {...props}>{children}</Box>
                ),
                ol: ({ children, ...props }) => (
                    <Box component="ol" sx={{ pl: 2, mb: 0.5, mt: 0 }} {...props}>{children}</Box>
                ),
                li: ({ children, ...props }) => (
                    <Typography component="li" sx={{
                        fontSize: fs('0.68rem', '0.7rem'), lineHeight: 1.55,
                        color: c.li, mb: 0.2,
                    }} {...props}>{children}</Typography>
                ),
                code: ({ children, className, ...props }) => {
                    const isInline = !className;
                    if (isInline) {
                        return (
                            <Box component="code" sx={{
                                fontSize: '0.64rem', bgcolor: c.codeBg, color: c.code,
                                px: 0.5, py: 0.15, borderRadius: '3px', fontFamily: 'monospace',
                            }} {...props}>{children}</Box>
                        );
                    }
                    return (
                        <Box component="pre" sx={{
                            fontSize: '0.62rem', bgcolor: c.preBg, color: c.preFg,
                            p: 1, borderRadius: 1, overflow: 'auto', mb: 0.5,
                            fontFamily: 'monospace', lineHeight: 1.5,
                        }}>
                            <code className={className} {...props}>{children}</code>
                        </Box>
                    );
                },
                a: ({ children, href, ...props }) => (
                    <Box component="a" href={href} target="_blank" rel="noopener noreferrer" sx={{
                        color: c.link, textDecoration: 'underline', fontSize: 'inherit',
                    }} {...props}>{children}</Box>
                ),
                blockquote: ({ children, ...props }) => (
                    <Box component="blockquote" sx={{
                        borderLeft: `3px solid ${c.blockquoteBorder}`, pl: 1.5,
                        my: 0.5, color: c.blockquote, fontStyle: 'italic',
                    }} {...props}>{children}</Box>
                ),
                hr: (props) => (
                    <Box component="hr" sx={{
                        border: 'none', borderTop: `1px solid ${c.hr}`, my: 1,
                    }} {...props} />
                ),
                table: ({ children }) => (
                    <Box component="table" sx={{
                        width: '100%', borderCollapse: 'collapse',
                        fontSize: '0.64rem', mb: 0.5,
                    }}>{children}</Box>
                ),
                th: ({ children }) => (
                    <Box component="th" sx={{
                        borderBottom: `1px solid ${c.thBorder}`, px: 1, py: 0.5,
                        textAlign: 'left', fontWeight: 600, color: c.th,
                    }}>{children}</Box>
                ),
                td: ({ children }) => (
                    <Box component="td" sx={{
                        borderBottom: `1px solid ${c.thBorder}`, px: 1, py: 0.5, color: c.td,
                    }}>{children}</Box>
                ),
            }}
        >
            {content}
        </ReactMarkdown>
    );
}
