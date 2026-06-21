import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Typography,
  Button,
  ButtonGroup,
  CircularProgress,
  alpha,
  Paper,
  Fade,
  LinearProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  ThumbUp as EasyIcon,
  ThumbDown as HardIcon,
} from '@mui/icons-material';
import useFlashcardStore from '../../stores/flashcardStore';

const QUALITY_LABELS = {
  0: 'Blackout',
  1: 'Wrong, remembered',
  2: 'Wrong, easy recall',
  3: 'Hard',
  4: 'Good',
  5: 'Easy',
};

const QUALITY_COLORS = {
  0: 'error',
  1: 'error',
  2: 'warning',
  3: 'warning',
  4: 'success',
  5: 'success',
};

function FlashcardQuiz({ brainstormId, onDone }) {
  const { dueFlashcards, loadDueFlashcards, reviewCard } = useFlashcardStore();

  const [loading, setLoading] = useState(true);
  const [cards, setCards] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [reviewedCount, setReviewedCount] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const cardRef = useRef(null);

  useEffect(() => {
    if (!brainstormId) return;
    (async () => {
      setLoading(true);
      await loadDueFlashcards(brainstormId);
      const due = useFlashcardStore.getState().dueFlashcards;
      setCards(due);
      setCurrentIndex(0);
      setShowAnswer(false);
      setReviewedCount(0);
      setDone(false);
      setLoading(false);
    })();
  }, [brainstormId, loadDueFlashcards]);

  const currentCard = cards[currentIndex];

  const handleReveal = useCallback(() => {
    setShowAnswer(true);
  }, []);

  const handleRate = useCallback(
    async (quality) => {
      if (!currentCard || submitting) return;

      setSubmitting(true);
      try {
        await reviewCard(brainstormId, currentCard.id, quality);
        setReviewedCount((c) => c + 1);
      } catch {
        // Continue even on error
      }
      setSubmitting(false);

      // Move to next card
      if (currentIndex + 1 < cards.length) {
        setCurrentIndex((i) => i + 1);
        setShowAnswer(false);
      } else {
        setDone(true);
      }
    },
    [brainstormId, currentCard, currentIndex, cards.length, reviewCard, submitting]
  );

  // Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e) => {
      if (done) return;
      if (submitting) return;

      if (!showAnswer) {
        if (e.key === ' ' || e.key === 'Enter') {
          e.preventDefault();
          handleReveal();
        }
      } else {
        const keyMap = {
          '1': 0,
          '2': 1,
          '3': 2,
          '4': 3,
          '5': 4,
          '6': 5,
        };
        const quality = keyMap[e.key];
        if (quality !== undefined) {
          e.preventDefault();
          handleRate(quality);
        }
      }
    };

    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [showAnswer, done, submitting, handleReveal, handleRate]);

  // ── Loading ──────────────────────────────────────────────
  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <CircularProgress size={28} sx={(t) => ({ color: t.palette.primary.light })} />
      </Box>
    );
  }

  // ── Done state ───────────────────────────────────────────
  if (done || cards.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          gap: 2,
          px: 4,
        }}
      >
        <Box
          sx={(t) => ({
            width: 56,
            height: 56,
            borderRadius: '50%',
            bgcolor: alpha(t.palette.success.main, 0.12),
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            mb: 1,
          })}
        >
          <CheckIcon sx={(t) => ({ fontSize: 28, color: t.palette.success.light })} />
        </Box>
        <Typography sx={{ fontWeight: 700, fontSize: '1.1rem' }}>
          {cards.length === 0 ? 'No cards due!' : 'Study session complete!'}
        </Typography>
        <Typography sx={(t) => ({ color: alpha(t.palette.text.secondary, 0.6), fontSize: '0.85rem', textAlign: 'center' })}>
          {reviewedCount > 0
            ? `You reviewed ${reviewedCount} card${reviewedCount !== 1 ? 's' : ''}. Come back when more cards are due.`
            : 'All caught up! New cards will appear as they become due for review.'}
        </Typography>
        <Button
          variant="outlined"
          size="small"
          onClick={onDone}
          startIcon={<BackIcon sx={{ fontSize: 16 }} />}
          sx={(t) => ({
            mt: 1,
            borderRadius: 1.5,
            textTransform: 'none',
            fontWeight: 600,
            fontSize: '0.8rem',
            borderColor: alpha(t.palette.divider, 0.2),
          })}
        >
          Back to list
        </Button>
      </Box>
    );
  }

  // ── Quiz view ────────────────────────────────────────────
  const progress = cards.length > 0 ? ((currentIndex) / cards.length) * 100 : 0;

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* ── Top bar ──────────────────────────────────────── */}
      <Box
        sx={(t) => ({
          px: 2.5,
          py: 1.5,
          borderBottom: '1px solid',
          borderColor: alpha(t.palette.divider, 0.08),
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          flexShrink: 0,
        })}
      >
        <IconButton
          size="small"
          onClick={onDone}
          sx={(t) => ({
            color: alpha(t.palette.text.secondary, 0.5),
            '&:hover': { color: t.palette.text.primary },
          })}
        >
          <BackIcon sx={{ fontSize: 18 }} />
        </IconButton>
        <Typography sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
          {currentIndex + 1} of {cards.length}
        </Typography>
        <Box sx={{ flex: 1 }} />
        <Typography sx={(t) => ({ fontSize: '0.75rem', color: alpha(t.palette.text.secondary, 0.5) })}>
          Reviewed: {reviewedCount}
        </Typography>
      </Box>

      <LinearProgress
        variant="determinate"
        value={progress}
        sx={(t) => ({
          height: 3,
          bgcolor: alpha(t.palette.primary.main, 0.06),
          '& .MuiLinearProgress-bar': {
            background: t.palette.gradients.primary,
          },
        })}
      />

      {/* ── Card area ────────────────────────────────────── */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          p: 3,
          gap: 2,
          overflow: 'auto',
        }}
      >
        <Fade in={!showAnswer} timeout={300} key={`q-${currentIndex}`}>
          <Paper
            ref={cardRef}
            sx={(t) => ({
              width: '100%',
              maxWidth: 560,
              p: 4,
              borderRadius: 3,
              bgcolor: alpha(t.palette.background.paper, 0.6),
              border: '1px solid',
              borderColor: alpha(t.palette.divider, 0.1),
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              '&:hover': {
                borderColor: alpha(t.palette.primary.main, 0.2),
                boxShadow: `0 4px 24px ${alpha(t.palette.primary.main, 0.08)}`,
              },
            })}
            onClick={handleReveal}
            elevation={0}
          >
            <Typography
              sx={(t) => ({
                fontSize: '0.65rem',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.1em',
                color: alpha(t.palette.text.secondary, 0.4),
                mb: 2,
              })}
            >
              Question
            </Typography>
            <Typography
              sx={{
                fontWeight: 600,
                fontSize: '1.05rem',
                lineHeight: 1.7,
              }}
            >
              {currentCard?.question}
            </Typography>
            <Typography
              sx={(t) => ({
                mt: 3,
                fontSize: '0.75rem',
                color: alpha(t.palette.text.secondary, 0.4),
                textAlign: 'center',
              })}
            >
              Click or press Space to reveal answer
            </Typography>
          </Paper>
        </Fade>

        {showAnswer && (
          <Fade in timeout={300}>
            <Box sx={{ width: '100%', maxWidth: 560, display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Paper
                sx={(t) => ({
                  p: 4,
                  borderRadius: 3,
                  bgcolor: alpha(t.palette.success.main, 0.04),
                  border: '1px solid',
                  borderColor: alpha(t.palette.success.main, 0.15),
                })}
                elevation={0}
              >
                <Typography
                  sx={(t) => ({
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em',
                    color: alpha(t.palette.success.light, 0.5),
                    mb: 2,
                  })}
                >
                  Answer
                </Typography>
                <Typography
                  sx={{
                    fontWeight: 500,
                    fontSize: '0.95rem',
                    lineHeight: 1.7,
                  }}
                >
                  {currentCard?.answer}
                </Typography>
              </Paper>

              {/* ── Rating buttons ──────────────────────── */}
              <Typography
                sx={(t) => ({
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  color: alpha(t.palette.text.secondary, 0.45),
                  textAlign: 'center',
                  mt: 1,
                })}
              >
                How well did you know this?
              </Typography>

              <Box sx={{ display: 'flex', gap: 1, justifyContent: 'center', flexWrap: 'wrap' }}>
                {[
                  { quality: 0, icon: <CloseIcon />, label: 'Blackout', short: '1' },
                  { quality: 1, icon: <HardIcon />, label: 'Wrong', short: '2' },
                  { quality: 2, icon: <HardIcon />, label: 'Recall', short: '3' },
                  { quality: 3, icon: <CheckIcon />, label: 'Hard', short: '4' },
                  { quality: 4, icon: <CheckIcon />, label: 'Good', short: '5' },
                  { quality: 5, icon: <EasyIcon />, label: 'Easy', short: '6' },
                ].map(({ quality, icon, label, short }) => (
                  <Tooltip key={quality} title={`${label} (press ${short})`} arrow>
                    <Button
                      variant="outlined"
                      size="small"
                      disabled={submitting}
                      onClick={() => handleRate(quality)}
                      sx={(t) => {
                        const colorMap = {
                          0: t.palette.error,
                          1: t.palette.error,
                          2: t.palette.warning,
                          3: t.palette.warning,
                          4: t.palette.success,
                          5: t.palette.success,
                        };
                        const c = colorMap[quality];
                        return {
                          flex: '1 1 auto',
                          minWidth: 60,
                          maxWidth: 90,
                          borderRadius: 2,
                          textTransform: 'none',
                          fontWeight: 500,
                          fontSize: '0.7rem',
                          py: 0.75,
                          px: 1,
                          borderColor: alpha(c.main, 0.2),
                          color: alpha(c.light, 0.7),
                          display: 'flex',
                          flexDirection: 'column',
                          gap: 0.25,
                          '&:hover': {
                            borderColor: alpha(c.main, 0.45),
                            bgcolor: alpha(c.main, 0.06),
                            color: c.light,
                          },
                          '& .MuiButton-startIcon': {
                            mr: 0,
                            '& svg': { fontSize: 14 },
                          },
                        };
                      }}
                    >
                      {label}
                    </Button>
                  </Tooltip>
                ))}
              </Box>

              <Typography
                sx={(t) => ({
                  fontSize: '0.65rem',
                  color: alpha(t.palette.text.secondary, 0.3),
                  textAlign: 'center',
                })}
              >
                Keyboard: press 1–6 to rate
              </Typography>
            </Box>
          </Fade>
        )}
      </Box>
    </Box>
  );
}

export default FlashcardQuiz;
