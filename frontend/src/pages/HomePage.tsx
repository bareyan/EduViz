import { useCallback } from 'react'
import { Sparkles, Play, BookOpen, Wand2 } from 'lucide-react'
import { useFileUpload } from '../hooks/useFileUpload'
import { UploadZone } from '../features/home/components/UploadZone'
import { FeatureCard } from '../features/home/components/FeatureCard'
import { Step } from '../features/home/components/Step'

export default function HomePage() {
  const { upload, isUploading, uploadProgress } = useFileUpload()

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return
    upload(acceptedFiles[acceptedFiles.length - 1])
  }, [upload])

  return (
    <div className="space-y-16">
      {/* Hero Section */}
      <section className="text-center py-12">
        <div className="relative inline-block">
          <h1 className="text-5xl md:text-6xl font-bold mb-6">
            Transform Knowledge into
            <span className="block gradient-text">Visual Magic</span>
          </h1>
          <Sparkles className="absolute -top-4 -right-8 w-8 h-8 text-yellow-400 animate-pulse" />
        </div>
        <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-8">
          Upload your educational materials — PDFs, images, or text files — and watch them transform into 
          beautiful animated explainer videos with AI narration. Works for math, CS, physics, economics & more.
        </p>

        <UploadZone 
          onDrop={onDrop} 
          isUploading={isUploading} 
          uploadProgress={uploadProgress} 
        />
      </section>

      {/* Features Section */}
      <section className="grid md:grid-cols-3 gap-8">
        <FeatureCard
          icon={<BookOpen className="w-8 h-8" />}
          title="Smart Analysis"
          description="AI-powered content analysis detects concepts, diagrams, code, and key ideas from your materials."
          color="blue"
        />
        <FeatureCard
          icon={<Wand2 className="w-8 h-8" />}
          title="Animated Explanations"
          description="Beautiful Manim animations generated automatically for each concept - like 3Blue1Brown."
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
          <Step number={1} title="Upload" description="Drop your PDF or images with educational content" />
          <Step number={2} title="Analyze" description="AI analyzes and suggests video topics" />
          <Step number={3} title="Customize" description="Choose topics, style, and voice preferences" />
          <Step number={4} title="Generate" description="Get beautiful animated videos with narration" />
        </div>
      </section>
    </div>
  )
}
