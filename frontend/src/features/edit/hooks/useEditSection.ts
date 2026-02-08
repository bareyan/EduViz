import { useState, useCallback } from 'react';
import { jobService } from '../../../services/job.service';
import { SectionEdit } from '../../../types/job.types';
import { toast } from 'react-hot-toast';

export const useEditSection = (jobId: string) => {
  const [sections, setSections] = useState<SectionEdit[]>([]);
  const [selectedSection, setSelectedSection] = useState<SectionEdit | null>(null);
  const [loading, setLoading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  
  const [capturedFrames, setCapturedFrames] = useState<{ time: number; dataUrl: string }[]>([]);
  const [fixPrompt, setFixPrompt] = useState('');
  const [videoLoaded, setVideoLoaded] = useState(false);

  const fetchSections = useCallback(async () => {
    if (!jobId) return;
    try {
      setLoading(true);
      const data = await jobService.getJobSections(jobId);
      setSections(data);
      if (data.length > 0 && !selectedSection) {
        setSelectedSection(data[0]);
      } else if (selectedSection) {
        // Update selected section from new data
        const updated = data.find(s => s.id === selectedSection.id);
        if (updated) setSelectedSection(updated);
      }
    } catch (error) {
      console.error('Failed to fetch sections:', error);
      toast.error('Failed to fetch sections');
    } finally {
      setLoading(false);
    }
  }, [jobId, selectedSection]);

  const handleRegenerate = async (sectionId: string) => {
    try {
      setIsProcessing(true);
      await jobService.regenerateSection(jobId, sectionId);
      await fetchSections();
      toast.success('Section regenerated successfully!');
    } catch (error) {
      toast.error('Failed to regenerate section');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleFixWithGemini = async (sectionId: string, currentCode: string) => {
    if (!fixPrompt.trim() && capturedFrames.length === 0) {
      toast.error('Please describe what you want to change or capture frames');
      return;
    }

    try {
      setIsProcessing(true);
      // Backend expects 'error' as the prompt field for fix
      const { fixed_code } = await jobService.fixSection(jobId, sectionId, fixPrompt, currentCode);
      
      if (fixed_code) {
        await jobService.updateSectionCode(jobId, sectionId, fixed_code);
        toast.success('Code fixed! Regenerating...');
        await jobService.regenerateSection(jobId, sectionId);
        await fetchSections();
        setFixPrompt('');
        setCapturedFrames([]);
      }
    } catch (error) {
      toast.error('Failed to fix section');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleUpdateCode = async (sectionId: string, code: string) => {
    try {
      setIsProcessing(true);
      await jobService.updateSectionCode(jobId, sectionId, code);
      toast.success('Code saved!');
      await fetchSections();
    } catch (error) {
      toast.error('Failed to save code');
    } finally {
      setIsProcessing(false);
    }
  };

  const captureFrame = useCallback((video: HTMLVideoElement | null) => {
    if (!video || !videoLoaded) {
      toast.error('Video not ready yet');
      return;
    }
    
    if (video.videoWidth === 0 || video.videoHeight === 0) {
      toast.error('Video dimensions not available');
      return;
    }
    
    try {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      
      ctx.drawImage(video, 0, 0);
      const dataUrl = canvas.toDataURL('image/png');
      
      setCapturedFrames(prev => [...prev, {
        time: video.currentTime,
        dataUrl
      }]);
      
      toast.success(`Frame captured at ${video.currentTime.toFixed(2)}s`);
    } catch (err: any) {
      toast.error('Failed to capture frame');
    }
  }, [videoLoaded]);

  const removeFrame = (index: number) => {
    setCapturedFrames(prev => prev.filter((_, i) => i !== index));
  };

  return {
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
    handleUpdateCode,
    captureFrame,
    removeFrame
  };
};
