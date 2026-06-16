import { getMessages } from '../api';
import logger from '../utils/logger';

export async function fetchMessages(brainstormId) {
  try {
    const res = await getMessages(brainstormId);
    return res.data?.messages || res.data || [];
  } catch (err) {
    logger.error('Failed to load messages:', err);
    return [];
  }
}
