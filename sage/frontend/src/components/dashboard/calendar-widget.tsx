'use client'

import Link from 'next/link'
import { Calendar, Clock, Video, MapPin, ChevronRight } from 'lucide-react'
import { formatTime } from '@/lib/utils'

interface CalendarEvent {
  id: string
  title: string
  start: string
  end: string
  location?: string
  meeting_link?: string
  attendees?: string[]
}

interface CalendarWidgetProps {
  events: CalendarEvent[]
}

export function CalendarWidget({ events }: CalendarWidgetProps) {
  return (
    <div className="rounded-lg bg-white shadow-sm">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <h2 className="text-lg font-semibold text-gray-900">Today&apos;s Schedule</h2>
        <Link
          href="/calendar"
          className="flex items-center text-sm text-blue-600 hover:text-blue-700"
        >
          View all
          <ChevronRight className="ml-1 h-4 w-4" />
        </Link>
      </div>

      <div className="divide-y">
        {events.length > 0 ? (
          events.map((event) => (
            <EventItem key={event.id} event={event} />
          ))
        ) : (
          <div className="p-8 text-center">
            <Calendar className="mx-auto h-8 w-8 text-gray-400" />
            <p className="mt-2 text-gray-500">No events today</p>
          </div>
        )}
      </div>
    </div>
  )
}

function EventItem({ event }: { event: CalendarEvent }) {
  return (
    <div className="p-4">
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
            <Calendar className="h-5 w-5 text-blue-600" />
          </div>
        </div>
        <div className="flex-1">
          <p className="font-medium text-gray-900">{event.title}</p>
          <div className="mt-1 flex items-center gap-3 text-sm text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatTime(event.start)} - {formatTime(event.end)}
            </span>
          </div>
          {event.location && (
            <div className="mt-1 flex items-center gap-1 text-sm text-gray-500">
              <MapPin className="h-3 w-3" />
              {event.location}
            </div>
          )}
          {event.meeting_link && (
            <a
              href={event.meeting_link}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
            >
              <Video className="h-3 w-3" />
              Join meeting
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
