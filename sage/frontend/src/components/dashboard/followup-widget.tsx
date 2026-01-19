'use client'

import Link from 'next/link'
import { AlertTriangle, Clock, ChevronRight } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'

interface Followup {
  id: number
  subject: string
  contact_email: string
  contact_name?: string
  due_date: string
  status: string
  priority: string
  is_overdue?: boolean
  days_until_due?: number
}

interface FollowupWidgetProps {
  overdueFollowups: Followup[]
  upcomingFollowups: Followup[]
}

export function FollowupWidget({ overdueFollowups, upcomingFollowups }: FollowupWidgetProps) {
  return (
    <div className="rounded-lg bg-white shadow-sm">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <h2 className="text-lg font-semibold text-gray-900">Follow-ups</h2>
        <Link
          href="/followups"
          className="flex items-center text-sm text-blue-600 hover:text-blue-700"
        >
          View all
          <ChevronRight className="ml-1 h-4 w-4" />
        </Link>
      </div>

      <div className="divide-y">
        {/* Overdue Section */}
        {overdueFollowups.length > 0 && (
          <div className="p-4">
            <div className="mb-3 flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm font-medium">Overdue ({overdueFollowups.length})</span>
            </div>
            <div className="space-y-3">
              {overdueFollowups.slice(0, 3).map((followup) => (
                <FollowupItem key={followup.id} followup={followup} isOverdue />
              ))}
            </div>
          </div>
        )}

        {/* Upcoming Section */}
        {upcomingFollowups.length > 0 && (
          <div className="p-4">
            <div className="mb-3 flex items-center gap-2 text-yellow-600">
              <Clock className="h-4 w-4" />
              <span className="text-sm font-medium">Upcoming ({upcomingFollowups.length})</span>
            </div>
            <div className="space-y-3">
              {upcomingFollowups.slice(0, 3).map((followup) => (
                <FollowupItem key={followup.id} followup={followup} />
              ))}
            </div>
          </div>
        )}

        {/* Empty State */}
        {overdueFollowups.length === 0 && upcomingFollowups.length === 0 && (
          <div className="p-8 text-center">
            <p className="text-gray-500">No pending follow-ups</p>
          </div>
        )}
      </div>
    </div>
  )
}

function FollowupItem({ followup, isOverdue = false }: { followup: Followup; isOverdue?: boolean }) {
  const priorityColors = {
    urgent: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    normal: 'bg-gray-100 text-gray-700',
    low: 'bg-green-100 text-green-700',
  }

  return (
    <Link
      href={`/followups/${followup.id}`}
      className={`block rounded-lg border p-3 transition-colors hover:bg-gray-50 ${
        isOverdue ? 'border-red-200 bg-red-50' : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="truncate font-medium text-gray-900">{followup.subject}</p>
          <p className="text-sm text-gray-500">
            {followup.contact_name || followup.contact_email}
          </p>
        </div>
        <span
          className={`ml-2 rounded-full px-2 py-1 text-xs font-medium ${
            priorityColors[followup.priority as keyof typeof priorityColors] || priorityColors.normal
          }`}
        >
          {followup.priority}
        </span>
      </div>
      <div className="mt-2 text-xs text-gray-400">
        Due {formatRelativeTime(followup.due_date)}
      </div>
    </Link>
  )
}
