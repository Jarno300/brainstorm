import axios from 'axios';

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
export const sendMessage = (data) => api.post('/chat/', data);

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
    const controller = new AbortController();
    const url = `${API_BASE}/chat/stream`;
    const token = localStorage.getItem('brainstorm-auth-token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(data),
        signal: controller.signal,
    })
        .then(async (response) => {
            if (!response.ok) {
                const text = await response.text().catch(() => 'Unknown error');
                onError(`Server error ${response.status}: ${text}`);
                return;
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                // Parse SSE frames: events are delimited by double-newline (\n\n).
                // Each event may have multiple "data:" lines concatenated.
                let idx;
                while ((idx = buffer.indexOf('\n\n')) !== -1) {
                    const frame = buffer.slice(0, idx);
                    buffer = buffer.slice(idx + 2);

                    // Collect all "data:" lines from this event
                    const dataLines = [];
                    for (const line of frame.split('\n')) {
                        if (line.startsWith('data: ')) {
                            dataLines.push(line.slice(6));
                        }
                    }
                    const payload = dataLines.join('\n');
                    if (!payload.trim()) continue;

                    try {
                        const event = JSON.parse(payload);
                        if (event.token) {
                            onToken(event.token);
                        } else if (event.done) {
                            onDone(event);
                        } else if (event.error) {
                            onError(event.error);
                        }
                    } catch {
                        // skip parse errors on partial frames
                    }
                }
            }

            // Process any remaining buffer (incomplete final event)
            if (buffer.trim()) {
                const dataLines = [];
                for (const line of buffer.split('\n')) {
                    if (line.startsWith('data: ')) {
                        dataLines.push(line.slice(6));
                    }
                }
                const payload = dataLines.join('\n');
                if (payload.trim()) {
                    try {
                        const event = JSON.parse(payload);
                        if (event.done) onDone(event);
                        else if (event.error) onError(event.error);
                    } catch { /* ignore */ }
                }
            }
        })
        .catch((err) => {
            if (err.name !== 'AbortError') {
                onError(err.message || 'Network error');
            }
        });

    return controller;
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
    const controller = new AbortController();
    const url = `${API_BASE}/map/${brainstormId}/topics/${topicId}/generate`;
    const token = localStorage.getItem('brainstorm-auth-token');
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    fetch(url, {
        method: 'POST',
        headers,
        signal: controller.signal,
    })
        .then(async (response) => {
            if (!response.ok) {
                const text = await response.text().catch(() => 'Unknown error');
                onError(`Server error ${response.status}: ${text}`);
                return;
            }
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                let idx;
                while ((idx = buffer.indexOf('\n\n')) !== -1) {
                    const frame = buffer.slice(0, idx);
                    buffer = buffer.slice(idx + 2);

                    const dataLines = [];
                    for (const line of frame.split('\n')) {
                        if (line.startsWith('data: ')) {
                            dataLines.push(line.slice(6));
                        }
                    }
                    const payload = dataLines.join('\n');
                    if (!payload.trim()) continue;

                    try {
                        const event = JSON.parse(payload);
                        if (event.token) {
                            onToken(event.token);
                        } else if (event.done) {
                            onDone(event);
                        } else if (event.error) {
                            onError(event.error);
                        }
                    } catch {
                        // skip parse errors
                    }
                }
            }

            if (buffer.trim()) {
                const dataLines = [];
                for (const line of buffer.split('\n')) {
                    if (line.startsWith('data: ')) {
                        dataLines.push(line.slice(6));
                    }
                }
                const payload = dataLines.join('\n');
                if (payload.trim()) {
                    try {
                        const event = JSON.parse(payload);
                        if (event.done) onDone(event);
                        else if (event.error) onError(event.error);
                    } catch { /* ignore */ }
                }
            }
        })
        .catch((err) => {
            if (err.name !== 'AbortError') {
                onError(err.message || 'Network error');
            }
        });

    return controller;
}

// Provider settings
export const getProviderSettings = (provider) => api.get(`/settings/${provider}`);
export const updateProviderSettings = (provider, data) => api.put(`/settings/${provider}`, data);

// Share
export const enableSharing = (id) => api.post(`/brainstorms/${id}/share`);
export const disableSharing = (id) => api.delete(`/brainstorms/${id}/share`);

// Export
export const exportMarkdown = (id) => api.get(`/brainstorms/${id}/export/markdown`, { responseType: 'blob' });

// Library
export const getLibrary = (id) => api.get(`/library/${id}`);
export const getLibraryEntry = (id) => api.get(`/library/entry/${id}`);
export const updateLibraryEntry = (id, content) => api.put(`/library/entry/${id}`, { content });
export const deleteLibraryEntry = (id) => api.delete(`/library/entry/${id}`);

// Search
export const searchAll = (q, limit = 30) => api.get('/search/', { params: { q, limit } });

// Research
export const researchTopic = (brainstormId, topic) => api.post(`/research/${brainstormId}`, { topic });

export default api;
