'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { todosApi } from '@/lib/api'
import { formatDate, formatTime, cn } from '@/lib/utils'
import { useState } from 'react'
import {
  ArrowLeft,
  ListTodo,
  User,
  Mail,
  AlertTriangle,
  Loader2,
  AlertCircle,
  Reply,
  CheckCircle,
  XCircle,
  Copy,
  ExternalLink,
  Calendar,
  FileText,
  Clock,
  Pause,
} from 'lucide-react'

interface SourceEmail {
  id: number
  gmail_id: string
  subject: string
  sender_email: string
  sender_name: string | null
  received_at: string
  snippet: string | null
  body_text: string | null
}

interface Todo {
  id: number
  title: string
  description: string | null
  category: string
  priority: string
  status: string
  due_date: string | null
  source_type: string
  source_id: string | null
  source_summary: string | null
  contact_name: string | null
  contact_email: string | null
  snoozed_until: string | null
  detection_confidence: number | null
  detected_deadline_text: string | null
  completed_at: string | null
  completed_reason: string | null
  created_at: string
  updated_at: string
  source_email: SourceEmail | null
}

interface DraftReply {
  subject: string
  body: string
  confidence: number
  notes: string | null
}

export default function TodoDetailPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const todoId = Number(params.id)
  const [draft, setDraft] = useState<DraftReply | null>(null)
  const [copied, setCopied] = useState(false)
  const [showSnoozeModal, setShowSnoozeModal] = useState(false)
  const [snoozeDate, setSnoozeDate] = useState('')

  // Fetch todo details
  const { data: todo, isLoading, error } = useQuery({
    queryKey: ['todo', todoId],
    queryFn: () => todosApi.get(todoId).then((res) => res.data as Todo),
    enabled: !isNaN(todoId),
  })

  // Generate draft mutation
  const draftMutation = useMutation({
    mutationFn: () => todosApi.draftEmail(todoId),
    onSuccess: (response) => {
      setDraft(response.data as DraftReply)
    },
  })

  // Complete mutation
  const completeMutation = useMutation({
    mutationFn: () => todosApi.complete(todoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todo', todoId] })
      queryClient.invalidateQueries({ queryKey: ['todos'] })
      queryClient.invalidateQueries({ queryKey: ['todos-grouped'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
      router.push('/')
    },
  })

  // Snooze mutation
  const snoozeMutation = useMutation({
    mutationFn: (snoozeUntil: string) => todosApi.snooze(todoId, snoozeUntil),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todo', todoId] })
      queryClient.invalidateQueries({ queryKey: ['todos'] })
      queryClient.invalidateQueries({ queryKey: ['todos-grouped'] })
      setShowSnoozeModal(false)
      setSnoozeDate('')
    },
  })

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: () => todosApi.cancel(todoId, 'Cancelled from detail view'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todo', todoId] })
      queryClient.invalidateQueries({ queryKey: ['todos'] })
      queryClient.invalidateQueries({ queryKey: ['todos-grouped'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
      router.push('/')
    },
  })

  const handleCopyDraft = () => {
    if (draft) {
      const text = `Subject: ${draft.subject}\n\n${draft.body}`
      navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleSendEmail = () => {
    if (todo && todo.contact_email) {
      const subject = draft ? encodeURIComponent(draft.subject) : ''
      const body = draft ? encodeURIComponent(draft.body) : ''
      window.open(`mailto:${todo.contact_email}?subject=${subject}&body=${body}`, '_blank')
    }
  }

  const handleSnooze = () => {
    if (snoozeDate) {
      snoozeMutation.mutate(snoozeDate)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error || !todo) {
    return (
      <div className="p-6">
        <button
          onClick={() => router.back()}
          className="mb-6 flex items-center gap-2 text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </button>
        <div className="rounded-lg bg-red-50 p-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-6 w-6 text-red-500 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-red-800">Todo Not Found</h3>
              <p className="mt-1 text-sm text-red-700">
                The todo item you're looking for could not be found.
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const priorityColors: Record<string, string> = {
    urgent: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    normal: 'bg-blue-100 text-blue-700',
    low: 'bg-green-100 text-green-700',
  }

  const categoryLabels: Record<string, string> = {
    self_reminder: 'Self Reminder',
    request_received: 'Request Received',
    commitment_made: 'Commitment Made',
    meeting_action: 'Meeting Action',
    manual: 'Manual',
  }

  const categoryColors: Record<string, string> = {
    self_reminder: 'bg-purple-100 text-purple-700',
    request_received: 'bg-blue-100 text-blue-700',
    commitment_made: 'bg-green-100 text-green-700',
    meeting_action: 'bg-yellow-100 text-yellow-700',
    manual: 'bg-gray-100 text-gray-700',
  }

  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    snoozed: 'bg-purple-100 text-purple-700',
    completed: 'bg-green-100 text-green-700',
    cancelled: 'bg-gray-100 text-gray-700',
  }

  const isActive = ['pending', 'snoozed'].includes(todo.status)
  const canGenerateDraft = ['request_received', 'commitment_made'].includes(todo.category)
  const isOverdue = todo.due_date && new Date(todo.due_date) < new Date() && isActive

  return (
    <div className="p-6">
      {/* Back button */}
      <button
        onClick={() => router.back()}
        className="mb-6 flex items-center gap-2 text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Dashboard
      </button>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-purple-100">
              <ListTodo className="h-6 w-6 text-purple-600" />
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-gray-900">{todo.title}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <span
                  className={cn(
                    'rounded-full px-2.5 py-0.5 text-xs font-medium',
                    categoryColors[todo.category] || 'bg-gray-100 text-gray-700'
                  )}
                >
                  {categoryLabels[todo.category] || todo.category}
                </span>
                <span
                  className={cn(
                    'rounded-full px-2.5 py-0.5 text-xs font-medium',
                    priorityColors[todo.priority] || 'bg-gray-100 text-gray-700'
                  )}
                >
                  {todo.priority}
                </span>
                <span
                  className={cn(
                    'rounded-full px-2.5 py-0.5 text-xs font-medium',
                    statusColors[todo.status] || 'bg-gray-100 text-gray-700'
                  )}
                >
                  {todo.status}
                </span>
                {isOverdue && (
                  <span className="flex items-center gap-1 rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
                    <AlertTriangle className="h-3 w-3" />
                    Overdue
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Action buttons */}
          {isActive && (
            <div className="flex gap-2">
              <button
                onClick={() => completeMutation.mutate()}
                disabled={completeMutation.isPending}
                className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-white hover:bg-green-700 disabled:opacity-50"
              >
                {completeMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle className="h-4 w-4" />
                )}
                Complete
              </button>
              <button
                onClick={() => setShowSnoozeModal(true)}
                className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-gray-700 hover:bg-gray-50"
              >
                <Pause className="h-4 w-4" />
                Snooze
              </button>
              <button
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {cancelMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <XCircle className="h-4 w-4" />
                )}
                Cancel
              </button>
            </div>
          )}
        </div>

        {/* Contact and Due Date */}
        <div className="mt-4 rounded-lg bg-gray-50 p-4">
          <div className="flex flex-wrap items-center gap-6 text-sm">
            {todo.contact_email && (
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-gray-400" />
                <span className="font-medium text-gray-900">
                  {todo.contact_name || todo.contact_email}
                </span>
                {todo.contact_name && (
                  <span className="text-gray-500">&lt;{todo.contact_email}&gt;</span>
                )}
              </div>
            )}
            {todo.due_date && (
              <div className="flex items-center gap-2 text-gray-500">
                <Calendar className="h-4 w-4" />
                Due: {formatDate(todo.due_date)}
                {isOverdue && <span className="text-red-600">(overdue)</span>}
              </div>
            )}
            {todo.snoozed_until && (
              <div className="flex items-center gap-2 text-purple-600">
                <Clock className="h-4 w-4" />
                Snoozed until: {formatDate(todo.snoozed_until)}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main content - 2 columns */}
        <div className="space-y-6 lg:col-span-2">
          {/* Description */}
          {todo.description && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <FileText className="h-5 w-5 text-purple-600" />
                Description
              </h2>
              <p className="text-gray-700 whitespace-pre-wrap">{todo.description}</p>
            </div>
          )}

          {/* Source Email */}
          {todo.source_email && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <Mail className="h-5 w-5 text-blue-600" />
                Source Email
              </h2>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">
                      {todo.source_email.sender_name || todo.source_email.sender_email}
                    </span>
                    {todo.source_email.sender_name && (
                      <span className="text-gray-500">
                        &lt;{todo.source_email.sender_email}&gt;
                      </span>
                    )}
                  </div>
                  <span className="text-gray-400">
                    {formatDate(todo.source_email.received_at)} at{' '}
                    {formatTime(todo.source_email.received_at)}
                  </span>
                </div>
                <p className="mb-2 font-medium text-gray-900">
                  {todo.source_email.subject}
                </p>
                <div className="prose max-w-none text-sm text-gray-700">
                  {todo.source_email.body_text ? (
                    <p className="whitespace-pre-wrap">{todo.source_email.body_text}</p>
                  ) : todo.source_email.snippet ? (
                    <p className="italic">{todo.source_email.snippet}</p>
                  ) : (
                    <p className="italic text-gray-400">No content available</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Draft Response Section (only for request_received and commitment_made) */}
          {canGenerateDraft && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
                  <Reply className="h-5 w-5 text-blue-600" />
                  Respond
                </h2>
                {!draft && (
                  <button
                    onClick={() => draftMutation.mutate()}
                    disabled={draftMutation.isPending}
                    className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
                  >
                    {draftMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Reply className="h-4 w-4" />
                    )}
                    Generate Response Draft
                  </button>
                )}
              </div>

              {draft ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500">
                      Confidence: {Math.round(draft.confidence * 100)}%
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={handleCopyDraft}
                        className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                      >
                        <Copy className="h-4 w-4" />
                        {copied ? 'Copied!' : 'Copy'}
                      </button>
                      {todo.contact_email && (
                        <button
                          onClick={handleSendEmail}
                          className="flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
                        >
                          <ExternalLink className="h-4 w-4" />
                          Open in Email
                        </button>
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Subject</label>
                    <p className="mt-1 rounded-lg border border-gray-200 bg-gray-50 p-3 text-gray-900">
                      {draft.subject}
                    </p>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-700">Body</label>
                    <div className="mt-1 rounded-lg border border-gray-200 bg-gray-50 p-3">
                      <p className="whitespace-pre-wrap text-gray-700">{draft.body}</p>
                    </div>
                  </div>
                  {draft.notes && (
                    <div className="rounded-lg bg-yellow-50 p-3 text-sm text-yellow-700">
                      <strong>Notes:</strong> {draft.notes}
                    </div>
                  )}
                  <button
                    onClick={() => draftMutation.mutate()}
                    disabled={draftMutation.isPending}
                    className="text-sm text-blue-600 hover:text-blue-700"
                  >
                    {draftMutation.isPending ? 'Regenerating...' : 'Regenerate draft'}
                  </button>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-4">
                  Click "Generate Response Draft" to create an email response for this{' '}
                  {todo.category === 'request_received' ? 'request' : 'commitment'}.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Sidebar - 1 column */}
        <div className="space-y-6">
          {/* Source Summary */}
          {todo.source_summary && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Source</h2>
              <p className="text-gray-700">{todo.source_summary}</p>
            </div>
          )}

          {/* Detection Info */}
          {todo.detection_confidence && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Detection</h2>
              <dl className="space-y-3 text-sm">
                <div>
                  <dt className="text-gray-500">Confidence</dt>
                  <dd className="text-gray-700">{Math.round(todo.detection_confidence * 100)}%</dd>
                </div>
                {todo.detected_deadline_text && (
                  <div>
                    <dt className="text-gray-500">Detected Deadline</dt>
                    <dd className="text-gray-700">"{todo.detected_deadline_text}"</dd>
                  </div>
                )}
              </dl>
            </div>
          )}

          {/* Details */}
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">Details</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-700">{formatDate(todo.created_at)}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Last Updated</dt>
                <dd className="text-gray-700">{formatDate(todo.updated_at)}</dd>
              </div>
              {todo.completed_at && (
                <div>
                  <dt className="text-gray-500">Completed</dt>
                  <dd className="text-gray-700">
                    {formatDate(todo.completed_at)}
                    {todo.completed_reason && ` - ${todo.completed_reason}`}
                  </dd>
                </div>
              )}
              <div>
                <dt className="text-gray-500">Source Type</dt>
                <dd className="text-gray-700 capitalize">{todo.source_type}</dd>
              </div>
              {todo.source_id && (
                <div>
                  <dt className="text-gray-500">Source ID</dt>
                  <dd className="font-mono text-xs text-gray-700 truncate">{todo.source_id}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>

      {/* Snooze Modal */}
      {showSnoozeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Snooze Todo</h3>
            <p className="text-sm text-gray-500 mb-4">
              Select a date to snooze this todo until:
            </p>
            <input
              type="date"
              value={snoozeDate}
              onChange={(e) => setSnoozeDate(e.target.value)}
              min={new Date().toISOString().split('T')[0]}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 mb-4 focus:border-blue-500 focus:outline-none"
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowSnoozeModal(false)
                  setSnoozeDate('')
                }}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleSnooze}
                disabled={!snoozeDate || snoozeMutation.isPending}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {snoozeMutation.isPending ? 'Snoozing...' : 'Snooze'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
