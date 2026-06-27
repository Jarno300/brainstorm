import { Box, Typography, Tooltip, Chip, alpha, useTheme } from '@mui/material';
import { Link as LinkIcon } from '@mui/icons-material';
import MarkdownRenderer from '../../../components/MarkdownRenderer';
import { formatLabel } from '../canvasUtils';

function CardDisplayMode({ topic, exploringName, libraryEntry, librarySections, summaryText, color, onSelect }) {
    const theme = useTheme();
    const isConnectionCard = topic.name.endsWith('-connection');

    return (
        <>
            {/* Connection card header */}
            {isConnectionCard && (
                <Box sx={(theme) => ({
                    mx: -2.5, mt: -2, mb: 2, px: 2.5, py: 0.5,
                    borderTopLeftRadius: 7, borderTopRightRadius: 7,
                    bgcolor: alpha(theme.palette.primary.main, 0.06),
                    borderBottom: '1px solid', borderColor: alpha(theme.palette.primary.main, 0.08),
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5,
                })}>
                    <LinkIcon sx={{ fontSize: 11, color: alpha(theme.palette.primary.light, 0.5) }} />
                    <Typography sx={{ fontSize: '0.58rem', fontWeight: 600, color: alpha(theme.palette.primary.light, 0.5), textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        Connection
                    </Typography>
                </Box>
            )}

            {/* Title */}
            <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: 'text.primary', lineHeight: 1.3, mb: summaryText ? 1 : 0, pr: 4 }}>
                {formatLabel(isConnectionCard ? topic.name.replace(/-connection$/, '') : topic.name)}
            </Typography>

            {/* Summary */}
            {summaryText && (
                <Typography sx={(theme) => ({
                    fontSize: '0.7rem', fontWeight: 400,
                    color: alpha(theme.palette.text.secondary, 0.6),
                    lineHeight: 1.55, fontStyle: 'italic',
                    mb: librarySections.length > 0 ? 1.5 : 0,
                })}>
                    {summaryText}
                </Typography>
            )}

            {/* Library sections — title only, full body on hover */}
            {librarySections.length > 0 && (
                <Box sx={{ mb: 0 }}>
                    {librarySections.slice(0, 5).map((section, i) => (
                        <Tooltip key={i}
                            title={
                                <Box sx={{ maxWidth: 360, p: 0.5 }}>
                                    <Typography sx={{ fontSize: '0.72rem', fontWeight: 700, mb: 0.75, color: '#fff' }}>
                                        {section.title}
                                    </Typography>
                                    <MarkdownRenderer content={section.body} />
                                </Box>
                            }
                            arrow placement="right" enterDelay={300} leaveDelay={100}
                            slotProps={{
                                tooltip: {
                                    sx: {
                                        bgcolor: alpha(theme.palette.background.default, 0.97),
                                        backdropFilter: 'blur(12px)',
                                        border: '1px solid', borderColor: alpha(color, 0.2),
                                        borderRadius: 2, boxShadow: '0 8px 32px rgba(0,0,0,0.25)',
                                        p: 1.5, maxWidth: 360,
                                        '& .MuiTooltip-arrow': { color: alpha(theme.palette.background.default, 0.97) },
                                    },
                                },
                            }}
                        >
                            <Box sx={{
                                mb: i < Math.min(librarySections.length - 1, 4) - 1 ? 0.75 : 0,
                                pl: 1.5, borderLeft: `2px solid ${alpha(color, 0.2)}`,
                                cursor: 'help', '&:hover': { borderLeftColor: alpha(color, 0.5) },
                            }}>
                                <Typography sx={{ fontSize: '0.7rem', fontWeight: 600, color: alpha(color, 0.75), textTransform: 'uppercase', letterSpacing: '0.04em', py: '1px' }}>
                                    {section.title}
                                </Typography>
                            </Box>
                        </Tooltip>
                    ))}
                </Box>
            )}

            {/* Suggestion pills — colored by category (hidden for connection cards) */}
            {!isConnectionCard && topic.suggestions && topic.suggestions.length > 0 && (
                <>
                    <Box sx={(theme) => ({ height: 1, my: 1.5, bgcolor: alpha(theme.palette.divider, 0.1) })} />
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                        {topic.suggestions.slice(0, 4).map((s, i) => {
                            const isExploring = exploringName && formatLabel(s.name) === exploringName;
                            const kindMatch = (s.description || '').match(/^\[(Parent|Child|Related)\]/);
                            const kindLabel = kindMatch ? kindMatch[1] : '';
                            const kindColors = {
                                Parent: { bg: 'rgba(124,58,237,0.12)', border: 'rgba(124,58,237,0.3)', text: '#a78bfa' },
                                Child: { bg: 'rgba(5,150,105,0.12)', border: 'rgba(5,150,105,0.3)', text: '#34d399' },
                                Related: { bg: 'rgba(2,132,199,0.12)', border: 'rgba(2,132,199,0.3)', text: '#38bdf8' },
                            };
                            const kc = kindColors[kindLabel] || { bg: alpha(color, 0.08), border: 'transparent', text: alpha(color, 0.75) };
                            return (
                                <Chip key={s.id || i}
                                    label={formatLabel(s.name)} size="small"
                                    onClick={(e) => { e.stopPropagation(); if (!isExploring) onSelect(s, true); }}
                                    sx={{
                                        height: 20, fontSize: '0.62rem', fontWeight: 600, borderRadius: '5px',
                                        bgcolor: isExploring ? alpha('#888', 0.06) : kc.bg,
                                        color: isExploring ? alpha('#888', 0.3) : kc.text,
                                        border: '1px solid', borderColor: isExploring ? 'transparent' : kc.border,
                                        cursor: isExploring ? 'default' : 'pointer', transition: 'all 0.2s',
                                        '&:hover': isExploring ? {} : { bgcolor: kindLabel ? kc.bg.replace('0.12', '0.22') : alpha(color, 0.16) },
                                        '& .MuiChip-label': { px: 0.8 },
                                    }}
                                />
                            );
                        })}
                    </Box>
                </>
            )}
        </>
    );
}

export default CardDisplayMode;
