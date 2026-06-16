/**
 * Development-only logger. Stripped in production builds.
 * Use instead of raw console.* for debug messages.
 */

const isProduction = import.meta.env.PROD;

const logger = {
  debug: (...args) => {
    if (!isProduction) console.log('[DEBUG]', ...args);
  },
  info: (...args) => {
    if (!isProduction) console.info('[INFO]', ...args);
  },
  warn: (...args) => {
    if (!isProduction) console.warn('[WARN]', ...args);
  },
  error: (...args) => {
    // Always log errors, even in production
    console.error('[ERROR]', ...args);
  },
};

export default logger;
