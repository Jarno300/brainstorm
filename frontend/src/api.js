import axios from 'axios';

// The backend is exposed on localhost:8000 via Docker port mapping
// or when running locally. Use VITE_API_URL env var to override.
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export function buildBrainstormWebSocketUrl(brainstormId) {
    const apiUrl = new URL(API_BASE.startsWith('http') ? API_BASE : `${window.location.origin}${API_BASE}`);
    const protocol = apiUrl.protocol === 'https:' ? 'wss:' : 'ws:';
    const basePath = apiUrl.pathname.replace(/\/$/, '');
    return `${protocol}//${apiUrl.host}${basePath}/ws/${brainstormId}`;
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

// Map
export const getMap = (id) => api.get(`/map/${id}`);
export const refreshMap = (id) => api.post(`/map/${id}/refresh`);

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

export default api;
