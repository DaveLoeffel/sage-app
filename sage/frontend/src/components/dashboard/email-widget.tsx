'use client'

import Link from 'next/link'
import { Mail, ChevronRight, AlertCircle } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'

interface Email {
  id: number
  gmail_id: string
  subject: string
  sender_email: string
  sender_name?: string
  snippet?: string
  received_at: string
  category?: string
  priority?: string
  is_unread: boolean
}

interface EmailWidgetProps {
  priorityEmails: Email[]
}

export function EmailWidget({ priorityEmails }: EmailWidgetProps) {
  return (
    <div className="rounded-lg bg-white shadow-sm">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <h2 className="text-lg font-semibold text-gray-900">Priority Emails</h2>
        <Link
          href="/emails"
          className="flex items-center text-sm text-blue-600 hover:text-blue-700"
        >
          View inbox
          <ChevronRight className="ml-1 h-4 w-4" />
        </Link>
      </div>

      <div className="divide-y">
        {priorityEmails.length > 0 ? (
          priorityEmails.map((email) => (
            <EmailItem key={email.id} email={email} />
          ))
        ) : (
          <div className="p-8 text-center">
            <Mail className="mx-auto h-8 w-8 text-gray-400" />
            <p className="mt-2 text-gray-500">No priority emails</p>
          </div>
        )}
      </div>
    </div>
  )
}

function EmailItem({ email }: { email: Email }) {
  const categoryBadges: Record<string, { bg: string; text: string }> = {
    urgent: { bg: 'bg-red-100', text: 'text-red-700' },
    action_required: { bg: 'bg-orange-100', text: 'text-orange-700' },
    fyi: { bg: 'bg-blue-100', text: 'text-blue-700' },
    newsletter: { bg: 'bg-gray-100', text: 'text-gray-700' },
  }

  const badge = email.category ? categoryBadges[email.category] : null

  return (
    <Link
      href={`/emails/${email.id}`}
      className="block p-4 transition-colors hover:bg-gray-50"
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          {email.priority === 'urgent' ? (
            <AlertCircle className="h-5 w-5 text-red-500" />
          ) : (
            <Mail className={`h-5 w-5 ${email.is_unread ? 'text-blue-500' : 'text-gray-400'}`} />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`font-medium ${email.is_unread ? 'text-gray-900' : 'text-gray-600'}`}>
              {email.sender_name || email.sender_email}
            </span>
            {badge && (
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge.bg} ${badge.text}`}>
                {email.category?.replace('_', ' ')}
              </span>
            )}
          </div>
          <p className={`truncate ${email.is_unread ? 'font-medium text-gray-900' : 'text-gray-600'}`}>
            {email.subject}
          </p>
          {email.snippet && (
            <p className="truncate text-sm text-gray-500">{email.snippet}</p>
          )}
          <p className="mt-1 text-xs text-gray-400">
            {formatRelativeTime(email.received_at)}
          </p>
        </div>
      </div>
    </Link>
  )
}
