'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { meetingsApi } from '@/lib/api'
import { formatDate } from '@/lib/utils'
import {
  Video,
  Search,
  RefreshCw,
  Loader2,
  Users,
  Clock,
  ChevronRight,
  Mic,
} from 'lucide-react'
import Link from 'next/link'
import { cn } from '@/lib/utils'

type SourceFilter = 'all' | 'fireflies' | 'plaud'

interface UnifiedMeeting {
  id: string
  source: 'fireflies' | 'plaud'
  title: string
  date: string | null
  duration_minutes: number | null
  participants: string[]
  sender: string | null
  summary_preview: string | null
}

interface SyncResponse {
  fireflies_synced: number
  fireflies_new: number
  fireflies_updated: number
  plaud_synced: number
  fireflies_error: string | null
  plaud_error: string | null
}

export default function MeetingsPage() {
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>('all')
  const [search, setSearch] = useState('')
  const queryClient = useQueryClient()

  // Fetch unified meetings
  const { data: meetings, isLoading } = useQuery({
    queryKey: ['meetings', 'unified', sourceFilter, search],
    queryFn: () =>
      meetingsApi
        .unifiedList({ limit: 30, source: sourceFilter, search: search || undefined })
        .then((res) => res.data as UnifiedMeeting[]),
  })

  // Unified sync mutation
  const syncMutation = useMutation({
    mutationFn: () => meetingsApi.unifiedSync(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meetings', 'unified'] })
    },
  })

  const syncData = syncMutation.data?.data as SyncResponse | undefined

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Meetings</h1>
          <p className="text-gray-500">Meeting transcripts and recordings</p>
        </div>
        <button
          onClick={() => syncMutation.mutate()}
          disabled={syncMutation.isPending}
          className="flex items-center gap-2 rounded-lg bg-sage-600 px-4 py-2 text-white hover:bg-sage-700 disabled:opacity-50"
        >
          {syncMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Sync All
        </button>
      </div>

      {/* Filter Chips */}
      <div className="mb-6 flex items-center gap-2">
        <FilterChip
          label="All Sources"
          active={sourceFilter === 'all'}
          onClick={() => setSourceFilter('all')}
        />
        <FilterChip
          label="Fireflies"
          icon={<Video className="h-3.5 w-3.5" />}
          active={sourceFilter === 'fireflies'}
          onClick={() => setSourceFilter('fireflies')}
        />
        <FilterChip
          label="Plaud"
          icon={<Mic className="h-3.5 w-3.5" />}
          active={sourceFilter === 'plaud'}
          onClick={() => setSourceFilter('plaud')}
        />
      </div>

      {/* Search */}
      <div className="mb-6">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search meetings..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-lg border border-gray-300 pl-10 pr-4 py-2 focus:border-sage-500 focus:outline-none"
          />
        </div>
      </div>

      {/* Sync result message */}
      {syncMutation.isSuccess && syncData && (
        <div className="mb-6 rounded-lg bg-green-50 p-4 text-sm text-green-700">
          <div>
            Synced {syncData.fireflies_synced} Fireflies meetings (
            {syncData.fireflies_new} new, {syncData.fireflies_updated} updated) and{' '}
            {syncData.plaud_synced} Plaud recordings
          </div>
          {(syncData.fireflies_error || syncData.plaud_error) && (
            <div className="mt-2 text-yellow-700">
              {syncData.fireflies_error && <div>Fireflies: {syncData.fireflies_error}</div>}
              {syncData.plaud_error && <div>Plaud: {syncData.plaud_error}</div>}
            </div>
          )}
        </div>
      )}

      {/* Meetings List */}
      <div className="rounded-lg bg-white shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center p-12">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : !meetings || meetings.length === 0 ? (
          <div className="p-12 text-center">
            <Video className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-4 text-gray-500">No meetings found</p>
            <p className="mt-2 text-sm text-gray-400">
              {search
                ? 'Try a different search term'
                : 'Click "Sync All" to fetch your recent meetings'}
            </p>
          </div>
        ) : (
          <div className="divide-y">
            {meetings.map((meeting) => (
              <UnifiedMeetingRow key={meeting.id} meeting={meeting} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function FilterChip({
  label,
  icon,
  active,
  onClick,
}: {
  label: string
  icon?: React.ReactNode
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
        active
          ? 'bg-sage-100 text-sage-700 ring-1 ring-sage-300'
          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
      )}
    >
      {icon}
      {label}
    </button>
  )
}

function UnifiedMeetingRow({ meeting }: { meeting: UnifiedMeeting }) {
  // Determine the correct link based on source
  const href =
    meeting.source === 'fireflies'
      ? `/meetings/${meeting.id}`
      : `/meetings/plaud/${meeting.id.replace('plaud_', '')}`

  const isFireflies = meeting.source === 'fireflies'

  return (
    <Link href={href} className="flex items-center gap-4 p-4 hover:bg-gray-50">
      <div className="flex-shrink-0">
        <div
          className={cn(
            'flex h-10 w-10 items-center justify-center rounded-full',
            isFireflies ? 'bg-sage-100' : 'bg-purple-100'
          )}
        >
          {isFireflies ? (
            <Video className="h-5 w-5 text-sage-600" />
          ) : (
            <Mic className="h-5 w-5 text-purple-600" />
          )}
        </div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <p className="font-medium text-gray-900">{meeting.title}</p>
          <span
            className={cn(
              'rounded px-1.5 py-0.5 text-xs font-medium',
              isFireflies ? 'bg-sage-100 text-sage-700' : 'bg-purple-100 text-purple-700'
            )}
          >
            {isFireflies ? 'Fireflies' : 'Plaud'}
          </span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-4 text-sm text-gray-500">
          {meeting.date && (
            <span className="flex items-center gap-1">
              <Clock className="h-4 w-4" />
              {formatDate(meeting.date)}
            </span>
          )}
          {isFireflies && meeting.duration_minutes && (
            <span>{meeting.duration_minutes} min</span>
          )}
          {isFireflies && meeting.participants.length > 0 && (
            <span className="flex items-center gap-1">
              <Users className="h-4 w-4" />
              {meeting.participants.length} participants
            </span>
          )}
          {!isFireflies && meeting.sender && <span>From: {meeting.sender}</span>}
        </div>
        {meeting.summary_preview && (
          <p className="mt-1 truncate text-sm text-gray-500">{meeting.summary_preview}</p>
        )}
      </div>
      <ChevronRight className="h-5 w-5 flex-shrink-0 text-gray-400" />
    </Link>
  )
}
