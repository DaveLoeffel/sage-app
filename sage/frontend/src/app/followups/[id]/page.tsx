'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { followupsApi } from '@/lib/api'
import { formatDate, formatTime, formatRelativeTime, cn } from '@/lib/utils'
import { useState } from 'react'
import {
  ArrowLeft,
  Clock,
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

interface Followup {
  id: number
  user_id: number
  gmail_id: string
  thread_id: string
  email_id: number | null
  subject: string
  contact_email: string
  contact_name: string | null
  status: string
  priority: string
  due_date: string
  notes: string | null
  ai_summary: string | null
  escalation_email: string | null
  escalation_days: number
  is_overdue: boolean
  days_until_due: number | null
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

export default function FollowupDetailPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const followupId = Number(params.id)
  const [draft, setDraft] = useState<DraftReply | null>(null)
  const [copied, setCopied] = useState(false)

  // Fetch followup details
  const { data: followup, isLoading, error } = useQuery({
    queryKey: ['followup', followupId],
    queryFn: () => followupsApi.get(followupId).then((res) => res.data as Followup),
    enabled: !isNaN(followupId),
  })

  // Generate draft mutation
  const draftMutation = useMutation({
    mutationFn: () => followupsApi.draft(followupId),
    onSuccess: (response) => {
      setDraft(response.data as DraftReply)
    },
  })

  // Complete mutation
  const completeMutation = useMutation({
    mutationFn: () => followupsApi.complete(followupId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['followup', followupId] })
      queryClient.invalidateQueries({ queryKey: ['followups'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
      router.push('/followups')
    },
  })

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: () => followupsApi.cancel(followupId, 'Dismissed from detail view'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['followup', followupId] })
      queryClient.invalidateQueries({ queryKey: ['followups'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
      router.push('/followups')
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
    if (followup) {
      const subject = draft ? encodeURIComponent(draft.subject) : encodeURIComponent(`Re: ${followup.subject}`)
      const body = draft ? encodeURIComponent(draft.body) : ''
      window.open(`mailto:${followup.contact_email}?subject=${subject}&body=${body}`, '_blank')
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error || !followup) {
    return (
      <div className="p-6">
        <button
          onClick={() => router.back()}
          className="mb-6 flex items-center gap-2 text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Follow-ups
        </button>
        <div className="rounded-lg bg-red-50 p-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-6 w-6 text-red-500 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-red-800">Follow-up Not Found</h3>
              <p className="mt-1 text-sm text-red-700">
                The follow-up you're looking for could not be found.
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

  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    reminded: 'bg-orange-100 text-orange-700',
    escalated: 'bg-red-100 text-red-700',
    completed: 'bg-green-100 text-green-700',
    cancelled: 'bg-gray-100 text-gray-700',
  }

  const isActive = ['pending', 'reminded', 'escalated'].includes(followup.status)

  return (
    <div className="p-6">
      {/* Back button */}
      <button
        onClick={() => router.back()}
        className="mb-6 flex items-center gap-2 text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Follow-ups
      </button>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-yellow-100">
              <Clock className="h-6 w-6 text-yellow-600" />
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-gray-900">{followup.subject}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                <span
                  className={cn(
                    'rounded-full px-2.5 py-0.5 text-xs font-medium',
                    priorityColors[followup.priority] || 'bg-gray-100 text-gray-700'
                  )}
                >
                  {followup.priority}
                </span>
                <span
                  className={cn(
                    'rounded-full px-2.5 py-0.5 text-xs font-medium',
                    statusColors[followup.status] || 'bg-gray-100 text-gray-700'
                  )}
                >
                  {followup.status}
                </span>
                {followup.is_overdue && (
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
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                {cancelMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <XCircle className="h-4 w-4" />
                )}
                Dismiss
              </button>
            </div>
          )}
        </div>

        {/* Contact and Due Date */}
        <div className="mt-4 rounded-lg bg-gray-50 p-4">
          <div className="flex flex-wrap items-center gap-6 text-sm">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-gray-400" />
              <span className="font-medium text-gray-900">
                {followup.contact_name || followup.contact_email}
              </span>
              {followup.contact_name && (
                <span className="text-gray-500">&lt;{followup.contact_email}&gt;</span>
              )}
            </div>
            <div className="flex items-center gap-2 text-gray-500">
              <Calendar className="h-4 w-4" />
              Due: {formatDate(followup.due_date)}
              {followup.days_until_due !== null && followup.days_until_due >= 0 && (
                <span className="text-green-600">({followup.days_until_due} days left)</span>
              )}
              {followup.is_overdue && (
                <span className="text-red-600">(overdue)</span>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main content - 2 columns */}
        <div className="space-y-6 lg:col-span-2">
          {/* Source Email */}
          {followup.source_email && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <Mail className="h-5 w-5 text-blue-600" />
                Source Email
              </h2>
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="mb-3 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900">
                      {followup.source_email.sender_name || followup.source_email.sender_email}
                    </span>
                    {followup.source_email.sender_name && (
                      <span className="text-gray-500">
                        &lt;{followup.source_email.sender_email}&gt;
                      </span>
                    )}
                  </div>
                  <span className="text-gray-400">
                    {formatDate(followup.source_email.received_at)} at{' '}
                    {formatTime(followup.source_email.received_at)}
                  </span>
                </div>
                <p className="mb-2 font-medium text-gray-900">
                  {followup.source_email.subject}
                </p>
                <div className="prose max-w-none text-sm text-gray-700">
                  {followup.source_email.body_text ? (
                    <p className="whitespace-pre-wrap">{followup.source_email.body_text}</p>
                  ) : followup.source_email.snippet ? (
                    <p className="italic">{followup.source_email.snippet}</p>
                  ) : (
                    <p className="italic text-gray-400">No content available</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Draft Follow-up Section */}
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
                <Reply className="h-5 w-5 text-blue-600" />
                Draft Follow-up
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
                  Generate Draft
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
                    <button
                      onClick={handleSendEmail}
                      className="flex items-center gap-1 rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
                    >
                      <ExternalLink className="h-4 w-4" />
                      Open in Email
                    </button>
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
                Click "Generate Draft" to create a follow-up email based on the original conversation.
              </p>
            )}
          </div>
        </div>

        {/* Sidebar - 1 column */}
        <div className="space-y-6">
          {/* Notes */}
          {followup.notes && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <FileText className="h-5 w-5 text-blue-600" />
                Notes
              </h2>
              <p className="text-gray-700">{followup.notes}</p>
            </div>
          )}

          {/* AI Summary */}
          {followup.ai_summary && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">AI Summary</h2>
              <p className="text-gray-700">{followup.ai_summary}</p>
            </div>
          )}

          {/* Details */}
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">Details</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Created</dt>
                <dd className="text-gray-700">{formatDate(followup.created_at)}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Last Updated</dt>
                <dd className="text-gray-700">{formatDate(followup.updated_at)}</dd>
              </div>
              {followup.escalation_email && (
                <div>
                  <dt className="text-gray-500">Escalation Contact</dt>
                  <dd className="text-gray-700">{followup.escalation_email}</dd>
                </div>
              )}
              <div>
                <dt className="text-gray-500">Thread ID</dt>
                <dd className="font-mono text-xs text-gray-700 truncate">{followup.thread_id}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
