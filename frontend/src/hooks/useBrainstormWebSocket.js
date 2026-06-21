import { useEffect, useRef } from 'react';
import { buildBrainstormWebSocketUrl } from '../api';
import logger from '../utils/logger';

const CLASSIFICATION_TIMEOUT_MS = 30_000;
const CONNECTION_EXPLORE_TIMEOUT_MS = 60_000;

export function useBrainstormWebSocket(activeBrainstorm, dependencies) {
  const { loadMap, loadLibrary, loadList, setExploringTopic, setExploringEdge, setHasClassified } = dependencies;

  const wsRef = useRef(null);
  const classifiedTimerRef = useRef(null);

  useEffect(() => {
    if (!activeBrainstorm) {
      if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
      if (classifiedTimerRef.current) { clearTimeout(classifiedTimerRef.current); classifiedTimerRef.current = null; }
      return;
    }
    if (wsRef.current) wsRef.current.close();

    // Fallback: if classification doesn't trigger within timeout, stop showing loading state
    setHasClassified(false);
    classifiedTimerRef.current = setTimeout(() => {
      setHasClassified(true);
    }, CLASSIFICATION_TIMEOUT_MS);

    const socket = new WebSocket(buildBrainstormWebSocketUrl(activeBrainstorm.id));
    wsRef.current = socket;

    socket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === 'classification_complete' || msg.event === 'classification_error') {
          if (classifiedTimerRef.current) { clearTimeout(classifiedTimerRef.current); classifiedTimerRef.current = null; }
          loadMap(activeBrainstorm.id);
          loadLibrary(activeBrainstorm.id);
          loadList();
          setExploringTopic(null);
          setHasClassified(true);
        }
        if (msg.event === 'topic_generated') {
          loadMap(activeBrainstorm.id);
          loadLibrary(activeBrainstorm.id);
          setExploringEdge?.(null);
        }
        if (msg.event === 'topic_created' || msg.event === 'topic_updated'
            || msg.event === 'topic_deleted' || msg.event === 'edge_created'
            || msg.event === 'edge_deleted') {
          loadMap(activeBrainstorm.id);
        }
        if (msg.event === 'CONNECTED') {
          logger.debug('WebSocket connected:', msg.brainstorm_id);
        }
      } catch (err) {
        logger.debug('WebSocket parse error:', err.message);
      }
    };

    socket.onclose = (e) => {
      logger.debug('WebSocket closed. code:', e.code, 'reason:', e.reason);
      if (wsRef.current === socket) wsRef.current = null;
    };

    socket.onerror = (err) => {
      logger.debug('WebSocket error:', err);
    };

    socket.onopen = () => {
      logger.debug('WebSocket connected for brainstorm:', activeBrainstorm.id);
    };

    return () => {
      socket.close();
      if (wsRef.current === socket) wsRef.current = null;
      if (classifiedTimerRef.current) { clearTimeout(classifiedTimerRef.current); classifiedTimerRef.current = null; }
    };
  }, [activeBrainstorm, loadMap, loadLibrary, loadList, setExploringTopic, setHasClassified]);
}
