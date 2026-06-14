import { Component } from 'react';
import { Box, Typography, Button, alpha } from '@mui/material';
import { Error as ErrorIcon, Refresh as RefreshIcon } from '@mui/icons-material';

class ErrorBoundary extends Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('ErrorBoundary caught:', error, errorInfo);
    }

    handleRetry = () => {
        this.setState({ hasError: false, error: null });
    };

    render() {
        if (this.state.hasError) {
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
                        sx={(theme) => ({
                            width: 64,
                            height: 64,
                            borderRadius: 3,
                            background: `linear-gradient(135deg, ${alpha(theme.palette.error.main, 0.1)} 0%, ${alpha(theme.palette.error.main, 0.04)} 100%)`,
                            border: '1px solid',
                            borderColor: alpha(theme.palette.error.main, 0.1),
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                        })}
                    >
                        <ErrorIcon
                            sx={(theme) => ({ fontSize: 28, color: theme.palette.error.light })}
                        />
                    </Box>
                    <Box sx={{ textAlign: 'center', maxWidth: 280 }}>
                        <Typography
                            sx={(theme) => ({
                                fontWeight: 600,
                                color: alpha(theme.palette.text.primary, 0.7),
                                mb: 0.5,
                                fontSize: '0.95rem',
                            })}
                        >
                            {this.props.fallbackTitle || 'Something went wrong'}
                        </Typography>
                        <Typography
                            variant="body2"
                            sx={(theme) => ({
                                color: alpha(theme.palette.text.secondary, 0.5),
                                lineHeight: 1.6,
                                mb: 2,
                            })}
                        >
                            {this.props.fallbackMessage ||
                                'An unexpected error occurred. Please try refreshing.'}
                        </Typography>
                        <Button
                            variant="outlined"
                            startIcon={<RefreshIcon />}
                            onClick={this.handleRetry}
                            sx={{
                                borderRadius: 2,
                                textTransform: 'none',
                                fontWeight: 600,
                                fontSize: '0.85rem',
                            }}
                        >
                            Try again
                        </Button>
                    </Box>
                </Box>
            );
        }

        return this.props.children;
    }
}

export default ErrorBoundary;