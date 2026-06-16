import {
  listBrainstorms,
  createBrainstorm,
  getBrainstorm,
  deleteBrainstorm,
  updateBrainstormTitle,
  updateBrainstormModel,
} from '../api';
import logger from '../utils/logger';

export async function fetchBrainstorms() {
  try {
    const res = await listBrainstorms();
    return res.data;
  } catch (err) {
    logger.error('Failed to load brainstorms:', err);
    return [];
  }
}

export async function fetchBrainstorm(id) {
  try {
    const res = await getBrainstorm(id);
    return res.data;
  } catch (err) {
    logger.error('Failed to load brainstorm:', err);
    return null;
  }
}

export async function createNewBrainstorm(title) {
  const res = await createBrainstorm({ title });
  return res.data;
}

export async function removeBrainstorm(id) {
  await deleteBrainstorm(id);
}

export async function renameBrainstorm(id, title) {
  const res = await updateBrainstormTitle(id, title);
  return res.data;
}

export async function changeBrainstormModel(id, model) {
  await updateBrainstormModel(id, model);
  return fetchBrainstorm(id);
}
