import { useNavigate } from 'react-router-dom'
import { 
  Loader2, 
  Palette, 
  ChevronRight, 
  ArrowLeft, 
  BookOpen, 
  GraduationCap, 
  FileText, 
  Link2, 
  Layers, 
  RotateCcw, 
  Globe, 
  Zap 
} from 'lucide-react'
import { useVoices } from '../hooks/useVoices'
import { storageService } from '../services/storage.service'
import { useGenerationForm } from '../features/generation/hooks/useGenerationForm'
import { SummaryCard } from '../features/generation/components/SummaryCard'
import { VideoModeSelector } from '../features/generation/components/VideoModeSelector'

export default function GenerationPage() {
  const navigate = useNavigate()
  
  // Retrieve stored data
  const selectedTopics = storageService.getSelectedTopics()
  const analysis = storageService.getAnalysis()
  const resumeJobId = storageService.getResumeJobId()
  const isResuming = !!resumeJobId

  const {
    selectedLanguage, setSelectedLanguage,
    selectedVoice, setSelectedVoice,
    style, setStyle,
    videoMode, setVideoMode,
    contentFocus, setContentFocus,
    documentContext, setDocumentContext,
    isGenerating,
    handleGenerate
  } = useGenerationForm(analysis, selectedTopics)

  const { voices, languages } = useVoices(selectedLanguage)

  if (!analysis) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-6">
        <p className="text-gray-400">No analysis data found. Please start over.</p>
        <button
          onClick={() => navigate('/')}
          className="px-6 py-3 bg-math-blue text-white rounded-lg hover:bg-math-blue/80 transition-colors"
        >
          Go Home
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Analysis
        </button>
        <h1 className="text-3xl font-bold mb-2">Customize Your Videos</h1>
        <p className="text-gray-400">
          Configure style, voice, and other settings before generating.
        </p>
      </div>

      <SummaryCard 
        analysis={analysis} 
        selectedTopics={selectedTopics} 
      />

      {/* Settings */}
      <div className="space-y-6">
        <VideoModeSelector 
          videoMode={videoMode} 
          setVideoMode={setVideoMode} 
        />

        {/* Content Focus Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800 text-left">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-math-orange/20 rounded-lg">
              <BookOpen className="w-5 h-5 text-math-orange" />
            </div>
            <h2 className="text-lg font-semibold">Content Focus</h2>
          </div>
          <p className="text-sm text-gray-400 mb-4">
            Choose how the video should balance examples and theory
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { 
                id: 'as_document', 
                name: 'As Document', 
                desc: 'Follow the document structure', 
                icon: FileText,
                color: 'bg-math-orange/20 border-math-orange'
              },
              { 
                id: 'practice', 
                name: 'Practice', 
                desc: 'More examples and problems', 
                icon: GraduationCap,
                color: 'bg-math-green/20 border-math-green'
              },
              { 
                id: 'theory', 
                name: 'Theory', 
                desc: 'More proofs and derivations', 
                icon: BookOpen,
                color: 'bg-math-purple/20 border-math-purple'
              }
            ].map(item => (
              <button
                key={item.id}
                onClick={() => setContentFocus(item.id as any)}
                className={`
                  p-4 rounded-lg text-left transition-all
                  ${contentFocus === item.id 
                    ? `${item.color} border-2` 
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                  }
                `}
              >
                <div className="flex items-center gap-2 mb-2">
                  <item.icon className="w-5 h-5" />
                  <p className="font-semibold">{item.name}</p>
                </div>
                <p className="text-sm text-gray-400">{item.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Document Context Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800 text-left">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-teal-500/20 rounded-lg">
              <Layers className="w-5 h-5 text-teal-400" />
            </div>
            <h2 className="text-lg font-semibold">Document Context</h2>
          </div>
          <p className="text-sm text-gray-400 mb-4">
            Is this document standalone or part of a series?
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {[
              { id: 'auto', name: 'Auto-detect', desc: 'AI will decide', icon: Zap },
              { id: 'standalone', name: 'Standalone', desc: 'No prior knowledge assumed', icon: FileText },
              { id: 'series', name: 'Part of Series', desc: 'Assumes prior concepts', icon: Link2 },
            ].map(item => (
              <button
                key={item.id}
                onClick={() => setDocumentContext(item.id as any)}
                className={`
                  p-4 rounded-lg text-left transition-all
                  ${documentContext === item.id 
                    ? 'bg-teal-500/20 border-teal-400 border-2' 
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                  }
                `}
              >
                <div className="flex items-center gap-2 mb-2">
                  <item.icon className="w-5 h-5" />
                  <p className="font-semibold">{item.name}</p>
                </div>
                <p className="text-sm text-gray-400">{item.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Language & Voice Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800 text-left">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-math-purple/20 rounded-lg">
              <Globe className="w-5 h-5 text-math-purple" />
            </div>
            <h2 className="text-lg font-semibold">Language & Voice</h2>
          </div>
          
          <div className="mb-6">
            <label className="text-sm text-gray-400 mb-2 block">Language</label>
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => setSelectedLanguage('auto')}
                className={`
                  px-4 py-2 rounded-lg font-medium transition-all
                  ${selectedLanguage === 'auto' 
                    ? 'bg-math-purple text-white' 
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                  }
                `}
              >
                Auto (Document)
              </button>
              {languages.map(lang => (
                <button
                  key={lang.code}
                  onClick={() => setSelectedLanguage(lang.code)}
                  className={`
                    px-4 py-2 rounded-lg font-medium transition-all
                    ${selectedLanguage === lang.code 
                      ? 'bg-math-purple text-white' 
                      : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                    }
                  `}
                >
                  {lang.name}
                </button>
              ))}
            </div>
          </div>
          
          <div>
            <label className="text-sm text-gray-400 mb-2 block">Voice</label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {voices.map(voice => (
                <button
                  key={voice.id}
                  onClick={() => setSelectedVoice(voice.id)}
                  className={`
                    p-3 rounded-lg text-left transition-all
                    ${selectedVoice === voice.id 
                      ? 'bg-math-purple/20 border-math-purple border' 
                      : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                    }
                  `}
                >
                  <p className="font-medium">{voice.name}</p>
                  <p className="text-sm text-gray-500 capitalize">{voice.gender}</p>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Style Selection */}
        <div className="p-6 bg-gray-900/50 rounded-xl border border-gray-800 text-left">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-math-green/20 rounded-lg">
              <Palette className="w-5 h-5 text-math-green" />
            </div>
            <h2 className="text-lg font-semibold">Animation Style</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {[
              { id: '3b1b', name: '3Blue1Brown', desc: 'Classic dark theme', color: 'bg-blue-600' },
              { id: 'clean', name: 'Clean White', desc: 'Light professional theme', color: 'bg-gray-200' },
              { id: 'dracula', name: 'Dracula', desc: 'Dark purple aesthetic', color: 'bg-purple-600' },
              { id: 'nord', name: 'Nord', desc: 'Cool arctic look', color: 'bg-slate-400' },
            ].map(s => (
              <button
                key={s.id}
                onClick={() => setStyle(s.id as any)}
                className={`
                  p-3 rounded-lg text-left transition-all relative overflow-hidden
                  ${style === s.id 
                    ? 'bg-math-green/20 border-math-green border-2' 
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-600'
                  }
                `}
              >
                <div className={`absolute top-2 right-2 w-3 h-3 rounded-full ${s.color} border border-gray-600`}></div>
                <p className="font-medium">{s.name}</p>
                <p className="text-xs text-gray-500">{s.desc}</p>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Resume Banner */}
      {isResuming && (
        <div className="bg-gradient-to-r from-math-green/20 to-teal-500/20 border border-math-green/50 rounded-xl p-4 flex items-center gap-3">
          <RotateCcw className="w-5 h-5 text-math-green" />
          <div>
            <p className="font-medium text-math-green">Resuming Previous Generation</p>
            <p className="text-sm text-gray-400">
              Continuing from where you left off.
            </p>
          </div>
        </div>
      )}

      {/* Generate Button */}
      <div className="flex justify-end pt-4">
        <button
          onClick={() => handleGenerate(selectedVoice)}
          disabled={isGenerating}
          className={`flex items-center justify-center gap-2 px-10 py-4 w-full md:w-auto
                     ${isResuming 
                       ? 'bg-gradient-to-r from-math-green to-teal-500' 
                       : 'bg-gradient-to-r from-math-blue to-math-purple'
                     }
                     text-white rounded-xl font-bold text-lg hover:opacity-90 transition-all active:scale-95
                     disabled:opacity-50 disabled:cursor-not-allowed shadow-xl`}
        >
          {isGenerating ? (
            <>
              <Loader2 className="w-6 h-6 animate-spin" />
              {isResuming ? 'Resuming...' : 'Generating...'}
            </>
          ) : isResuming ? (
            <>
              <RotateCcw className="w-6 h-6" />
              Resume Generation
            </>
          ) : (
            <>
              Generate Videos
              <ChevronRight className="w-6 h-6" />
            </>
          )}
        </button>
      </div>
    </div>
  )
}
