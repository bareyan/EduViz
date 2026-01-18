import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { Upload, FileText, Image, Loader2, Sparkles, Play, BookOpen, Wand2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { uploadFile } from '../api'

export default function HomePage() {
  const navigate = useNavigate()
  const [isUploading, setIsUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return

    const file = acceptedFiles[0]
    setIsUploading(true)
    setUploadProgress(0)

    try {
      // Simulate upload progress
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90))
      }, 200)

      const result = await uploadFile(file)
      
      clearInterval(progressInterval)
      setUploadProgress(100)
      
      toast.success('File uploaded successfully!')
      navigate(`/analysis/${result.file_id}`)
    } catch (error) {
      console.error('Upload failed:', error)
      toast.error('Failed to upload file. Please try again.')
    } finally {
      setIsUploading(false)
      setUploadProgress(0)
    }
  }, [navigate])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/webp': ['.webp'],
      'text/plain': ['.txt'],
      'application/x-tex': ['.tex'],
      'text/x-tex': ['.tex'],
    },
    maxFiles: 1,
    disabled: isUploading,
  })

  return (
    <div className="space-y-16">
      {/* Hero Section */}
      <section className="text-center py-12">
        <div className="relative inline-block">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Transform Math into
            <span className="block gradient-text">Visual Magic</span>
          </h1>
          <Sparkles className="absolute -top-4 -right-8 w-8 h-8 text-yellow-400 animate-pulse" />
        </div>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-8">
          Upload your math materials — PDFs, LaTeX, images, or text files — and watch them transform into 
          beautiful 3Blue1Brown-style animated videos with AI narration.
        </p>

        {/* Upload Zone */}
        <div
          {...getRootProps()}
          className={`
            relative max-w-2xl mx-auto p-12 border-2 border-dashed rounded-2xl cursor-pointer
            transition-all duration-300 card-hover
            ${isDragActive 
              ? 'border-math-blue bg-math-blue/10' 
              : 'border-gray-700 hover:border-math-blue/50 bg-gray-900/50'
            }
            ${isUploading ? 'pointer-events-none opacity-70' : ''}
          `}
        >
          <input {...getInputProps()} />
          
          {isUploading ? (
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="w-16 h-16 text-math-blue animate-spin" />
              <div className="w-full max-w-xs bg-gray-800 rounded-full h-2">
                <div 
                  className="bg-math-blue h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-gray-400">Uploading your file...</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-4">
              <div className="relative">
                <Upload className="w-16 h-16 text-gray-500" />
                <div className="absolute inset-0 bg-math-blue/20 blur-xl" />
              </div>
              <div>
                <p className="text-lg font-medium text-white">
                  {isDragActive ? 'Drop your file here' : 'Drag & drop your file here'}
                </p>
                <p className="text-gray-500 mt-1">or click to browse</p>
              </div>
              <div className="flex gap-4 mt-4">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <FileText className="w-4 h-4" />
                  <span>PDF, LaTeX, TXT</span>
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Image className="w-4 h-4" />
                  <span>PNG, JPG, WebP</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Features Section */}
      <section className="grid md:grid-cols-3 gap-8">
        <FeatureCard
          icon={<BookOpen className="w-8 h-8" />}
          title="Smart Analysis"
          description="AI-powered content analysis detects equations, theorems, and key concepts from your materials."
          color="blue"
        />
        <FeatureCard
          icon={<Wand2 className="w-8 h-8" />}
          title="Manim Animations"
          description="Beautiful 3Blue1Brown-style animations generated automatically for each concept."
          color="purple"
        />
        <FeatureCard
          icon={<Play className="w-8 h-8" />}
          title="Voice Narration"
          description="Natural-sounding AI voices explain concepts clearly, synced with animations."
          color="green"
        />
      </section>

      {/* How It Works */}
      <section className="py-12">
        <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>
        <div className="grid md:grid-cols-4 gap-6">
          <Step number={1} title="Upload" description="Drop your PDF or images with math content" />
          <Step number={2} title="Analyze" description="AI analyzes and suggests video topics" />
          <Step number={3} title="Customize" description="Choose topics, style, and voice preferences" />
          <Step number={4} title="Generate" description="Get beautiful animated videos with narration" />
        </div>
      </section>
    </div>
  )
}

function FeatureCard({ 
  icon, 
  title, 
  description, 
  color 
}: { 
  icon: React.ReactNode
  title: string
  description: string
  color: 'blue' | 'purple' | 'green'
}) {
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

function Step({ number, title, description }: { number: number; title: string; description: string }) {
  return (
    <div className="relative">
      <div className="flex items-center gap-4 mb-3">
        <div className="w-10 h-10 rounded-full bg-math-blue/20 flex items-center justify-center text-math-blue font-bold">
          {number}
        </div>
        {number < 4 && (
          <div className="hidden md:block flex-1 h-0.5 bg-gradient-to-r from-math-blue/50 to-transparent" />
        )}
      </div>
      <h3 className="font-semibold mb-1">{title}</h3>
      <p className="text-sm text-gray-500">{description}</p>
    </div>
  )
}
