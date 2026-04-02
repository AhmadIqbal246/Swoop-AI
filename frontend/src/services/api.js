import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1/chatbot';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const scraperService = {
  processUrl: async (url) => {
    const response = await api.post('/process-url', { url });
    return response.data;
  },
  
  getTaskStatus: async (taskId) => {
    const response = await api.get(`/task-status/${taskId}`);
    return response.data;
  }
};

export const chatService = {
  sendMessage: async (query, contextUrl = null, sessionId = 'default') => {
    const response = await api.post('/chat', { 
      query, 
      session_id: sessionId,
      context_url: contextUrl 
    });
    return response.data;
  }
};

export default api;
