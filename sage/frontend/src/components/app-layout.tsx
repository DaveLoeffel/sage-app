'use client'

import { usePathname } from 'next/navigation'
import { Sidebar } from '@/components/sidebar'
import { useAuth, AuthGuard } from '@/lib/auth'

export function AppLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const { isLoading } = useAuth()

  // Don't show sidebar on login page
  const isLoginPage = pathname === '/login'

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-sage-950">
        <div className="text-sage-300">Loading...</div>
      </div>
    )
  }

  if (isLoginPage) {
    return <>{children}</>
  }

  return (
    <AuthGuard>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-gray-50">
          {children}
        </main>
      </div>
    </AuthGuard>
  )
}
