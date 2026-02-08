import React from 'react'

interface StatCardProps {
  icon: React.ReactNode
  label: string
  value: string
}

export function StatCard({ icon, label, value }: StatCardProps) {
  return (
    <div className="p-4 bg-gray-900/50 rounded-xl border border-gray-800 text-center">
      <div className="flex justify-center text-math-blue mb-2">{icon}</div>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  )
}
