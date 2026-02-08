import { useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  ChevronLeft, 
  Video, 
  Camera, 
  RefreshCw,
  Save,
  Play
} from 'lucide-react';
import { jobService } from '../services/job.service';
import { API_BASE as API_URL } from '../config/api.config';
import { useEditSection } from '../features/edit/hooks/useEditSection';
import { toast } from 'react-hot-toast';
import { EditSidebar } from '../features/edit/components/EditSidebar';
import { AIEditorPanel } from '../features/edit/components/AIEditorPanel';
import { CodePreview } from '../features/edit/components/CodePreview';
import { CapturedFrames } from '../features/edit/components/CapturedFrames';

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
        <EditSidebar 
          sections={sections}
          selectedSection={selectedSection}
          onSelectSection={setSelectedSection}
        />

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

                  <CapturedFrames
                    frames={capturedFrames}
                    onClearAll={() => setCapturedFrames([])}
                    onRemoveFrame={removeFrame}
                  />
                </div>

                {/* AI Editor Panel */}
                <div className="lg:col-span-12 xl:col-span-5">
                  <AIEditorPanel
                    fixPrompt={fixPrompt}
                    setFixPrompt={setFixPrompt}
                    isProcessing={isProcessing}
                    capturedFramesCount={capturedFrames.length}
                    onFix={() => handleFixWithGemini(selectedSection.id, selectedSection.manim_code)}
                    onRegenerate={() => handleRegenerate(selectedSection.id)}
                  />
                </div>
              </div>

              {/* Code Preview */}
              <CodePreview code={selectedSection.manim_code} />
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
