'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { briefingsApi, emailsApi } from '@/lib/api'
import {
  Sunrise,
  RefreshCw,
  Search,
  FileText,
  MessageSquare,
  Loader2,
} from 'lucide-react'
import Link from 'next/link'

export function QuickActions() {
  const [syncStatus, setSyncStatus] = useState<'idle' | 'syncing' | 'done'>('idle')

  const syncMutation = useMutation({
    mutationFn: () => emailsApi.sync().then((res) => res.data),
    onMutate: () => setSyncStatus('syncing'),
    onSuccess: () => {
      setSyncStatus('done')
      setTimeout(() => setSyncStatus('idle'), 2000)
    },
    onError: () => setSyncStatus('idle'),
  })

  const briefingMutation = useMutation({
    mutationFn: () => briefingsApi.morning().then((res) => res.data),
  })

  return (
    <div className="rounded-lg bg-white shadow-sm">
      <div className="border-b px-6 py-4">
        <h2 className="text-lg font-semibold text-gray-900">Quick Actions</h2>
      </div>

      <div className="p-4 space-y-2">
        <ActionButton
          icon={Sunrise}
          label="Morning Briefing"
          description="Generate today's summary"
          onClick={() => briefingMutation.mutate()}
          loading={briefingMutation.isPending}
        />

        <ActionButton
          icon={RefreshCw}
          label="Sync Emails"
          description={
            syncStatus === 'done'
              ? 'Sync complete!'
              : syncStatus === 'syncing'
              ? 'Syncing...'
              : 'Fetch new emails'
          }
          onClick={() => syncMutation.mutate()}
          loading={syncStatus === 'syncing'}
        />

        <Link href="/chat">
          <ActionButton
            icon={MessageSquare}
            label="Ask Sage"
            description="Chat with your AI assistant"
          />
        </Link>

        <Link href="/emails?search=true">
          <ActionButton
            icon={Search}
            label="Search Emails"
            description="Find specific emails"
          />
        </Link>

        <Link href="/followups/new">
          <ActionButton
            icon={FileText}
            label="Create Follow-up"
            description="Track a new item"
          />
        </Link>
      </div>
    </div>
  )
}

function ActionButton({
  icon: Icon,
  label,
  description,
  onClick,
  loading = false,
}: {
  icon: React.ElementType
  label: string
  description: string
  onClick?: () => void
  loading?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="flex w-full items-center gap-3 rounded-lg border border-gray-200 p-3 text-left transition-colors hover:bg-gray-50 disabled:opacity-50"
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gray-100">
        {loading ? (
          <Loader2 className="h-5 w-5 animate-spin text-gray-600" />
        ) : (
          <Icon className="h-5 w-5 text-gray-600" />
        )}
      </div>
      <div>
        <p className="font-medium text-gray-900">{label}</p>
        <p className="text-sm text-gray-500">{description}</p>
      </div>
    </button>
  )
}
