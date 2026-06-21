import axios from 'axios';
import { streamSSE } from './sse';

// The backend is exposed on localhost:8000 via Docker port mapping
// or when running locally. Use VITE_API_URL env var to override.
// In production (behind nginx), use relative path /api/v1.
// In dev with Vite proxy, also use /api/v1 (proxied to localhost:8000).
// Direct dev (no proxy): set VITE_API_URL=http://localhost:8000/api/v1
const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export function buildBrainstormWebSocketUrl(brainstormId) {
    const base = API_BASE.startsWith('http')
        ? API_BASE
        : `${window.location.origin}${API_BASE}`;
    const apiUrl = new URL(base);
    const protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const basePath = apiUrl.pathname.replace(/\/$/, '');
    const token = localStorage.getItem('brainstorm-auth-token');
    const params = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${protocol}//${apiUrl.host}${basePath}/ws/${brainstormId}${params}`;
}

const api = axios.create({
    baseURL: API_BASE,
    headers: {
        'Content-Type': 'application/json',
    },
});

// ── Global 401 handler — clears session on auth failure ───
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('brainstorm-auth-token');
            localStorage.removeItem('brainstorm-auth-user');
            delete api.defaults.headers.common['Authorization'];
            window.location.reload();
        }
        return Promise.reject(error);
    },
);

// Brainstorms
export const listBrainstorms = () => api.get('/brainstorms/');
export const createBrainstorm = (data) => api.post('/brainstorms/', data);
export const getBrainstorm = (id) => api.get(`/brainstorms/${id}`);
export const deleteBrainstorm = (id) => api.delete(`/brainstorms/${id}`);
export const updateBrainstormTitle = (id, title) => api.patch(`/brainstorms/${id}/title`, { title });
export const updateBrainstormModel = (id, model) => api.patch(`/brainstorms/${id}/model`, { model });
export const getMessages = (id, limit = 50, beforeId = null) => {
  const params = { limit };
  if (beforeId) params.before_id = beforeId;
  return api.get(`/brainstorms/${id}/messages`, { params });
};

// Chat
/**
 * Stream a chat message via SSE and invoke callbacks for each event.
 *
 * @param {object} data - { brainstorm_id, message, model?, api_key?, base_url? }
 * @param {object} callbacks
 * @param {(token:string)=>void} callbacks.onToken - called per token
 * @param {({message_id:string})=>void} callbacks.onDone - called on completion
 * @param {(error:string)=>void} callbacks.onError - called on error
 * @returns {AbortController} - call .abort() to cancel the stream
 */
export function streamMessage(data, { onToken, onDone, onError }) {
    return streamSSE(`${API_BASE}/chat/stream`, data, {
        onEvent(event) {
            if (event.token) {
                onToken(event.token);
            } else if (event.done) {
                onDone(event);
            } else if (event.error) {
                onError(event.error);
            }
        },
        onError,
    });
}

// Map
export const getMap = (id) => api.get(`/map/${id}`);
export const refreshMap = (id) => api.post(`/map/${id}/refresh`);
export const updateTopic = (brainstormId, topicId, data) => api.patch(`/map/${brainstormId}/topics/${topicId}`, data);
export const deleteTopic = (brainstormId, topicId) => api.delete(`/map/${brainstormId}/topics/${topicId}`);
export const createTopic = (brainstormId, data) => api.post(`/map/${brainstormId}/topics`, data);
export const exploreTopic = (brainstormId, topicId) => api.post(`/map/${brainstormId}/topics/${topicId}/explore`);
export const createEdge = (brainstormId, data) => api.post(`/map/${brainstormId}/edges`, data);
export const deleteEdge = (brainstormId, edgeId) => api.delete(`/map/${brainstormId}/edges/${edgeId}`);

// Explore connection between two topics
export const exploreConnection = (brainstormId, data) => api.post(`/map/${brainstormId}/explore-connection`, data);

// Gap detection
export const getGaps = (brainstormId) => api.get(`/map/${brainstormId}/gaps`);

// Topic comments
export const getTopicComments = (brainstormId, topicId) => api.get(`/map/${brainstormId}/topics/${topicId}/comments`);
export const addTopicComment = (brainstormId, topicId, content) => api.post(`/map/${brainstormId}/topics/${topicId}/comments`, { content });

/**
 * Stream AI-generated content for a topic's outline sections.
 *
 * @param {string} brainstormId
 * @param {string} topicId
 * @param {object} callbacks
 * @param {(token:string)=>void} callbacks.onToken - called per token
 * @param {({topic_id:string,summary:string})=>void} callbacks.onDone - called on completion
 * @param {(error:string)=>void} callbacks.onError - called on error
 * @returns {AbortController}
 */
export function generateTopicContent(brainstormId, topicId, { onToken, onDone, onError }) {
    return streamSSE(`${API_BASE}/map/${brainstormId}/topics/${topicId}/generate`, null, {
        onEvent(event) {
            if (event.token) {
                onToken(event.token);
            } else if (event.done) {
                onDone(event);
            } else if (event.error) {
                onError(event.error);
            }
        },
        onError,
    });
}

// Provider settings
export const updateProviderSettings = (provider, data) => api.put(`/settings/${provider}`, data);

// Share
export const enableSharing = (id) => api.post(`/brainstorms/${id}/share`);
export const disableSharing = (id) => api.delete(`/brainstorms/${id}/share`);

// Export
export const exportMarkdown = (id) => api.get(`/brainstorms/${id}/export/markdown`, { responseType: 'blob' });
export const exportOPML = (id) => api.get(`/brainstorms/${id}/export/opml`, { responseType: 'blob' });
export const importBrainstorm = (id, data) => api.post(`/brainstorms/${id}/export/import`, data);

// Library
export const getLibrary = (id) => api.get(`/library/${id}`);
export const updateLibraryEntry = (id, content) => api.put(`/library/entry/${id}`, { content });
export const deleteLibraryEntry = (id) => api.delete(`/library/entry/${id}`);

// Search
export const searchAll = (q, limit = 30) => api.get('/search/', { params: { q, limit } });

// Research
export const researchTopic = (brainstormId, topic) => api.post(`/research/${brainstormId}`, { topic });

// URL import
export const importUrl = (brainstormId, url, topicId = null) => api.post(`/upload/${brainstormId}/url`, { url, topic_id: topicId });

// Flashcards
export const getFlashcards = (brainstormId) => api.get(`/map/${brainstormId}/flashcards`);
export const getDueFlashcards = (brainstormId) => api.get(`/map/${brainstormId}/flashcards/due`);
export const reviewFlashcard = (brainstormId, flashcardId, quality) => api.post(`/map/${brainstormId}/flashcards/${flashcardId}/review`, { quality });

/**
 * Stream AI-generated flashcards from the knowledge map via SSE.
 *
 * @param {string} brainstormId
 * @param {object} callbacks
 * @param {(token:string)=>void} callbacks.onToken - called per token
 * @param {({count:number})=>void} callbacks.onDone - called on completion
 * @param {(error:string)=>void} callbacks.onError - called on error
 * @returns {AbortController}
 */
export function generateFlashcards(brainstormId, { onToken, onDone, onError }) {
    return streamSSE(`${API_BASE}/map/${brainstormId}/flashcards/generate`, null, {
        onEvent(event) {
            if (event.token) {
                onToken(event.token);
            } else if (event.done) {
                if (event.error) {
                    onError(event.error);
                } else {
                    onDone(event);
                }
            } else if (event.error) {
                onError(event.error);
            }
        },
        onError,
    });
}

export default api;
