import { Box } from '@mui/material';
import { CARD_COLORS } from './cardConstants';

function CardColorPicker({ color, isDark, showColorPicker, setShowColorPicker, setCustomColor }) {
    return (
        <Box className="card-action" sx={{ position: 'relative' }}>
            <Box onClick={() => setShowColorPicker(!showColorPicker)}
                sx={{
                    width: 18, height: 18, borderRadius: '50%', bgcolor: color, cursor: 'pointer',
                    border: '2px solid', borderColor: 'rgba(255,255,255,0.6)',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
                }} />
            {showColorPicker && (
                <Box sx={{
                    position: 'absolute', top: 24, right: 0, display: 'flex', gap: 0.5, p: 0.75,
                    borderRadius: 2, bgcolor: 'rgba(18,18,18,0.97)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    boxShadow: '0 4px 16px rgba(0,0,0,0.15)', zIndex: 30,
                }}>
                    {CARD_COLORS.map(c => (
                        <Box key={c.key} onClick={() => { setCustomColor(isDark ? c.dark : c.light); setShowColorPicker(false); }}
                            sx={{
                                width: 18, height: 18, borderRadius: '50%', bgcolor: isDark ? c.dark : c.light,
                                cursor: 'pointer',
                                border: color === (isDark ? c.dark : c.light) ? '2px solid #fff' : '2px solid transparent',
                                '&:hover': { transform: 'scale(1.15)' },
                            }} />
                    ))}
                </Box>
            )}
        </Box>
    );
}

export default CardColorPicker;
