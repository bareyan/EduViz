import React from 'react'

interface FeatureCardProps {
  icon: React.ReactNode
  title: string
  description: string
  color: 'blue' | 'purple' | 'green'
}

export function FeatureCard({ icon, title, description, color }: FeatureCardProps) {
  const colors = {
    blue: 'text-math-blue bg-math-blue/10',
    purple: 'text-math-purple bg-math-purple/10',
    green: 'text-math-green bg-math-green/10',
  }

  return (
    <div className="p-6 rounded-xl bg-gray-900/50 border border-gray-800 card-hover">
      <div className={`w-14 h-14 rounded-lg flex items-center justify-center mb-4 ${colors[color]}`}>
        {icon}
      </div>
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-gray-400">{description}</p>
    </div>
  )
}
