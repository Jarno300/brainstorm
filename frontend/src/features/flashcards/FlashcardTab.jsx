import { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Typography,
  Button,
  CircularProgress,
  Chip,
  alpha,
  Paper,
  Card,
  CardContent,
  CardActions,
  Fade,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  AutoAwesome as SparkleIcon,
  School as SchoolIcon,
  Refresh as RefreshIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import useFlashcardStore from '../../stores/flashcardStore';
import FlashcardQuiz from './FlashcardQuiz';

function FlashcardTab({ brainstormId }) {
  const {
    flashcards,
    total,
    dueCount,
    isGenerating,
    generationText,
    generationError,
    generateCards,
    abortGeneration,
    loadFlashcards,
    clear,
  } = useFlashcardStore();

  const [quizActive, setQuizActive] = useState(false);

  useEffect(() => {
    if (brainstormId) {
      loadFlashcards(brainstormId);
    }
    return () => clear();
  }, [brainstormId, loadFlashcards, clear]);

  const handleGenerate = useCallback(() => {
    if (!brainstormId) return;
    generateCards(brainstormId, {
      onDone: (event) => {
        if (event.error) {
          // handled by onError in store
        }
      },
    });
  }, [brainstormId, generateCards]);

  const handleStartQuiz = useCallback(() => {
    setQuizActive(true);
  }, []);

  const handleQuizDone = useCallback(() => {
    setQuizActive(false);
    if (brainstormId) {
      loadFlashcards(brainstormId);
    }
  }, [brainstormId, loadFlashcards]);

  // ── Quiz view ────────────────────────────────────────────
  if (quizActive) {
    return (
      <FlashcardQuiz
        brainstormId={brainstormId}
        onDone={handleQuizDone}
      />
    );
  }

  // ── Loading state ────────────────────────────────────────
  if (!brainstormId) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <Typography sx={(t) => ({ color: alpha(t.palette.text.secondary, 0.5), fontSize: '0.9rem' })}>
          Select a brainstorm to view flashcards.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ── Header / toolbar ──────────────────────────────── */}
      <Box
        sx={(theme) => ({
          px: 2.5,
          py: 2,
          borderBottom: '1px solid',
          borderColor: alpha(theme.palette.divider, 0.08),
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          flexShrink: 0,
        })}
      >
        <SchoolIcon sx={(t) => ({ fontSize: 20, color: t.palette.primary.light })} />
        <Typography
          sx={{
            fontWeight: 700,
            fontSize: '1rem',
            flex: 1,
          }}
        >
          Flashcards
        </Typography>

        {total > 0 && (
          <Chip
            label={`${total} cards`}
            size="small"
            sx={(t) => ({
              height: 22,
              fontSize: '0.7rem',
              fontWeight: 600,
              bgcolor: alpha(t.palette.primary.main, 0.1),
              color: t.palette.primary.light,
            })}
          />
        )}

        {dueCount > 0 && (
          <Chip
            label={`${dueCount} due`}
            size="small"
            color="warning"
            sx={(t) => ({
              height: 22,
              fontSize: '0.7rem',
              fontWeight: 700,
            })}
          />
        )}

        {!isGenerating && (
          <Tooltip title="Generate flashcards from your knowledge map" arrow>
            <Button
              variant="outlined"
              size="small"
              startIcon={<SparkleIcon sx={{ fontSize: 15 }} />}
              onClick={handleGenerate}
              sx={(t) => ({
                borderRadius: 1.5,
                textTransform: 'none',
                fontWeight: 600,
                fontSize: '0.78rem',
                py: 0.5,
                borderColor: alpha(t.palette.primary.main, 0.25),
                color: t.palette.primary.light,
                '&:hover': {
                  borderColor: alpha(t.palette.primary.main, 0.5),
                  bgcolor: alpha(t.palette.primary.main, 0.06),
                },
              })}
            >
              Generate
            </Button>
          </Tooltip>
        )}

        {dueCount > 0 && !isGenerating && (
          <Button
            variant="contained"
            size="small"
            onClick={handleStartQuiz}
            sx={(t) => ({
              borderRadius: 1.5,
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.78rem',
              py: 0.5,
              background: t.palette.gradients.primary,
            })}
          >
            Study ({dueCount})
          </Button>
        )}
      </Box>

      {/* ── Content area ──────────────────────────────────── */}
      <Box sx={{ flex: 1, overflow: 'auto', p: 2.5 }}>
        {/* Generating state */}
        {isGenerating && (
          <Fade in>
            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, py: 6 }}>
              <CircularProgress size={28} sx={(t) => ({ color: t.palette.primary.light })} />
              <Typography sx={(t) => ({ color: alpha(t.palette.text.secondary, 0.6), fontSize: '0.85rem' })}>
                Generating flashcards from your knowledge map...
              </Typography>
              <Button
                size="small"
                startIcon={<CancelIcon sx={{ fontSize: 14 }} />}
                onClick={abortGeneration}
                sx={(t) => ({
                  textTransform: 'none',
                  fontSize: '0.75rem',
                  color: alpha(t.palette.text.secondary, 0.5),
                })}
              >
                Cancel
              </Button>
              {generationText && (
                <Paper
                  sx={(t) => ({
                    mt: 2,
                    p: 2,
                    maxWidth: 600,
                    width: '100%',
                    maxHeight: 200,
                    overflow: 'auto',
                    bgcolor: alpha(t.palette.background.paper, 0.5),
                    borderRadius: 2,
                    border: `1px solid ${alpha(t.palette.divider, 0.1)}`,
                    fontFamily: 'monospace',
                    fontSize: '0.72rem',
                    whiteSpace: 'pre-wrap',
                    color: alpha(t.palette.text.secondary, 0.5),
                    lineHeight: 1.5,
                  })}
                >
                  {generationText}
                </Paper>
              )}
            </Box>
          </Fade>
        )}

        {/* Empty state */}
        {!isGenerating && total === 0 && (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', py: 8, gap: 2 }}>
            <SchoolIcon sx={(t) => ({ fontSize: 48, color: alpha(t.palette.text.secondary, 0.15) })} />
            {generationError ? (
              <>
                <Typography sx={(t) => ({ color: t.palette.error.light, fontSize: '0.85rem', textAlign: 'center', maxWidth: 360, fontWeight: 600 })}>
                  Generation failed
                </Typography>
                <Paper sx={(t) => ({ p: 2, maxWidth: 500, width: '100%', bgcolor: alpha(t.palette.error.main, 0.06), borderRadius: 2, border: `1px solid ${alpha(t.palette.error.main, 0.15)}`, fontFamily: 'monospace', fontSize: '0.72rem', color: alpha(t.palette.text.secondary, 0.7), whiteSpace: 'pre-wrap', lineHeight: 1.5 })}>
                  {generationError}
                </Paper>
                <Button size="small" onClick={handleGenerate} sx={{ textTransform: 'none', fontSize: '0.78rem' }}>Try again</Button>
              </>
            ) : (
              <Typography sx={(t) => ({ color: alpha(t.palette.text.secondary, 0.4), fontSize: '0.9rem', textAlign: 'center', maxWidth: 360 })}>
                No flashcards yet. Click <strong>Generate</strong> to automatically create flashcards from your knowledge map's topic cards and connections.
              </Typography>
            )}
          </Box>
        )}

        {/* Card list */}
        {!isGenerating && total > 0 && (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {flashcards.map((card) => {
              const isDue = new Date(card.next_review) <= new Date();
              return (
                <Card
                  key={card.id}
                  sx={(t) => ({
                    bgcolor: alpha(t.palette.background.paper, 0.5),
                    border: '1px solid',
                    borderColor: isDue
                      ? alpha(t.palette.warning.main, 0.3)
                      : alpha(t.palette.divider, 0.08),
                    borderRadius: 2,
                    transition: 'all 0.15s ease',
                    '&:hover': {
                      borderColor: alpha(t.palette.primary.main, 0.15),
                    },
                  })}
                >
                  <CardContent sx={{ pb: 1 }}>
                    <Typography
                      sx={{
                        fontWeight: 600,
                        fontSize: '0.85rem',
                        mb: 1,
                        lineHeight: 1.5,
                      }}
                    >
                      {card.question}
                    </Typography>
                    <Typography
                      sx={(t) => ({
                        color: alpha(t.palette.text.secondary, 0.7),
                        fontSize: '0.8rem',
                        lineHeight: 1.6,
                      })}
                    >
                      {card.answer}
                    </Typography>
                  </CardContent>
                  <CardActions sx={{ px: 2, pb: 1.5, pt: 0, gap: 0.5 }}>
                    <Chip
                      label={`EF: ${card.ease_factor.toFixed(1)}`}
                      size="small"
                      sx={(t) => ({
                        height: 20,
                        fontSize: '0.6rem',
                        bgcolor: alpha(t.palette.text.secondary, 0.06),
                        color: alpha(t.palette.text.secondary, 0.5),
                      })}
                    />
                    <Chip
                      label={`Interval: ${card.interval}d`}
                      size="small"
                      sx={(t) => ({
                        height: 20,
                        fontSize: '0.6rem',
                        bgcolor: alpha(t.palette.text.secondary, 0.06),
                        color: alpha(t.palette.text.secondary, 0.5),
                      })}
                    />
                    <Chip
                      label={`Reps: ${card.repetitions}`}
                      size="small"
                      sx={(t) => ({
                        height: 20,
                        fontSize: '0.6rem',
                        bgcolor: alpha(t.palette.text.secondary, 0.06),
                        color: alpha(t.palette.text.secondary, 0.5),
                      })}
                    />
                    <Chip
                      label={isDue ? 'Due now' : `Next: ${new Date(card.next_review).toLocaleDateString()}`}
                      size="small"
                      color={isDue ? 'warning' : 'default'}
                      sx={(t) => ({
                        height: 20,
                        fontSize: '0.6rem',
                        fontWeight: 600,
                        ml: 'auto',
                      })}
                    />
                  </CardActions>
                </Card>
              );
            })}
          </Box>
        )}
      </Box>
    </Box>
  );
}

export default FlashcardTab;
