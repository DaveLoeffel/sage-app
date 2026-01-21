'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { dashboardApi } from '@/lib/api'
import { FollowupWidget } from '@/components/dashboard/followup-widget'
import { TodoWidget } from '@/components/dashboard/todo-widget'
import { EmailWidget } from '@/components/dashboard/email-widget'
import { CalendarWidget } from '@/components/dashboard/calendar-widget'
import { QuickActions } from '@/components/dashboard/quick-actions'
import { AlertTriangle, Mail, CheckCircle, Clock, ListTodo } from 'lucide-react'

export default function DashboardPage() {
  const { data: summary, isLoading } = useQuery({
    queryKey: ['dashboard-summary'],
    queryFn: () => dashboardApi.summary().then((res) => res.data),
    refetchInterval: 60000, // Refresh every minute
  })

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      </div>
    )
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500">
          {new Date().toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })}
        </p>
      </div>

      {/* Stats Grid */}
      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          title="Overdue Follow-ups"
          value={summary?.followup_summary?.overdue || 0}
          icon={AlertTriangle}
          color="red"
          href="/followups?overdue=true"
        />
        <StatCard
          title="Overdue Todos"
          value={summary?.todo_summary?.overdue || 0}
          icon={ListTodo}
          color="red"
          href="/todos?overdue=true"
        />
        <StatCard
          title="Pending Todos"
          value={summary?.todo_summary?.total_pending || 0}
          icon={ListTodo}
          color="purple"
          href="/todos"
        />
        <StatCard
          title="Unread Emails"
          value={summary?.email_summary?.unread_count || 0}
          icon={Mail}
          color="blue"
          href="/emails"
        />
        <StatCard
          title="Completed Today"
          value={(summary?.followup_summary?.completed_today || 0) + (summary?.todo_summary?.completed_today || 0)}
          icon={CheckCircle}
          color="green"
          href="/todos?status=completed"
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column - Follow-ups & Todos */}
        <div className="lg:col-span-2 space-y-6">
          <FollowupWidget
            overdueFollowups={summary?.overdue_followups || []}
            upcomingFollowups={summary?.upcoming_followups || []}
          />
          <TodoWidget />
          <EmailWidget priorityEmails={summary?.priority_emails || []} />
        </div>

        {/* Right Column - Calendar & Actions */}
        <div className="space-y-6">
          <CalendarWidget events={summary?.todays_events || []} />
          <QuickActions />
        </div>
      </div>
    </div>
  )
}

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  href,
}: {
  title: string
  value: number
  icon: React.ElementType
  color: 'red' | 'yellow' | 'blue' | 'green' | 'purple'
  href: string
}) {
  const colors = {
    red: 'bg-red-50 text-red-600',
    yellow: 'bg-yellow-50 text-yellow-600',
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-green-50 text-green-600',
    purple: 'bg-purple-50 text-purple-600',
  }

  return (
    <Link
      href={href}
      className="rounded-lg bg-white p-6 shadow-sm hover:shadow-md hover:bg-gray-50 transition-all cursor-pointer"
    >
      <div className="flex items-center gap-4">
        <div className={`rounded-lg p-3 ${colors[color]}`}>
          <Icon className="h-6 w-6" />
        </div>
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
      </div>
    </Link>
  )
}
