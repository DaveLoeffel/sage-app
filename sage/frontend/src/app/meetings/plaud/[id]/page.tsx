'use client'

import { useParams, useRouter } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import { meetingsApi } from '@/lib/api'
import { formatDate, formatTime } from '@/lib/utils'
import {
  ArrowLeft,
  Mic,
  Clock,
  FileText,
  CheckSquare,
  Loader2,
  AlertCircle,
  User,
} from 'lucide-react'

interface PlaudRecordingDetail {
  id: number
  email_id: string
  title: string
  date: string
  sender: string
  summary: string | null
  body_text: string | null
  action_items: string | null
}

export default function PlaudRecordingDetailPage() {
  const params = useParams()
  const router = useRouter()
  const recordingId = parseInt(params.id as string, 10)

  // Fetch recording details
  const { data: recording, isLoading, error } = useQuery({
    queryKey: ['plaud', recordingId],
    queryFn: () => meetingsApi.plaudGet(recordingId).then((res) => res.data as PlaudRecordingDetail),
    enabled: !isNaN(recordingId),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error || !recording) {
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
              <h3 className="font-medium text-red-800">Recording Not Found</h3>
              <p className="mt-1 text-sm text-red-700">
                The Plaud recording you're looking for could not be found.
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Parse action items if they exist (assuming they're newline-separated)
  const actionItems = recording.action_items
    ? recording.action_items.split('\n').filter((item) => item.trim())
    : []

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
      <div className="mb-6 flex items-start gap-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-purple-100">
          <Mic className="h-6 w-6 text-purple-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{recording.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="h-4 w-4" />
              {formatDate(recording.date)} at {formatTime(recording.date)}
            </span>
            <span className="flex items-center gap-1">
              <User className="h-4 w-4" />
              {recording.sender}
            </span>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main content - 2 columns */}
        <div className="space-y-6 lg:col-span-2">
          {/* Summary */}
          {recording.summary && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <FileText className="h-5 w-5 text-purple-600" />
                Summary
              </h2>
              <p className="text-gray-700 whitespace-pre-wrap">{recording.summary}</p>
            </div>
          )}

          {/* Full Content */}
          {recording.body_text && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-lg font-semibold text-gray-900">Meeting Notes</h2>
              <div className="max-h-[600px] overflow-y-auto">
                <div className="prose prose-sm max-w-none text-gray-700 whitespace-pre-wrap">
                  {recording.body_text}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar - 1 column */}
        <div className="space-y-6">
          {/* Action Items */}
          {actionItems.length > 0 && (
            <div className="rounded-lg bg-white p-6 shadow-sm">
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
                <CheckSquare className="h-5 w-5 text-purple-600" />
                Action Items
              </h2>
              <ul className="space-y-2">
                {actionItems.map((item, index) => (
                  <li key={index} className="flex items-start gap-2">
                    <input type="checkbox" className="mt-1 rounded border-gray-300" />
                    <span className="text-gray-700">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recording Info */}
          <div className="rounded-lg bg-white p-6 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">Recording Info</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-gray-500">Source</dt>
                <dd className="font-medium text-gray-900">Plaud Recording</dd>
              </div>
              <div>
                <dt className="text-gray-500">Received</dt>
                <dd className="font-medium text-gray-900">
                  {formatDate(recording.date)} at {formatTime(recording.date)}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">From</dt>
                <dd className="font-medium text-gray-900">{recording.sender}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </div>
  )
}
