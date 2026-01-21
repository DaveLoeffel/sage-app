'use client'

import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { todosApi } from '@/lib/api'
import { formatDate, formatRelativeTime } from '@/lib/utils'
import {
  ListTodo,
  Plus,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Loader2,
  Check,
  Pause,
} from 'lucide-react'

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
  snoozed_until?: string
  is_overdue?: boolean
}

interface TodoListResponse {
  todos: Todo[]
  total: number
  pending_count: number
  overdue_count: number
  completed_count: number
}

export default function TodosPage() {
  const searchParams = useSearchParams()

  const [statusFilter, setStatusFilter] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [priorityFilter, setPriorityFilter] = useState<string>('')
  const [showOverdueOnly, setShowOverdueOnly] = useState(false)

  // Initialize filters from URL params
  useEffect(() => {
    const overdueParam = searchParams.get('overdue')
    const statusParam = searchParams.get('status')
    const categoryParam = searchParams.get('category')
    const priorityParam = searchParams.get('priority')

    if (overdueParam === 'true') {
      setShowOverdueOnly(true)
    }
    if (statusParam) {
      setStatusFilter(statusParam)
    }
    if (categoryParam) {
      setCategoryFilter(categoryParam)
    }
    if (priorityParam) {
      setPriorityFilter(priorityParam)
    }
  }, [searchParams])

  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['todos', { statusFilter, categoryFilter, priorityFilter, showOverdueOnly }],
    queryFn: () =>
      todosApi
        .list({
          status: statusFilter || undefined,
          category: categoryFilter || undefined,
          priority: priorityFilter || undefined,
          include_completed: statusFilter === 'completed',
        })
        .then((res) => res.data as TodoListResponse),
  })

  const completeMutation = useMutation({
    mutationFn: (id: number) => todosApi.complete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todos'] })
      queryClient.invalidateQueries({ queryKey: ['todos-grouped'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (id: number) => todosApi.cancel(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['todos'] })
      queryClient.invalidateQueries({ queryKey: ['todos-grouped'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard-summary'] })
    },
  })

  // Filter for overdue if needed
  const filteredTodos = showOverdueOnly
    ? data?.todos?.filter((t) => t.is_overdue)
    : data?.todos

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">To-Do List</h1>
          <p className="text-gray-500">Track tasks and action items</p>
        </div>
        <Link
          href="/todos/new"
          className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-white hover:bg-purple-700"
        >
          <Plus className="h-4 w-4" />
          New Todo
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
              <ListTodo className="h-8 w-8 text-purple-500" />
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
          className="rounded-lg border border-gray-300 px-4 py-2 focus:border-purple-500 focus:outline-none"
        >
          <option value="">Active Todos</option>
          <option value="pending">Pending</option>
          <option value="snoozed">Snoozed</option>
          <option value="completed">Completed</option>
          <option value="cancelled">Cancelled</option>
        </select>

        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-lg border border-gray-300 px-4 py-2 focus:border-purple-500 focus:outline-none"
        >
          <option value="">All Categories</option>
          <option value="self_reminder">Self Reminder</option>
          <option value="request_received">Request Received</option>
          <option value="commitment_made">Commitment Made</option>
          <option value="meeting_action">Meeting Action</option>
          <option value="manual">Manual</option>
        </select>

        <select
          value={priorityFilter}
          onChange={(e) => setPriorityFilter(e.target.value)}
          className="rounded-lg border border-gray-300 px-4 py-2 focus:border-purple-500 focus:outline-none"
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

      {/* Todo List */}
      <div className="rounded-lg bg-white shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center p-12">
            <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          </div>
        ) : filteredTodos?.length === 0 ? (
          <div className="p-12 text-center">
            <ListTodo className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-4 text-gray-500">No todos found</p>
          </div>
        ) : (
          <div className="divide-y">
            {filteredTodos?.map((todo) => (
              <TodoRow
                key={todo.id}
                todo={todo}
                onComplete={() => completeMutation.mutate(todo.id)}
                onCancel={() => cancelMutation.mutate(todo.id)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function TodoRow({
  todo,
  onComplete,
  onCancel,
}: {
  todo: Todo
  onComplete: () => void
  onCancel: () => void
}) {
  const statusColors: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-700',
    snoozed: 'bg-purple-100 text-purple-700',
    completed: 'bg-green-100 text-green-700',
    cancelled: 'bg-gray-100 text-gray-700',
  }

  const priorityColors: Record<string, string> = {
    urgent: 'border-l-red-500',
    high: 'border-l-orange-500',
    normal: 'border-l-purple-500',
    low: 'border-l-green-500',
  }

  const categoryLabels: Record<string, string> = {
    self_reminder: 'Self',
    request_received: 'Request',
    commitment_made: 'Commitment',
    meeting_action: 'Meeting',
    manual: 'Manual',
  }

  const categoryColors: Record<string, string> = {
    self_reminder: 'bg-purple-100 text-purple-700',
    request_received: 'bg-blue-100 text-blue-700',
    commitment_made: 'bg-green-100 text-green-700',
    meeting_action: 'bg-yellow-100 text-yellow-700',
    manual: 'bg-gray-100 text-gray-700',
  }

  const isActive = ['pending', 'snoozed'].includes(todo.status)
  const isOverdue = todo.is_overdue || (todo.due_date && new Date(todo.due_date) < new Date() && isActive)

  return (
    <div
      className={`flex items-center gap-4 border-l-4 p-4 ${
        priorityColors[todo.priority] || priorityColors.normal
      } ${isOverdue ? 'bg-red-50' : ''}`}
    >
      {/* Complete checkbox */}
      {isActive && (
        <button
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onComplete()
          }}
          className="flex-shrink-0 rounded-full border-2 border-gray-300 p-1 hover:border-green-500 hover:bg-green-50 transition-colors"
          title="Mark as complete"
        >
          <Check className="h-4 w-4 text-transparent hover:text-green-500" />
        </button>
      )}

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            href={`/todos/${todo.id}`}
            className="font-medium text-gray-900 hover:text-purple-600"
          >
            {todo.title}
          </Link>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              categoryColors[todo.category] || categoryColors.manual
            }`}
          >
            {categoryLabels[todo.category] || todo.category}
          </span>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              statusColors[todo.status] || statusColors.pending
            }`}
          >
            {todo.status}
          </span>
          {isOverdue && (
            <span className="flex items-center gap-1 text-xs text-red-600">
              <AlertTriangle className="h-3 w-3" />
              Overdue
            </span>
          )}
          {todo.snoozed_until && (
            <span className="flex items-center gap-1 text-xs text-purple-600">
              <Pause className="h-3 w-3" />
              Until {formatDate(todo.snoozed_until)}
            </span>
          )}
        </div>
        <p className="text-sm text-gray-500">
          {todo.contact_name || todo.contact_email || todo.source_summary || 'No source'}
        </p>
        {todo.due_date && (
          <p className="text-xs text-gray-400">
            Due: {formatDate(todo.due_date)}
          </p>
        )}
      </div>
      {isActive && (
        <div className="flex gap-2">
          <Link
            href={`/todos/${todo.id}`}
            className="flex items-center gap-1 rounded-lg bg-purple-100 px-3 py-1 text-sm text-purple-700 hover:bg-purple-200"
          >
            View
          </Link>
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
