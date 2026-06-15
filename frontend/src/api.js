import axios from 'axios';

// The backend is exposed on localhost:8000 via Docker port mapping
// or when running locally. Use VITE_API_URL env var to override.
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export function buildBrainstormWebSocketUrl(brainstormId) {
    const apiUrl = new URL(API_BASE.startsWith('http') ? API_BASE : `${window.location.origin}${API_BASE}`);
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
export const updateBrainstormTitle = (id, title) => api.patch(`/brainstorms/${id}/title?title=${encodeURIComponent(title)}`);
export const updateBrainstormModel = (id, model) => api.patch(`/brainstorms/${id}/model`, { model });
export const getMessages = (id) => api.get(`/brainstorms/${id}/messages`);

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

                // Parse SSE frames: lines starting with "data: "
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    const payload = line.slice(6);
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

            // Process any remaining buffer
            if (buffer.startsWith('data: ')) {
                const payload = buffer.slice(6);
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

export default api;
