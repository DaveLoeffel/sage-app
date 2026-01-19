'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { calendarApi } from '@/lib/api'
import { formatTime, formatDate } from '@/lib/utils'
import { Calendar, Clock, Video, MapPin, Users, Loader2, ChevronDown } from 'lucide-react'

interface CalendarEvent {
  id: string
  title: string
  start: string
  end: string
  location: string | null
  attendees: string[] | null
  description: string | null
  meeting_link: string | null
}

export default function CalendarPage() {
  const [daysToShow, setDaysToShow] = useState(7)

  // Calculate date range based on daysToShow
  const startDate = new Date()
  startDate.setHours(0, 0, 0, 0)
  const endDate = new Date(startDate)
  endDate.setDate(endDate.getDate() + daysToShow)

  const { data: events, isLoading } = useQuery({
    queryKey: ['calendar-events', daysToShow],
    queryFn: () =>
      calendarApi
        .events({
          start_date: startDate.toISOString(),
          end_date: endDate.toISOString(),
          max_results: 100,
        })
        .then((res) => res.data as CalendarEvent[]),
  })

  // Group events by date
  const eventsByDate = groupEventsByDate(events || [], daysToShow)

  const loadMore = () => {
    setDaysToShow((prev) => prev + 7)
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Calendar</h1>
        <p className="text-gray-500">Your upcoming schedule</p>
      </div>

      {/* Agenda View */}
      <div className="rounded-lg bg-white shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : eventsByDate.length === 0 ? (
          <div className="py-16 text-center">
            <Calendar className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-4 text-gray-500">No events scheduled</p>
            <p className="mt-1 text-sm text-gray-400">
              Your upcoming events will appear here
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {eventsByDate.map(({ date, dateLabel, isToday, events: dayEvents }) => (
              <div key={date} className="p-4">
                {/* Date Header */}
                <div className="mb-3 flex items-center gap-3">
                  <div
                    className={`flex h-12 w-12 flex-col items-center justify-center rounded-lg ${
                      isToday ? 'bg-sage-600 text-white' : 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    <span className="text-xs font-medium uppercase">
                      {new Date(date).toLocaleDateString('en-US', { weekday: 'short' })}
                    </span>
                    <span className="text-lg font-bold">
                      {new Date(date).getDate()}
                    </span>
                  </div>
                  <div>
                    <p className={`font-medium ${isToday ? 'text-sage-600' : 'text-gray-900'}`}>
                      {dateLabel}
                    </p>
                    <p className="text-sm text-gray-500">
                      {dayEvents.length} {dayEvents.length === 1 ? 'event' : 'events'}
                    </p>
                  </div>
                </div>

                {/* Events for this date */}
                <div className="ml-15 space-y-3 pl-[60px]">
                  {dayEvents.length === 0 ? (
                    <p className="py-2 text-sm text-gray-400 italic">No events</p>
                  ) : (
                    dayEvents.map((event) => (
                      <EventCard key={event.id} event={event} />
                    ))
                  )}
                </div>
              </div>
            ))}

            {/* Load More Button */}
            <div className="p-4">
              <button
                onClick={loadMore}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-200 py-3 text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              >
                <ChevronDown className="h-4 w-4" />
                Load 7 more days
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function groupEventsByDate(events: CalendarEvent[], daysToShow: number) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const result: {
    date: string
    dateLabel: string
    isToday: boolean
    events: CalendarEvent[]
  }[] = []

  // Create entries for each day in the range
  for (let i = 0; i < daysToShow; i++) {
    const date = new Date(today)
    date.setDate(date.getDate() + i)
    const dateStr = date.toISOString().split('T')[0]

    let dateLabel: string
    if (i === 0) {
      dateLabel = 'Today'
    } else if (i === 1) {
      dateLabel = 'Tomorrow'
    } else {
      dateLabel = date.toLocaleDateString('en-US', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
      })
    }

    result.push({
      date: dateStr,
      dateLabel,
      isToday: i === 0,
      events: [],
    })
  }

  // Assign events to their respective dates
  for (const event of events) {
    const eventDate = new Date(event.start)
    const eventDateStr = eventDate.toISOString().split('T')[0]

    const dayEntry = result.find((d) => d.date === eventDateStr)
    if (dayEntry) {
      dayEntry.events.push(event)
    }
  }

  // Sort events within each day by start time
  for (const day of result) {
    day.events.sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime())
  }

  return result
}

function EventCard({ event }: { event: CalendarEvent }) {
  const startTime = formatTime(event.start)
  const endTime = formatTime(event.end)

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 transition-shadow hover:shadow-md">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-blue-50">
          <Calendar className="h-5 w-5 text-blue-600" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900">{event.title}</h3>
          <div className="mt-1 space-y-1 text-sm text-gray-500">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 flex-shrink-0" />
              <span>
                {startTime} - {endTime}
              </span>
            </div>
            {event.location && (
              <div className="flex items-center gap-2">
                <MapPin className="h-4 w-4 flex-shrink-0" />
                <span className="truncate">{event.location}</span>
              </div>
            )}
            {event.attendees && event.attendees.length > 0 && (
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 flex-shrink-0" />
                <span>{event.attendees.length} attendees</span>
              </div>
            )}
          </div>
          {event.meeting_link && (
            <a
              href={event.meeting_link}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700"
            >
              <Video className="h-4 w-4" />
              Join meeting
            </a>
          )}
        </div>
      </div>
    </div>
  )
}
