'use client'

import Link from 'next/link'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { todosApi } from '@/lib/api'
import { AlertTriangle, Clock, CheckCircle2, ChevronRight, ListTodo, Check } from 'lucide-react'
import { formatRelativeTime } from '@/lib/utils'

interface Todo {
  id: number
  title: string
  description?: string
  category: string
  priority: string
  status: string
  due_date?: string
  source_type: string
  source_summary?: string
  contact_name?: string
  contact_email?: string
  detection_confidence?: number
}

interface GroupedTodos {
  due_today: Todo[]
  due_this_week: Todo[]
  overdue: Todo[]
  no_deadline: Todo[]
  completed_recently: Todo[]
  total_pending: number
  total_overdue: number
}

export function TodoWidget() {
  const queryClient = useQueryClient()

  const { data: grouped, isLoading } = useQuery({
    queryKey: ['todos-grouped'],
    queryFn: () => todosApi.grouped().then((res) => res.data as GroupedTodos),
    refetchInterval: 60000,
  })

  const completeMutation = useMutation({
    mutationFn: (id: number) => todosApi.complete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todos-grouped'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })

  if (isLoading) {
    return (
      <div className="rounded-lg bg-white shadow-sm p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 rounded w-1/3"></div>
          <div className="h-20 bg-gray-100 rounded"></div>
        </div>
      </div>
    )
  }

  const hasOverdue = (grouped?.overdue?.length || 0) > 0
  const hasDueToday = (grouped?.due_today?.length || 0) > 0
  const hasDueThisWeek = (grouped?.due_this_week?.length || 0) > 0
  const hasAnyTodos = hasOverdue || hasDueToday || hasDueThisWeek

  return (
    <div className="rounded-lg bg-white shadow-sm">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div className="flex items-center gap-2">
          <ListTodo className="h-5 w-5 text-purple-600" />
          <h2 className="text-lg font-semibold text-gray-900">To-Do List</h2>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-sm text-gray-500">
            {grouped?.total_pending || 0} pending
            {(grouped?.total_overdue || 0) > 0 && (
              <span className="text-red-600 ml-2">({grouped?.total_overdue} overdue)</span>
            )}
          </div>
          <a
            href="/todos"
            className="flex items-center text-sm text-blue-600 hover:text-blue-700"
          >
            View all
            <ChevronRight className="ml-1 h-4 w-4" />
          </a>
        </div>
      </div>

      <div className="divide-y">
        {/* Overdue Section */}
        {hasOverdue && (
          <div className="p-4">
            <div className="mb-3 flex items-center gap-2 text-red-600">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm font-medium">Overdue ({grouped?.overdue?.length})</span>
            </div>
            <div className="space-y-2">
              {grouped?.overdue?.slice(0, 3).map((todo) => (
                <TodoItem
                  key={todo.id}
                  todo={todo}
                  isOverdue
                  onComplete={() => completeMutation.mutate(todo.id)}
                />
              ))}
              {(grouped?.overdue?.length || 0) > 3 && (
                <p className="text-xs text-gray-400 pl-8">
                  +{(grouped?.overdue?.length || 0) - 3} more overdue items
                </p>
              )}
            </div>
          </div>
        )}

        {/* Due Today Section */}
        {hasDueToday && (
          <div className="p-4">
            <div className="mb-3 flex items-center gap-2 text-orange-600">
              <Clock className="h-4 w-4" />
              <span className="text-sm font-medium">Due Today ({grouped?.due_today?.length})</span>
            </div>
            <div className="space-y-2">
              {grouped?.due_today?.slice(0, 3).map((todo) => (
                <TodoItem
                  key={todo.id}
                  todo={todo}
                  onComplete={() => completeMutation.mutate(todo.id)}
                />
              ))}
              {(grouped?.due_today?.length || 0) > 3 && (
                <p className="text-xs text-gray-400 pl-8">
                  +{(grouped?.due_today?.length || 0) - 3} more items due today
                </p>
              )}
            </div>
          </div>
        )}

        {/* Due This Week Section */}
        {hasDueThisWeek && (
          <div className="p-4">
            <div className="mb-3 flex items-center gap-2 text-yellow-600">
              <CheckCircle2 className="h-4 w-4" />
              <span className="text-sm font-medium">Due This Week ({grouped?.due_this_week?.length})</span>
            </div>
            <div className="space-y-2">
              {grouped?.due_this_week?.slice(0, 3).map((todo) => (
                <TodoItem
                  key={todo.id}
                  todo={todo}
                  onComplete={() => completeMutation.mutate(todo.id)}
                />
              ))}
              {(grouped?.due_this_week?.length || 0) > 3 && (
                <p className="text-xs text-gray-400 pl-8">
                  +{(grouped?.due_this_week?.length || 0) - 3} more items this week
                </p>
              )}
            </div>
          </div>
        )}

        {/* Empty State */}
        {!hasAnyTodos && (
          <div className="p-8 text-center">
            <CheckCircle2 className="mx-auto h-12 w-12 text-green-400" />
            <p className="mt-2 text-gray-500">All caught up! No pending todos.</p>
          </div>
        )}
      </div>
    </div>
  )
}

function TodoItem({
  todo,
  isOverdue = false,
  onComplete,
}: {
  todo: Todo
  isOverdue?: boolean
  onComplete: () => void
}) {
  const priorityColors = {
    urgent: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    normal: 'bg-gray-100 text-gray-700',
    low: 'bg-green-100 text-green-700',
  }

  const categoryLabels = {
    self_reminder: 'Self',
    request_received: 'Request',
    commitment_made: 'Commitment',
    meeting_action: 'Meeting',
    manual: 'Manual',
  }

  const categoryColors = {
    self_reminder: 'bg-purple-100 text-purple-700',
    request_received: 'bg-blue-100 text-blue-700',
    commitment_made: 'bg-green-100 text-green-700',
    meeting_action: 'bg-yellow-100 text-yellow-700',
    manual: 'bg-gray-100 text-gray-700',
  }

  return (
    <div
      className={`flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-gray-50 ${
        isOverdue ? 'border-red-200 bg-red-50' : ''
      }`}
    >
      <button
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onComplete()
        }}
        className="mt-0.5 flex-shrink-0 rounded-full border-2 border-gray-300 p-1 hover:border-green-500 hover:bg-green-50 transition-colors z-10"
        title="Mark as complete"
      >
        <Check className="h-3 w-3 text-transparent hover:text-green-500" />
      </button>

      <Link href={`/todos/${todo.id}`} className="flex-1 min-w-0">
        <p className="truncate font-medium text-gray-900 hover:text-blue-600">{todo.title}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              categoryColors[todo.category as keyof typeof categoryColors] || categoryColors.manual
            }`}
          >
            {categoryLabels[todo.category as keyof typeof categoryLabels] || todo.category}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              priorityColors[todo.priority as keyof typeof priorityColors] || priorityColors.normal
            }`}
          >
            {todo.priority}
          </span>
          {todo.source_summary && (
            <span className="text-xs text-gray-400 truncate max-w-[150px]">
              {todo.source_summary}
            </span>
          )}
        </div>
        {todo.due_date && (
          <div className="mt-1 text-xs text-gray-400">
            Due {formatRelativeTime(todo.due_date)}
          </div>
        )}
      </Link>
    </div>
  )
}
