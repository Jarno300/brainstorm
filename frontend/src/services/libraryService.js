import {
  getLibrary,
  updateLibraryEntry,
  deleteLibraryEntry,
} from '../api';
import logger from '../utils/logger';

export async function fetchLibrary(brainstormId) {
  try {
    const res = await getLibrary(brainstormId);
    return res.data;
  } catch (err) {
    logger.error('Failed to load library:', err);
  }
}

export async function patchLibraryEntry(entryId, content) {
  await updateLibraryEntry(entryId, content);
}

export async function removeLibraryEntry(entryId) {
  await deleteLibraryEntry(entryId);
}
