'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { followupsApi } from '@/lib/api'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import {
  ClipboardCheck,
  Plus,
  Filter,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Loader2,
} from 'lucide-react'
import Link from 'next/link'

export default function FollowupsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const [showOverdueOnly, setShowOverdueOnly] = useState(false)

  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['followups', { statusFilter, priorityFilter, showOverdueOnly }],
    queryFn: () =>
      followupsApi
        .list({
          status: statusFilter || undefined,
          priority: priorityFilter || undefined,
          overdue_only: showOverdueOnly,
        })
        .then((res) => res.data),
  })

  const completeMutation = useMutation({
    mutationFn: (id: number) => followupsApi.complete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['followups'] })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (id: number) => followupsApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['followups'] })
    },
  })

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Follow-ups</h1>
          <p className="text-gray-500">Track emails requiring responses</p>
        </div>
        <Link
          href="/followups/new"
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4" />
          New Follow-up
        </Link>
      </div>

      {/* Stats */}
      {data && (
        <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-lg bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <Clock className="h-8 w-8 text-yellow-500" />
              <div>
                <p className="text-2xl font-bold">{data.pending_count}</p>
                <p className="text-sm text-gray-500">Pending</p>
              </div>
            </div>
          </div>
          <div className="rounded-lg bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-8 w-8 text-red-500" />
              <div>
                <p className="text-2xl font-bold">{data.overdue_count}</p>
                <p className="text-sm text-gray-500">Overdue</p>
              </div>
            </div>
          </div>
          <div className="rounded-lg bg-white p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <ClipboardCheck className="h-8 w-8 text-blue-500" />
              <div>
                <p className="text-2xl font-bold">{data.total}</p>
                <p className="text-sm text-gray-500">Total Active</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none"
        >
          <option value="">Active Follow-ups</option>
          <option value="pending">Pending</option>
          <option value="reminded">Reminded</option>
          <option value="escalated">Escalated</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>

        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none"
        >
          <option value="">All Priorities</option>
          <option value="urgent">Urgent</option>
          <option value="high">High</option>
          <option value="normal">Normal</option>
          <option value="low">Low</option>
        </select>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={showOverdueOnly}
            onChange={(e) => setShowOverdueOnly(e.target.checked)}
            className="rounded border-gray-300"
          />
          <span className="text-sm text-gray-600">Overdue only</span>
        </label>
      </div>

      {/* Follow-up List */}
      <div className="rounded-lg bg-white shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center p-12">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : data?.followups?.length === 0 ? (
          <div className="p-12 text-center">
            <ClipboardCheck className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-4 text-gray-500">No follow-ups found</p>
          </div>
        ) : (
          <div className="divide-y">
            {data?.followups?.map((followup: any) => (
              <FollowupRow
                key={followup.id}
                followup={followup}
                onComplete={() => completeMutation.mutate(followup.id)}
                onCancel={() => cancelMutation.mutate(followup.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function FollowupRow({
  followup,
  onComplete,
  onCancel,
}: {
  followup: any
  onComplete: () => void
  onCancel: () => void
}) {
  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    reminded: 'bg-orange-100 text-orange-700',
    escalated: 'bg-red-100 text-red-700',
    completed: 'bg-green-100 text-green-700',
    cancelled: 'bg-gray-100 text-gray-700',
  }

  const priorityColors: Record<string, string> = {
    urgent: 'border-l-red-500',
    high: 'border-l-orange-500',
    normal: 'border-l-blue-500',
    low: 'border-l-green-500',
  }

  const isActive = ['pending', 'reminded', 'escalated'].includes(followup.status)

  return (
    <div
      className={`flex items-center gap-4 border-l-4 p-4 ${
        priorityColors[followup.priority] || priorityColors.normal
      } ${followup.is_overdue ? 'bg-red-50' : ''}`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link
            href={`/followups/${followup.id}`}
            className="font-medium text-gray-900 hover:text-blue-600"
          >
            {followup.subject}
          </Link>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              statusColors[followup.status] || statusColors.pending
            }`}
          >
            {followup.status}
          </span>
          {followup.is_overdue && (
            <span className="flex items-center gap-1 text-xs text-red-600">
              <AlertTriangle className="h-3 w-3" />
              Overdue
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500">
          {followup.contact_name || followup.contact_email}
        </p>
        <p className="text-xs text-gray-400">
          Due: {formatDate(followup.due_date)}
          {followup.days_until_due !== null && followup.days_until_due >= 0 && (
            <span className="ml-2">({followup.days_until_due} days left)</span>
          )}
        </p>
      </div>
      {isActive && (
        <div className="flex gap-2">
          <button
            onClick={onComplete}
            className="flex items-center gap-1 rounded-lg bg-green-100 px-3 py-1 text-sm text-green-700 hover:bg-green-200"
          >
            <CheckCircle className="h-4 w-4" />
            Complete
          </button>
          <button
            onClick={onCancel}
            className="flex items-center gap-1 rounded-lg bg-gray-100 px-3 py-1 text-sm text-gray-700 hover:bg-gray-200"
          >
            <XCircle className="h-4 w-4" />
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}
