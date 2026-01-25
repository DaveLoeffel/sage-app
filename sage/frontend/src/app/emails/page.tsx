'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { emailsApi } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { Mail, Search, Filter, RefreshCw, AlertCircle, Loader2 } from 'lucide-react'
import Link from 'next/link'

export default function EmailsPage() {
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState<string>('')
  const [priority, setPriority] = useState<string>('')
  const [unreadOnly, setUnreadOnly] = useState(true)
  const [page, setPage] = useState(1)
  const [syncing, setSyncing] = useState(false)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['emails', { search, category, priority, unreadOnly, page }],
    queryFn: () =>
      emailsApi
        .list({
          page,
          page_size: 20,
          search: search || undefined,
          category: category || undefined,
          priority: priority || undefined,
          unread_only: unreadOnly,
        })
        .then((res) => res.data),
  })

  const handleSync = async () => {
    setSyncing(true)
    try {
      await emailsApi.sync()
      await refetch()
    } catch (error) {
      console.error('Failed to sync emails:', error)
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Emails</h1>
          <p className="text-gray-500">Manage your inbox with AI assistance</p>
        </div>
        <button
          onClick={handleSync}
          disabled={syncing}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {syncing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          {syncing ? 'Syncing...' : 'Sync'}
        </button>
      </div>

      {/* Filters */}
      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search emails..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-gray-300 pl-10 pr-4 py-2 focus:border-blue-500 focus:outline-none"
          />
        </div>

        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="rounded-lg border border-gray-300 px-4 py-2 focus:border-blue-500 focus:outline-none"
        >
          <option value="">All Categories</option>
          <option value="urgent">Urgent</option>
          <option value="action_required">Action Required</option>
          <option value="fyi">FYI</option>
          <option value="newsletter">Newsletter</option>
        </select>

        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
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
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            className="rounded border-gray-300"
          />
          <span className="text-sm text-gray-600">Unread only</span>
        </label>
      </div>

      {/* Email List */}
      <div className="rounded-lg bg-white shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center p-12">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : data?.emails?.length === 0 ? (
          <div className="p-12 text-center">
            <Mail className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-4 text-gray-500">No emails found</p>
          </div>
        ) : (
          <>
            <div className="divide-y">
              {data?.emails?.map((email: any) => (
                <EmailRow key={email.id} email={email} />
              ))}
            </div>

            {/* Pagination */}
            {data && data.total > 20 && (
              <div className="flex items-center justify-between border-t px-4 py-3">
                <p className="text-sm text-gray-500">
                  Showing {(page - 1) * 20 + 1} to {Math.min(page * 20, data.total)} of{' '}
                  {data.total}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="rounded-lg border px-3 py-1 text-sm disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage((p) => p + 1)}
                    disabled={!data.has_next}
                    className="rounded-lg border px-3 py-1 text-sm disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function EmailRow({ email }: { email: any }) {
  const priorityColors: Record<string, string> = {
    urgent: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    normal: 'bg-gray-100 text-gray-700',
    low: 'bg-green-100 text-green-700',
  }

  return (
    <Link
      href={`/emails/${email.id}`}
      className="flex items-center gap-4 p-4 hover:bg-gray-50"
    >
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
          {email.priority && (
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                priorityColors[email.priority] || priorityColors.normal
              }`}
            >
              {email.priority}
            </span>
          )}
        </div>
        <p className={`truncate ${email.is_unread ? 'font-medium text-gray-900' : 'text-gray-600'}`}>
          {email.subject}
        </p>
        {email.summary && (
          <p className="truncate text-sm text-gray-500">{email.summary}</p>
        )}
      </div>
      <div className="flex-shrink-0 text-sm text-gray-400">
        {formatRelativeTime(email.received_at)}
      </div>
    </Link>
  )
}
