import { useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  ChevronLeft, 
  Video, 
  Camera, 
  Wand2, 
  RefreshCw,
  Save,
  Play,
  Terminal,
  AlertCircle
} from 'lucide-react';
import { jobService } from '../services/job.service';
import { API_BASE as API_URL } from '../config/api.config';
import { useEditSection } from '../features/edit/hooks/useEditSection';
import { formatDuration } from '../utils/format.utils';
import { toast } from 'react-hot-toast';

export default function EditPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  
  const {
    sections,
    selectedSection,
    setSelectedSection,
    loading,
    isProcessing,
    capturedFrames,
    setCapturedFrames,
    fixPrompt,
    setFixPrompt,
    videoLoaded,
    setVideoLoaded,
    fetchSections,
    handleRegenerate,
    handleFixWithGemini,
    captureFrame,
    removeFrame
  } = useEditSection(jobId || '');

  useEffect(() => {
    fetchSections();
  }, [fetchSections]);

  const recompileAll = async () => {
    if (!jobId) return;
    try {
      await jobService.recompileJob(jobId);
      toast.success('Recompilation started! Redirecting...');
      setTimeout(() => navigate(`/results/${jobId}`), 2000);
    } catch (err) {
      toast.error('Failed to start recompilation');
    }
  };

  const getVideoUrl = (videoPath: string | undefined) => {
    if (!videoPath) return null;
    // Use the proxy/endpoint that handles file content and add cache buster
    return `${API_URL}/file-content?path=${encodeURIComponent(videoPath)}&t=${Date.now()}`;
  };

  if (loading && sections.length === 0) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <RefreshCw className="w-10 h-10 text-blue-500 animate-spin" />
          <div className="text-white text-xl">Loading sections...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white flex flex-col">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 p-4 shrink-0">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              to="/gallery"
              className="p-2 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors"
            >
              <ChevronLeft className="w-6 h-6" />
            </Link>
            <div>
              <h1 className="text-xl font-bold">Edit Video Sections</h1>
              <p className="text-xs text-gray-400">Job ID: {jobId}</p>
            </div>
          </div>
          <button
            onClick={recompileAll}
            disabled={isProcessing}
            className="flex items-center gap-2 px-6 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-700 rounded-lg font-bold shadow-lg transition-all"
          >
            {isProcessing ? (
              <RefreshCw className="w-5 h-5 animate-spin" />
            ) : (
              <Save className="w-5 h-5" />
            )}
            Apply All Changes & Recompile
          </button>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        {/* Sections Sidebar */}
        <div className="w-80 bg-gray-800 border-r border-gray-700 flex flex-col">
          <div className="p-4 border-b border-gray-700">
            <h2 className="font-semibold text-gray-300">Sections ({sections.length})</h2>
          </div>
          <div className="flex-1 overflow-y-auto">
            {sections.map((section, index) => (
              <button
                key={section.id}
                onClick={() => setSelectedSection(section)}
                className={`w-full p-4 flex flex-col gap-1 text-left border-b border-gray-700 transition-all ${
                  selectedSection?.id === section.id 
                    ? 'bg-blue-600/20 border-l-4 border-l-blue-500' 
                    : 'hover:bg-gray-700/50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Section {index + 1}
                  </span>
                  <span className="text-xs text-gray-500">
                    {formatDuration(section.duration_seconds)}
                  </span>
                </div>
                <h3 className="font-semibold truncate text-gray-200">{section.title}</h3>
                <div className="flex items-center gap-2 mt-1">
                  {section.video ? (
                    <span className="flex items-center gap-1 text-[10px] bg-green-500/10 text-green-400 px-1.5 py-0.5 rounded border border-green-500/20">
                      <Play className="w-2.5 h-2.5" /> VIDEO Ready
                    </span>
                  ) : (
                    <span className="text-[10px] bg-yellow-500/10 text-yellow-500 px-1.5 py-0.5 rounded border border-yellow-500/20">
                      NO VIDEO
                    </span>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 flex flex-col overflow-y-auto bg-gray-900/50">
          {selectedSection ? (
            <div className="p-6 max-w-5xl mx-auto w-full flex flex-col gap-6">
              {/* Info Card */}
              <div className="bg-gray-800/80 backdrop-blur rounded-xl p-5 border border-gray-700 shadow-xl text-left">
                <h2 className="text-xl font-bold text-white mb-2">{selectedSection.title}</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500 block mb-1">Narration</span>
                    <p className="text-gray-300 italic">"{selectedSection.narration}"</p>
                  </div>
                  <div>
                    <span className="text-gray-500 block mb-1">Visual Direction</span>
                    <p className="text-gray-300">{selectedSection.visual_description}</p>
                  </div>
                </div>
              </div>

              {/* Video & Controls */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className="lg:col-span-12 xl:col-span-7 flex flex-col gap-4">
                  <div className="bg-black rounded-xl overflow-hidden aspect-video relative group shadow-2xl border border-gray-800">
                    {selectedSection.video ? (
                      <>
                        <video
                          key={selectedSection.id + (selectedSection.video || '')}
                          ref={videoRef}
                          src={getVideoUrl(selectedSection.video)!}
                          controls
                          crossOrigin="anonymous"
                          className="w-full h-full"
                          onLoadedData={() => setVideoLoaded(true)}
                        />
                        <button
                          onClick={() => captureFrame(videoRef.current)}
                          disabled={!videoLoaded}
                          className="absolute bottom-16 right-4 flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg text-sm font-bold shadow-xl transition-all opacity-0 group-hover:opacity-100 disabled:opacity-0"
                        >
                          <Camera className="w-4 h-4" />
                          Capture Frame
                        </button>
                      </>
                    ) : (
                      <div className="w-full h-full flex items-center justify-center text-gray-600 bg-gray-900">
                        <div className="text-center">
                          <Video className="w-16 h-16 mx-auto mb-2 opacity-20" />
                          <p>No video generated for this section yet</p>
                        </div>
                      </div>
                    )}
                  </div>

                  {capturedFrames.length > 0 && (
                    <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-bold text-gray-400 flex items-center gap-2">
                          <Camera className="w-4 h-4" /> CAPTURED CONTEXT ({capturedFrames.length})
                        </h3>
                        <button 
                          onClick={() => setCapturedFrames([])}
                          className="text-xs text-red-400 hover:underline"
                        >
                          Clear All
                        </button>
                      </div>
                      <div className="flex gap-3 overflow-x-auto pb-2">
                        {capturedFrames.map((frame, idx) => (
                          <div key={idx} className="relative shrink-0 group">
                            <img 
                              src={frame.dataUrl} 
                              alt="Context" 
                              className="h-20 rounded border border-gray-600 group-hover:border-blue-500 transition-colors"
                            />
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                              <button 
                                onClick={() => removeFrame(idx)}
                                className="bg-red-500 p-1 rounded-full"
                              >
                                <AlertCircle className="w-4 h-4" />
                              </button>
                            </div>
                            <span className="absolute bottom-0 left-0 right-0 bg-black/60 text-[10px] text-center">
                              {frame.time.toFixed(1)}s
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* AI Editor Panel */}
                <div className="lg:col-span-12 xl:col-span-5">
                  <div className="bg-gray-800 rounded-xl p-5 border border-gray-700 h-full flex flex-col gap-4 shadow-xl text-left">
                    <div className="flex items-center gap-2 text-purple-400">
                      <Wand2 className="w-5 h-5" />
                      <h3 className="font-bold text-lg">AI Vision Editor</h3>
                    </div>
                    
                    <div className="flex-1 flex flex-col gap-2">
                      <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                        What would you like to change?
                      </label>
                      <textarea
                        value={fixPrompt}
                        onChange={(e) => setFixPrompt(e.target.value)}
                        placeholder="e.g. 'Move the text to the center', 'Make objects blue'..."
                        className="flex-1 bg-gray-900 border border-gray-700 rounded-lg p-3 text-sm focus:ring-2 focus:ring-purple-500 outline-none resize-none transition-all"
                      />
                    </div>

                    <div className="flex flex-col gap-2">
                      <button
                        onClick={() => handleFixWithGemini(selectedSection.id, selectedSection.manim_code)}
                        disabled={isProcessing || (!fixPrompt.trim() && capturedFrames.length === 0)}
                        className="w-full py-3 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 disabled:from-gray-700 disabled:to-gray-700 rounded-lg font-bold flex items-center justify-center gap-2 shadow-lg transition-transform active:scale-95"
                      >
                        {isProcessing ? (
                          <RefreshCw className="w-5 h-5 animate-spin" />
                        ) : (
                          <Wand2 className="w-5 h-5" />
                        )}
                        Ask AI to Fix & Regenerate
                      </button>
                      
                      <button
                        onClick={() => handleRegenerate(selectedSection.id)}
                        disabled={isProcessing}
                        className="w-full py-2 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg text-sm font-semibold flex items-center justify-center gap-2"
                      >
                        <RefreshCw className={`w-4 h-4 ${isProcessing ? 'animate-spin' : ''}`} />
                        Just Regenerate current code
                      </button>
                    </div>
                    
                    <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-xs text-blue-300">
                      <p className="flex items-center gap-2">
                        <Terminal className="w-3.5 h-3.5" />
                        Tip: Pause the video at the moment of the issue and capture a frame.
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Code Preview */}
              <div className="bg-gray-800 rounded-xl overflow-hidden border border-gray-700 shadow-xl text-left">
                <div className="bg-gray-900/50 p-3 border-b border-gray-700 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-gray-400">
                    <Terminal className="w-4 h-4" />
                    <span className="text-xs font-mono">manim_code.py</span>
                  </div>
                </div>
                <div className="relative group">
                  <pre className="p-4 text-xs font-mono text-gray-300 overflow-x-auto max-h-60 bg-[#1a1b26]">
                    <code>{selectedSection.manim_code}</code>
                  </pre>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex items-center justify-center p-8">
              <div className="text-center max-w-sm">
                <div className="w-20 h-20 bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-4 border border-gray-700">
                  <Play className="w-10 h-10 text-gray-600" />
                </div>
                <h2 className="text-xl font-bold mb-2">Select a Section</h2>
                <p className="text-gray-500 text-sm">
                  Choose a section from the left sidebar to preview and edit.
                </p>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
