'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { emailsApi } from '@/lib/api'
import { formatDate, formatTime } from '@/lib/utils'
import {
  ArrowLeft,
  Mail,
  Clock,
  User,
  Users,
  FileText,
  CheckSquare,
  Loader2,
  AlertCircle,
  Sparkles,
  Reply,
  Tag,
  AlertTriangle,
  Paperclip,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useState } from 'react'

interface Email {
  id: number
  gmail_id: string
  thread_id: string
  subject: string
  sender_email: string
  sender_name: string | null
  to_emails: string[] | null
  snippet: string | null
  body_text: string | null
  labels: string[] | null
  is_unread: boolean
  has_attachments: boolean
  received_at: string
  category: string | null
  priority: string | null
  summary: string | null
  requires_response: boolean | null
  action_items?: string[] | null
}

interface DraftReply {
  subject: string
  body: string
  confidence: number
  notes: string | null
}

export default function EmailDetailPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const emailId = Number(params.id)
  const [showDraftReply, setShowDraftReply] = useState(false)

  // Fetch email details
  const { data: email, isLoading, error } = useQuery({
    queryKey: ['email', emailId],
    queryFn: () => emailsApi.get(emailId).then((res) => res.data as Email),
    enabled: !isNaN(emailId),
  })

  // Analyze mutation
  const analyzeMutation = useMutation({
    mutationFn: () => emailsApi.analyze(emailId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['email', emailId] })
    },
  })

  // Draft reply mutation
  const draftReplyMutation = useMutation({
    mutationFn: (data: { tone?: string; key_points?: string[]; context?: string }) =>
      emailsApi.draftReply(emailId, data),
    onSuccess: () => {
      setShowDraftReply(true)
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error || !email) {
    return (
      <div className="p-6">
        <button
          onClick={() => router.back()}
          className="mb-6 flex items-center gap-2 text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Emails
        </button>
        <div className="rounded-lg bg-red-50 p-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-6 w-6 text-red-500 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-red-800">Email Not Found</h3>
              <p className="mt-1 text-sm text-red-700">
                The email you're looking for could not be found.
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
    low: 'bg-gray-100 text-gray-700',
  }

  const categoryColors: Record<string, string> = {
    action_required: 'bg-red-100 text-red-700',
    follow_up: 'bg-yellow-100 text-yellow-700',
    meeting: 'bg-purple-100 text-purple-700',
    fyi: 'bg-blue-100 text-blue-700',
    newsletter: 'bg-gray-100 text-gray-700',
    personal: 'bg-green-100 text-green-700',
    spam: 'bg-gray-100 text-gray-500',
  }

  const draftReply = draftReplyMutation.data?.data as DraftReply | undefined

  return (
    <div className="p-6">
      {/* Back button */}
      <button
        onClick={() => router.back()}
        className="mb-6 flex items-center gap-2 text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Emails
      </button>

      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-sage-100">
              <Mail className="h-6 w-6 text-sage-600" />
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-gray-900">{email.subject}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-3">
                {/* Badges */}
                {email.priority && (
                  <span
                    className={cn(
                      'rounded-full px-2.5 py-0.5 text-xs font-medium',
                      priorityColors[email.priority] || 'bg-gray-100 text-gray-700'
                    )}
                  >
                    {email.priority}
                  </span>
                )}
                {email.category && (
                  <span
                    className={cn(
                      'rounded-full px-2.5 py-0.5 text-xs font-medium',
                      categoryColors[email.category] || 'bg-gray-100 text-gray-700'
                    )}
                  >
                    {email.category.replace('_', ' ')}
                  </span>
                )}
                {email.is_unread && (
                  <span className="rounded-full bg-sage-100 px-2.5 py-0.5 text-xs font-medium text-sage-700">
                    Unread
                  </span>
                )}
                {email.has_attachments && (
                  <span className="flex items-center gap-1 text-xs text-gray-500">
                    <Paperclip className="h-3 w-3" />
                    Attachments
                  </span>
                )}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => analyzeMutation.mutate()}
              disabled={analyzeMutation.isPending}
              className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {analyzeMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Analyze
            </button>
            <button
              onClick={() => draftReplyMutation.mutate({})}
              disabled={draftReplyMutation.isPending}
              className="flex items-center gap-2 rounded-lg bg-sage-600 px-4 py-2 text-white hover:bg-sage-700 disabled:opacity-50"
            >
              {draftReplyMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Reply className="h-4 w-4" />
              )}
              Draft Reply
            </button>
          </div>
        </div>

        {/* Sender info */}
        <div className="mt-4 rounded-lg bg-gray-50 p-4">
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-gray-400" />
              <span className="font-medium text-gray-900">
                {email.sender_name || email.sender_email}
              </span>
              {email.sender_name && (
                <span className="text-gray-500">&lt;{email.sender_email}&gt;</span>
              )}
            </div>
            <div className="flex items-center gap-2 text-gray-500">
              <Clock className="h-4 w-4" />
              {formatDate(email.received_at)} at {formatTime(email.received_at)}
            </div>
          </div>
          {email.to_emails && email.to_emails.length > 0 && (
            <div className="mt-2 flex items-center gap-2 text-sm text-gray-500">
              <Users className="h-4 w-4" />
              <span>To: {email.to_emails.join(', ')}</span>
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main content - 2 columns */}
        <div className="space-y-6 lg:col-span-2">
          {/* AI Summary */}
          {email.summary && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <Sparkles className="h-5 w-5 text-sage-600" />
                AI Summary
              </h2>
              <p className="text-gray-700">{email.summary}</p>
            </div>
          )}

          {/* Draft Reply */}
          {showDraftReply && draftReply && (
            <div className="rounded-lg bg-white p-6 shadow-sm border-2 border-sage-200">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <Reply className="h-5 w-5 text-sage-600" />
                Draft Reply
                <span className="ml-auto text-sm font-normal text-gray-500">
                  Confidence: {Math.round(draftReply.confidence * 100)}%
                </span>
              </h2>
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-700">Subject</label>
                  <p className="mt-1 text-gray-900">{draftReply.subject}</p>
                </div>
                <div>
                  <label className="text-sm font-medium text-gray-700">Body</label>
                  <div className="mt-1 rounded-lg border border-gray-200 bg-gray-50 p-4">
                    <p className="whitespace-pre-wrap text-gray-700">{draftReply.body}</p>
                  </div>
                </div>
                {draftReply.notes && (
                  <div className="rounded-lg bg-yellow-50 p-3 text-sm text-yellow-700">
                    <strong>Notes:</strong> {draftReply.notes}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Email Body */}
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
              <FileText className="h-5 w-5 text-sage-600" />
              Email Content
            </h2>
            <div className="prose max-w-none">
              {email.body_text ? (
                <p className="whitespace-pre-wrap text-gray-700">{email.body_text}</p>
              ) : (
                <p className="text-gray-500 italic">No email content available</p>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar - 1 column */}
        <div className="space-y-6">
          {/* Requires Response */}
          {email.requires_response && (
            <div className="rounded-lg bg-yellow-50 p-4 shadow-sm">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-600" />
                <span className="font-medium text-yellow-800">Response Required</span>
              </div>
            </div>
          )}

          {/* Action Items */}
          {email.action_items && email.action_items.length > 0 && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <CheckSquare className="h-5 w-5 text-sage-600" />
                Action Items
              </h2>
              <ul className="space-y-2">
                {email.action_items.map((item, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <input type="checkbox" className="mt-1 rounded border-gray-300" />
                    <span className="text-gray-700">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Labels */}
          {email.labels && email.labels.length > 0 && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <Tag className="h-5 w-5 text-sage-600" />
                Labels
              </h2>
              <div className="flex flex-wrap gap-2">
                {email.labels.map((label, index) => (
                  <span
                    key={index}
                    className="rounded-full bg-gray-100 px-3 py-1 text-sm text-gray-700"
                  >
                    {label}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Quick Info */}
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">Details</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Thread ID</dt>
                <dd className="font-mono text-xs text-gray-700 truncate">{email.thread_id}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Gmail ID</dt>
                <dd className="font-mono text-xs text-gray-700 truncate">{email.gmail_id}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
