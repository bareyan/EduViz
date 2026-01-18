import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';

interface Section {
  id: string;
  title: string;
  narration: string;
  duration_seconds: number;
  visual_description: string;
  manim_code: string;
  video?: string;
  audio?: string;
}

interface CapturedFrame {
  time: number;
  dataUrl: string;
}

const API_URL = 'http://localhost:8000';

export default function EditPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  
  const [sections, setSections] = useState<Section[]>([]);
  const [selectedSection, setSelectedSection] = useState<Section | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [recompiling, setRecompiling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  // Frame capture state
  const [capturedFrames, setCapturedFrames] = useState<CapturedFrame[]>([]);
  const [fixPrompt, setFixPrompt] = useState('');
  const [fixing, setFixing] = useState(false);
  const [videoLoaded, setVideoLoaded] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (jobId) {
      fetchSections();
    }
  }, [jobId]);

  const fetchSections = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/job/${jobId}/sections`);
      setSections(response.data.sections || []);
      if (response.data.sections?.length > 0 && !selectedSection) {
        setSelectedSection(response.data.sections[0]);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fetch sections');
    } finally {
      setLoading(false);
    }
  };

  const selectSection = (section: Section) => {
    setSelectedSection(section);
    setCapturedFrames([]);
    setFixPrompt('');
    setError(null);
    setSuccessMessage(null);
    setVideoLoaded(false);
  };

  const regenerateSection = async () => {
    if (!selectedSection || !jobId) return;
    
    try {
      setRegenerating(true);
      setError(null);
      await axios.post(
        `${API_URL}/job/${jobId}/section/${selectedSection.id}/regenerate`
      );
      
      // Refresh sections to get new video
      await fetchSections();
      setSuccessMessage('Section regenerated successfully!');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to regenerate section');
    } finally {
      setRegenerating(false);
    }
  };

  const recompileAll = async () => {
    if (!jobId) return;
    
    try {
      setRecompiling(true);
      setError(null);
      await axios.post(`${API_URL}/job/${jobId}/recompile`);
      setSuccessMessage('Recompilation started! Redirecting to results...');
      setTimeout(() => navigate(`/results/${jobId}`), 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to start recompilation');
    } finally {
      setRecompiling(false);
    }
  };

  const captureFrame = useCallback(() => {
    if (!videoRef.current || !videoLoaded) {
      setError('Video not ready yet. Please wait for it to load.');
      return;
    }
    
    const video = videoRef.current;
    
    // Check if video has dimensions
    if (video.videoWidth === 0 || video.videoHeight === 0) {
      setError('Video dimensions not available. Please wait for video to load.');
      return;
    }
    
    try {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        setError('Could not create canvas context');
        return;
      }
      
      ctx.drawImage(video, 0, 0);
      const dataUrl = canvas.toDataURL('image/png');
      
      setCapturedFrames(prev => [...prev, {
        time: video.currentTime,
        dataUrl
      }]);
      
      setSuccessMessage(`Frame captured at ${video.currentTime.toFixed(2)}s`);
      setTimeout(() => setSuccessMessage(null), 2000);
    } catch (err: any) {
      setError(`Failed to capture frame: ${err.message}`);
    }
  }, [videoLoaded]);

  const removeFrame = (index: number) => {
    setCapturedFrames(prev => prev.filter((_, i) => i !== index));
  };

  const fixWithGemini = async () => {
    if (!selectedSection || !jobId) return;
    if (!fixPrompt.trim() && capturedFrames.length === 0) {
      setError('Please describe what you want to change or capture frames showing the issue');
      return;
    }
    
    try {
      setFixing(true);
      setError(null);
      
      // Step 1: Get the fixed code from Gemini
      const response = await axios.post(
        `${API_URL}/job/${jobId}/section/${selectedSection.id}/fix`,
        {
          prompt: fixPrompt,
          frames: capturedFrames.map(f => f.dataUrl),
          current_code: selectedSection.manim_code
        }
      );
      
      if (response.data.fixed_code) {
        // Step 2: Save the fixed code
        await axios.put(
          `${API_URL}/job/${jobId}/section/${selectedSection.id}/code`,
          { manim_code: response.data.fixed_code }
        );
        
        setSuccessMessage('Code fixed! Now regenerating video...');
        
        // Step 3: Regenerate the video
        await axios.post(
          `${API_URL}/job/${jobId}/section/${selectedSection.id}/regenerate`
        );
        
        // Refresh to get the new video
        await fetchSections();
        
        // Clear the form
        setFixPrompt('');
        setCapturedFrames([]);
        
        setSuccessMessage('Section fixed and regenerated successfully!');
        setTimeout(() => setSuccessMessage(null), 5000);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to fix section');
    } finally {
      setFixing(false);
    }
  };

  const formatDuration = (seconds: number | undefined) => {
    if (seconds === undefined || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getVideoUrl = (section: Section) => {
    if (section.video) {
      return `${API_URL}/file-content?path=${encodeURIComponent(section.video)}`;
    }
    return null;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-white text-xl">Loading sections...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/gallery')}
              className="text-gray-400 hover:text-white"
            >
              ← Back to Gallery
            </button>
            <h1 className="text-xl font-bold">Edit Video Sections</h1>
          </div>
          <button
            onClick={recompileAll}
            disabled={recompiling}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 rounded-lg font-medium"
          >
            {recompiling ? 'Recompiling...' : 'Recompile All & Apply'}
          </button>
        </div>
      </header>

      {/* Messages */}
      {error && (
        <div className="max-w-7xl mx-auto mt-4 px-4">
          <div className="bg-red-900/50 border border-red-500 text-red-200 px-4 py-3 rounded-lg">
            {error}
          </div>
        </div>
      )}
      {successMessage && (
        <div className="max-w-7xl mx-auto mt-4 px-4">
          <div className="bg-green-900/50 border border-green-500 text-green-200 px-4 py-3 rounded-lg">
            {successMessage}
          </div>
        </div>
      )}

  <div className="max-w-6xl mx-auto px-3 py-3 flex gap-3" style={{ height: 'calc(100vh - 80px)' }}>
        {/* Sections List */}
  <div className="w-72 flex-shrink-0 bg-gray-800 rounded-lg overflow-hidden flex flex-col">
          <h2 className="text-lg font-semibold p-4 border-b border-gray-700">
            Sections ({sections.length})
          </h2>
          <div className="flex-1 overflow-y-auto">
            {sections.map((section, index) => (
              <div
                key={section.id}
                onClick={() => selectSection(section)}
                className={`p-4 cursor-pointer border-b border-gray-700 hover:bg-gray-700 transition-colors ${
                  selectedSection?.id === section.id ? 'bg-blue-900/50 border-l-4 border-l-blue-500' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-gray-400">Section {index + 1}</span>
                  <span className="text-xs text-gray-500">
                    {formatDuration(section.duration_seconds)}
                  </span>
                </div>
                <h3 className="font-medium truncate">{section.title}</h3>
                {section.video && (
                  <span className="inline-block mt-1 text-xs bg-green-900/50 text-green-400 px-2 py-0.5 rounded">
                    Has Video
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Main Content */}
        {selectedSection ? (
          <div className="flex-1 flex flex-col gap-4 overflow-auto p-2">
            {/* Section Info */}
            <div className="bg-gray-800 rounded-lg p-4">
              <h2 className="text-xl font-bold mb-2">{selectedSection.title}</h2>
              <p className="text-gray-400 text-sm mb-2">{selectedSection.narration}</p>
              <p className="text-gray-500 text-xs">
                Duration: {formatDuration(selectedSection.duration_seconds)} | 
                Visual: {selectedSection.visual_description}
              </p>
            </div>

            {/* Video Preview & Frame Capture */}
            {getVideoUrl(selectedSection) && (
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-semibold">Video Preview</h3>
                  <span className="text-sm text-gray-400">
                    Pause video and click capture to send frames to AI
                  </span>
                </div>
                <div className="relative">
                  <video
                    ref={videoRef}
                    src={getVideoUrl(selectedSection)!}
                    controls
                    crossOrigin="anonymous"
                    className="w-full rounded-lg bg-black"
                    style={{ maxHeight: '300px' }}
                    onLoadedData={() => setVideoLoaded(true)}
                    onError={() => setError('Failed to load video')}
                  />
                  <button
                    onClick={captureFrame}
                    disabled={!videoLoaded}
                    className="absolute bottom-14 right-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 rounded-lg text-sm shadow-lg flex items-center gap-2"
                  >
                    📷 Capture Frame
                    {capturedFrames.length > 0 && (
                      <span className="bg-white/20 px-2 py-0.5 rounded-full text-xs">
                        {capturedFrames.length}
                      </span>
                    )}
                  </button>
                </div>
              </div>
            )}

            {/* AI-Powered Edit Section */}
            <div className="flex-1 bg-gray-800 rounded-lg p-6 flex flex-col">
              <h3 className="text-xl font-semibold mb-4">✨ Edit with AI</h3>
              
              <div className="space-y-4 flex-1">
                {/* Prompt Input */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Describe what you want to change:
                  </label>
                  <textarea
                    value={fixPrompt}
                    onChange={(e) => setFixPrompt(e.target.value)}
                    placeholder="Examples:&#10;• Make the animation slower and smoother&#10;• Center the equations on screen&#10;• Add a fade-in effect to the title&#10;• Change the color scheme to blue and white&#10;• Fix the positioning of the graph"
                    className="w-full h-32 bg-gray-700 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-400 resize-none"
                  />
                </div>
                
                {/* Captured Frames Display */}
                {capturedFrames.length > 0 && (
                  <div className="bg-gray-700/50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-gray-300">
                        📷 Captured Frames ({capturedFrames.length})
                      </span>
                      <button
                        onClick={() => setCapturedFrames([])}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        Clear all
                      </button>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      {capturedFrames.map((frame, index) => (
                        <div key={index} className="relative group">
                          <img
                            src={frame.dataUrl}
                            alt={`Frame ${index + 1}`}
                            className="h-16 w-auto rounded border border-gray-600"
                          />
                          <button
                            onClick={() => removeFrame(index)}
                            className="absolute -top-1 -right-1 bg-red-600 text-white rounded-full w-4 h-4 text-xs flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                    <p className="text-xs text-gray-400 mt-2">
                      These frames will be sent to AI to understand the visual context
                    </p>
                  </div>
                )}
                
                {/* Action Buttons */}
                <div className="flex gap-3 pt-2">
                  <button
                    onClick={fixWithGemini}
                    disabled={fixing || (!fixPrompt.trim() && capturedFrames.length === 0)}
                    className="flex-1 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-600 disabled:to-gray-600 rounded-lg font-medium text-lg transition-all"
                  >
                    {fixing ? (
                      <span className="flex items-center justify-center gap-2">
                        <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Fixing & Regenerating...
                      </span>
                    ) : (
                      '🤖 Fix with AI & Regenerate'
                    )}
                  </button>
                  
                  <button
                    onClick={regenerateSection}
                    disabled={regenerating || fixing}
                    className="px-6 py-3 bg-orange-600 hover:bg-orange-700 disabled:bg-gray-600 rounded-lg font-medium"
                    title="Regenerate video from current code"
                  >
                    {regenerating ? 'Regenerating...' : '🔄 Regenerate'}
                  </button>
                </div>
                
                <p className="text-xs text-gray-500 mt-2">
                  💡 Tip: Capture frames from the video to show the AI exactly what needs fixing
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            <div className="text-center">
              <p className="text-xl mb-2">👈 Select a section to edit</p>
              <p className="text-sm">Click on a section from the list to start editing</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}