import {
  getMap,
  refreshMap,
  updateTopic,
  deleteTopic,
  createTopic,
  createEdge,
  deleteEdge,
  exploreTopic,
  generateTopicContent,
  exploreConnection,
} from '../api';
import logger from '../utils/logger';

export async function fetchMap(brainstormId) {
  try {
    const res = await getMap(brainstormId);
    return res.data;
  } catch (err) {
    logger.error('Failed to load map:', err);
  }
}

export async function triggerMapRefresh(brainstormId) {
  try {
    const res = await refreshMap(brainstormId);
    return res.data;
  } catch (err) {
    logger.error('Failed to refresh map:', err);
  }
}

export async function patchTopic(brainstormId, topicId, data) {
  await updateTopic(brainstormId, topicId, data);
}

export async function createBlankTopic(brainstormId, name, outline = null) {
  try {
    const res = await createTopic(brainstormId, {
      name,
      auto_generate: false,
      outline: outline || undefined,
    });
    return res.data;
  } catch (err) {
    logger.error('Failed to create blank topic:', err);
    throw err;
  }
}

export async function streamTopicContent(brainstormId, topicId, callbacks) {
  return generateTopicContent(brainstormId, topicId, callbacks);
}

export async function createConnectionTopic(brainstormId, sourceTopicId, targetTopicId, positionX, positionY) {
  try {
    const res = await exploreConnection(brainstormId, {
      source_topic_id: sourceTopicId,
      target_topic_id: targetTopicId,
      position_x: positionX,
      position_y: positionY,
    });
    return res.data;
  } catch (err) {
    logger.error('Failed to create connection topic:', err);
    throw err;
  }
}

export async function removeTopic(brainstormId, topicId) {
  await deleteTopic(brainstormId, topicId);
}

export async function deepenTopic(brainstormId, topicId) {
  const res = await exploreTopic(brainstormId, topicId);
  return res.data;
}

export async function addEdge(brainstormId, sourceId, targetId) {
  try {
    await createEdge(brainstormId, {
      source_topic_id: sourceId,
      target_topic_id: targetId,
      relationship: 'related',
      weight: 0.5,
    });
  } catch (err) {
    if (err?.response?.status !== 409) {
      throw err;
    }
  }
}

export async function removeEdge(brainstormId, edgeId) {
  await deleteEdge(brainstormId, edgeId);
}
