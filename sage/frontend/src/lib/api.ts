import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for auth token
api.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized - redirect to login
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// API functions
export const authApi = {
  googleLogin: () => api.get('/auth/google'),
  me: () => api.get('/auth/me'),
  logout: () => api.post('/auth/logout'),
}

export const emailsApi = {
  list: (params?: {
    page?: number
    page_size?: number
    category?: string
    priority?: string
    unread_only?: boolean
    search?: string
  }) => api.get('/emails', { params }),
  get: (id: number) => api.get(`/emails/${id}`),
  analyze: (id: number) => api.post(`/emails/${id}/analyze`),
  draftReply: (id: number, data: { tone?: string; key_points?: string[]; context?: string }) =>
    api.post(`/emails/${id}/draft-reply`, data),
  sync: () => api.post('/emails/sync'),
  getThread: (threadId: string) => api.get(`/emails/thread/${threadId}`),
}

export const followupsApi = {
  list: (params?: {
    status?: string
    priority?: string
    contact_email?: string
    overdue_only?: boolean
  }) => api.get('/followups', { params }),
  get: (id: number) => api.get(`/followups/${id}`),
  create: (data: {
    gmail_id: string
    thread_id: string
    subject: string
    contact_email: string
    contact_name?: string
    priority?: string
    due_date: string
    notes?: string
    escalation_email?: string
  }) => api.post('/followups', data),
  update: (id: number, data: {
    status?: string
    priority?: string
    due_date?: string
    notes?: string
  }) => api.patch(`/followups/${id}`, data),
  complete: (id: number, reason?: string) =>
    api.post(`/followups/${id}/complete`, null, { params: { reason } }),
  cancel: (id: number, reason?: string) =>
    api.post(`/followups/${id}/cancel`, null, { params: { reason } }),
  delete: (id: number) => api.delete(`/followups/${id}`),
  overdue: () => api.get('/followups/overdue'),
  dueToday: () => api.get('/followups/due-today'),
  draft: (id: number) => api.post(`/followups/${id}/draft`),
}

export const calendarApi = {
  events: (params?: { start_date?: string; end_date?: string; max_results?: number }) =>
    api.get('/calendar/events', { params }),
  today: () => api.get('/calendar/today'),
  next: () => api.get('/calendar/next'),
  eventContext: (eventId: string) => api.get(`/calendar/event/${eventId}/context`),
}

export const briefingsApi = {
  morning: () => api.post('/briefings/morning'),
  weekly: () => api.post('/briefings/weekly'),
  sendMorning: () => api.post('/briefings/morning/send'),
}

export const chatApi = {
  send: (data: { message: string; conversation_id?: string; context?: object }) =>
    api.post('/chat', data),
  getConversation: (id: string) => api.get(`/chat/conversations/${id}`),
  summarizeThread: (threadId: string) =>
    api.post('/chat/quick-actions/summarize-thread', null, { params: { thread_id: threadId } }),
  findActionItems: (threadId: string) =>
    api.post('/chat/quick-actions/find-action-items', null, { params: { thread_id: threadId } }),
  searchEmails: (query: string, limit?: number) =>
    api.post('/chat/quick-actions/search-emails', null, { params: { query, limit } }),
}

export const dashboardApi = {
  summary: () => api.get('/dashboard/summary'),
  stats: (days?: number) => api.get('/dashboard/stats', { params: { days } }),
}

export const todosApi = {
  list: (params?: {
    status?: string
    category?: string
    priority?: string
    include_completed?: boolean
  }) => api.get('/todos', { params }),
  grouped: () => api.get('/todos/grouped'),
  get: (id: number) => api.get(`/todos/${id}`),
  create: (data: {
    title: string
    description?: string
    category: string
    priority?: string
    due_date?: string
    contact_name?: string
    contact_email?: string
  }) => api.post('/todos', data),
  update: (id: number, data: {
    title?: string
    description?: string
    priority?: string
    due_date?: string
    status?: string
  }) => api.patch(`/todos/${id}`, data),
  complete: (id: number, reason?: string) =>
    api.post(`/todos/${id}/complete`, null, { params: { reason } }),
  snooze: (id: number, snooze_until: string) =>
    api.post(`/todos/${id}/snooze`, { snooze_until }),
  cancel: (id: number, reason?: string) =>
    api.post(`/todos/${id}/cancel`, null, { params: { reason } }),
  delete: (id: number) => api.delete(`/todos/${id}`),
  overdue: () => api.get('/todos/overdue'),
  dueToday: () => api.get('/todos/due-today'),
  scan: (userEmail: string, sinceDays?: number) =>
    api.post('/todos/scan', null, { params: { user_email: userEmail, since_days: sinceDays } }),
  scanProgress: (scanId: string) => api.get(`/todos/scan/${scanId}`),
  draftEmail: (id: number) => api.post(`/todos/${id}/draft-email`),
}

export const meetingsApi = {
  status: () => api.get('/meetings/status'),
  recent: (limit?: number) => api.get('/meetings/recent', { params: { limit } }),
  search: (params?: {
    query?: string
    participant_email?: string
    start_date?: string
    end_date?: string
    limit?: number
  }) => api.get('/meetings/search', { params }),
  get: (meetingId: string) => api.get(`/meetings/${meetingId}`),
  getSummary: (meetingId: string) => api.get(`/meetings/${meetingId}/summary`),
  sync: (limit?: number) => api.post('/meetings/sync', null, { params: { limit } }),
  cache: (meetingId: string) => api.post(`/meetings/${meetingId}/cache`),
  cachedList: (params?: { limit?: number; offset?: number }) =>
    api.get('/meetings/cached/list', { params }),
  // Plaud recordings
  plaudList: (params?: { limit?: number; search?: string }) =>
    api.get('/meetings/plaud', { params }),
  plaudGet: (recordingId: number) => api.get(`/meetings/plaud/${recordingId}`),
  // Unified meetings
  unifiedList: (params?: { limit?: number; source?: 'all' | 'fireflies' | 'plaud'; search?: string }) =>
    api.get('/meetings/unified', { params }),
  unifiedSync: () => api.post('/meetings/unified/sync'),
}
