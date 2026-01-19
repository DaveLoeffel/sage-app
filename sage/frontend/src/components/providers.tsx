'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState, Suspense } from 'react'
import { AuthProvider } from '@/lib/auth'

function LoadingFallback() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-lg text-gray-500">Loading...</div>
    </div>
  )
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<LoadingFallback />}>
        <AuthProvider>
          {children}
        </AuthProvider>
      </Suspense>
    </QueryClientProvider>
  )
}
