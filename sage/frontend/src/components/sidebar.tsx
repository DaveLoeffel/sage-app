'use client'

import Image from 'next/image'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Mail,
  ClipboardCheck,
  Calendar,
  MessageSquare,
  Settings,
  LogOut,
  Video,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/auth'

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Emails', href: '/emails', icon: Mail },
  { name: 'Follow-ups', href: '/followups', icon: ClipboardCheck },
  { name: 'Calendar', href: '/calendar', icon: Calendar },
  { name: 'Meetings', href: '/meetings', icon: Video },
  { name: 'Chat', href: '/chat', icon: MessageSquare },
]

export function Sidebar() {
  const pathname = usePathname()
  const { user, logout } = useAuth()

  return (
    <div className="flex h-full w-64 flex-col bg-sage-950">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-4">
        <Image
          src="/logo.svg"
          alt="Sage Logo"
          width={40}
          height={40}
          className="rounded-lg"
        />
        <div>
          <h1 className="text-lg font-bold text-white">Sage</h1>
          <span className="text-xs text-sage-400">AI Assistant</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navigation.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-sage-800 text-white'
                  : 'text-sage-300 hover:bg-sage-900 hover:text-white'
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* User info and actions */}
      <div className="border-t border-sage-800 p-3">
        {/* User info */}
        {user && (
          <div className="mb-3 flex items-center gap-3 rounded-lg px-3 py-2">
            {user.picture ? (
              <Image
                src={user.picture}
                alt={user.name}
                width={32}
                height={32}
                className="rounded-full"
              />
            ) : (
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-sage-700 text-sm font-medium text-white">
                {user.name?.charAt(0) || user.email?.charAt(0)}
              </div>
            )}
            <div className="flex-1 overflow-hidden">
              <p className="truncate text-sm font-medium text-white">{user.name}</p>
              <p className="truncate text-xs text-sage-400">{user.email}</p>
            </div>
          </div>
        )}

        <Link
          href="/settings"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sage-300 hover:bg-sage-900 hover:text-white"
        >
          <Settings className="h-5 w-5" />
          Settings
        </Link>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sage-300 hover:bg-sage-900 hover:text-white"
        >
          <LogOut className="h-5 w-5" />
          Sign out
        </button>
      </div>
    </div>
  )
}
