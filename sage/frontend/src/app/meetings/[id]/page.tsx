'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { meetingsApi } from '@/lib/api'
import { formatDate, formatTime } from '@/lib/utils'
import {
  ArrowLeft,
  Video,
  Clock,
  Users,
  FileText,
  CheckSquare,
  Tag,
  Loader2,
  Save,
  AlertCircle,
} from 'lucide-react'

interface TranscriptEntry {
  speaker: string
  text: string
  timestamp: number | null
}

interface MeetingDetail {
  id: string
  title: string
  date: string | null
  duration_minutes: number | null
  participants: string[]
  summary: string | null
  key_points: string[]
  action_items: string[]
  keywords: string[]
  transcript: TranscriptEntry[]
}

export default function MeetingDetailPage() {
  const params = useParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const meetingId = params.id as string

  // Fetch meeting details
  const { data: meeting, isLoading, error } = useQuery({
    queryKey: ['meeting', meetingId],
    queryFn: () => meetingsApi.get(meetingId).then((res) => res.data as MeetingDetail),
  })

  // Cache mutation
  const cacheMutation = useMutation({
    mutationFn: () => meetingsApi.cache(meetingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['meeting', meetingId] })
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error || !meeting) {
    return (
      <div className="p-6">
        <button
          onClick={() => router.back()}
          className="mb-6 flex items-center gap-2 text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Meetings
        </button>
        <div className="rounded-lg bg-red-50 p-6">
          <div className="flex items-start gap-4">
            <AlertCircle className="h-6 w-6 text-red-500 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-red-800">Meeting Not Found</h3>
              <p className="mt-1 text-sm text-red-700">
                The meeting you're looking for could not be found.
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6">
      {/* Back button */}
      <button
        onClick={() => router.back()}
        className="mb-6 flex items-center gap-2 text-gray-600 hover:text-gray-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Meetings
      </button>

      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-sage-100">
            <Video className="h-6 w-6 text-sage-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{meeting.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-gray-500">
              {meeting.date && (
                <span className="flex items-center gap-1">
                  <Clock className="h-4 w-4" />
                  {formatDate(meeting.date)} at {formatTime(meeting.date)}
                </span>
              )}
              {meeting.duration_minutes && (
                <span>{meeting.duration_minutes} minutes</span>
              )}
              {meeting.participants.length > 0 && (
                <span className="flex items-center gap-1">
                  <Users className="h-4 w-4" />
                  {meeting.participants.length} participants
                </span>
              )}
            </div>
          </div>
        </div>
        <button
          onClick={() => cacheMutation.mutate()}
          disabled={cacheMutation.isPending}
          className="flex items-center gap-2 rounded-lg border border-gray-300 px-4 py-2 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
        >
          {cacheMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save to Cache
        </button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main content - 2 columns */}
        <div className="space-y-6 lg:col-span-2">
          {/* Summary */}
          {meeting.summary && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <FileText className="h-5 w-5 text-sage-600" />
                Summary
              </h2>
              <p className="text-gray-700 whitespace-pre-wrap">{meeting.summary}</p>
            </div>
          )}

          {/* Key Points */}
          {meeting.key_points && meeting.key_points.length > 0 && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Key Points</h2>
              <ul className="space-y-2">
                {meeting.key_points.map((point, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-sage-500" />
                    <span className="text-gray-700">{point}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Transcript */}
          {meeting.transcript && meeting.transcript.length > 0 && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Transcript</h2>
              <div className="max-h-[500px] space-y-4 overflow-y-auto">
                {meeting.transcript.map((entry, index) => (
                  <div key={index} className="border-l-2 border-gray-200 pl-4">
                    <p className="text-sm font-medium text-sage-700">{entry.speaker}</p>
                    <p className="text-gray-700">{entry.text}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar - 1 column */}
        <div className="space-y-6">
          {/* Action Items */}
          {meeting.action_items && meeting.action_items.length > 0 && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <CheckSquare className="h-5 w-5 text-sage-600" />
                Action Items
              </h2>
              <ul className="space-y-2">
                {meeting.action_items.map((item, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <input type="checkbox" className="mt-1 rounded border-gray-300" />
                    <span className="text-gray-700">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Participants */}
          {meeting.participants.length > 0 && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <Users className="h-5 w-5 text-sage-600" />
                Participants
              </h2>
              <ul className="space-y-2">
                {meeting.participants.map((participant, index) => (
                  <li key={index} className="text-gray-700">
                    {participant}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Keywords */}
          {meeting.keywords && meeting.keywords.length > 0 && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <Tag className="h-5 w-5 text-sage-600" />
                Keywords
              </h2>
              <div className="flex flex-wrap gap-2">
                {meeting.keywords.map((keyword, index) => (
                  <span
                    key={index}
                    className="rounded-full bg-sage-100 px-3 py-1 text-sm text-sage-700"
                  >
                    {keyword}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
