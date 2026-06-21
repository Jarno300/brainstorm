import { Box, Typography, List, alpha } from '@mui/material';
import { Psychology as BrainIcon } from '@mui/icons-material';
import BrainstormItem from './BrainstormItem';

function BrainstormList({ brainstorms, activeBrainstorm, onSelect, onDelete, editingId, editTitle, editingRef, onStartEdit, onEditTitleChange, onEditKeyDown, onSaveEdit, searchQuery }) {
    if (brainstorms.length === 0) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    py: 6,
                    px: 2,
                    gap: 1.5,
                }}
            >
                <BrainIcon
                    sx={(theme) => ({
                        fontSize: 36,
                        color: alpha(theme.palette.text.disabled, 0.4),
                        opacity: 0.5,
                    })}
                    className="empty-state-icon"
                />
                <Typography
                    variant="body2"
                    sx={(theme) => ({ color: alpha(theme.palette.text.secondary, 0.6), textAlign: 'center', lineHeight: 1.5 })}
                >
                    {searchQuery ? 'No matching sessions.' : 'No brainstorms yet.\nEnter a topic above and explore.'}
                </Typography>
            </Box>
        );
    }

    return (
        <List sx={{ flex: 1, overflow: 'auto', px: 1.5, pb: 2, '& > :last-child': { mb: 0 } }}>
            {brainstorms.map((b) => (
                <BrainstormItem
                    key={b.id}
                    brainstorm={b}
                    isActive={activeBrainstorm?.id === b.id}
                    editingId={editingId}
                    editTitle={editTitle}
                    editingRef={editingRef}
                    onSelect={() => onSelect(b)}
                    onStartEdit={(e) => onStartEdit(e, b)}
                    onEditTitleChange={(e) => onEditTitleChange(e)}
                    onEditKeyDown={onEditKeyDown}
                    onSaveEdit={onSaveEdit}
                    onDelete={(e) => {
                        e.stopPropagation();
                        onDelete(b);
                    }}
                />
            ))}
        </List>
    );
}

export default BrainstormList;
