import { Outlet, Link } from 'react-router-dom'
import { Sigma, Github, Grid } from 'lucide-react'

export default function Layout() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0f0f1a] via-[#1a1a2e] to-[#0f0f1a]">
      {/* Header */}
      <header className="border-b border-gray-800 bg-black/30 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link to="/" className="flex items-center gap-3 group">
              <div className="relative">
                <Sigma className="w-8 h-8 text-math-blue" />
                <div className="absolute inset-0 bg-math-blue/30 blur-lg group-hover:bg-math-purple/30 transition-colors" />
              </div>
              <span className="text-xl font-bold gradient-text">MathViz</span>
            </Link>
            
            <nav className="flex items-center gap-6">
              <Link 
                to="/" 
                className="text-gray-400 hover:text-white transition-colors"
              >
                Home
              </Link>
              <Link 
                to="/gallery" 
                className="text-gray-400 hover:text-white transition-colors flex items-center gap-2"
              >
                <Grid className="w-4 h-4" />
                Gallery
              </Link>
              <a 
                href="https://github.com" 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-white transition-colors"
              >
                <Github className="w-5 h-5" />
              </a>
            </nav>
          </div>
        </div>
      </header>
      
      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
      
      {/* Footer */}
      <footer className="border-t border-gray-800 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-gray-500 text-sm">
            MathViz - Transform your math materials into 3Blue1Brown-style videos
          </p>
        </div>
      </footer>
    </div>
  )
}
