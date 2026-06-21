/**
 * Shared SSE (Server-Sent Events) streaming helper.
 *
 * Handles the low-level ReadableStream → SSE frame → JSON parsing for
 * all streaming endpoints (chat, topic content generation, etc.).
 *
 * @param {string} url - Full URL to POST to
 * @param {object} body - JSON body (null for GET-style streams)
 * @param {object} callbacks
 * @param {(event:object)=>void} callbacks.onEvent - called per parsed SSE event
 * @param {(error:string)=>void} callbacks.onError - called on error
 * @returns {AbortController}
 */
export function streamSSE(url, body, { onEvent, onError }) {
  const controller = new AbortController();
  const token = localStorage.getItem('brainstorm-auth-token');
  const headers = {};
  if (body != null) headers['Content-Type'] = 'application/json';
  if (token) headers['Authorization'] = `Bearer ${token}`;

  const opts = {
    method: 'POST',
    headers,
    signal: controller.signal,
  };
  if (body != null) opts.body = JSON.stringify(body);

  fetch(url, opts)
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

        // Parse SSE frames: events delimited by double-newline
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
            onEvent(event);
          } catch {
            // skip parse errors on partial / malformed frames
          }
        }
      }

      // Process remaining partial buffer
      if (buffer.trim()) {
        const dataLines = [];
        for (const line of buffer.split('\n')) {
          if (line.startsWith('data: ')) dataLines.push(line.slice(6));
        }
        const payload = dataLines.join('\n');
        if (payload.trim()) {
          try {
            const event = JSON.parse(payload);
            onEvent(event);
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
