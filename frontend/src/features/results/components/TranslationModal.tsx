import { Play, Pause, Loader2 } from 'lucide-react'
import { TranslationsResponse } from '../../../types/translation.types'
import { Voice } from '../../../types/voice.types'
import { useVoicePreview } from '../../../hooks/useVoicePreview'

interface TranslationModalProps {
  onClose: () => void;
  onConfirm: () => void;
  translationLanguages: { code: string; name: string }[];
  translations?: TranslationsResponse | null;
  selectedLanguage: string;
  setSelectedLanguage: (code: string) => void;
  selectedVoice: string;
  setSelectedVoice: (voice: string) => void;
  translationVoices: Voice[];
  isTranslating: boolean;
}

export function TranslationModal({
  onClose,
  onConfirm,
  translationLanguages,
  translations,
  selectedLanguage,
  setSelectedLanguage,
  selectedVoice,
  setSelectedVoice,
  translationVoices,
  isTranslating
}: TranslationModalProps) {
  const { playingVoiceId, handlePreview } = useVoicePreview()

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-900 rounded-xl p-6 max-w-md w-full mx-4 border border-gray-800">
        <h3 className="text-xl font-semibold mb-4">Add Translation</h3>
        <p className="text-gray-400 text-sm mb-4">
          Select a language to translate the video into. The narration will be translated and
          new audio will be generated.
        </p>

        <label className="block text-sm font-medium text-gray-300 mb-2">Target Language</label>
        <div className="space-y-2 max-h-40 overflow-y-auto mb-4">
          {translationLanguages
            .filter(lang => lang.code !== translations?.original_language)
            .filter(lang => !translations?.translations.some((t: any) => t.language === lang.code))
            .map(lang => (
              <button
                key={lang.code}
                onClick={() => setSelectedLanguage(lang.code)}
                className={`w-full p-3 rounded-lg text-left transition-all ${selectedLanguage === lang.code
                    ? 'bg-math-purple/20 border-math-purple border'
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-700'
                  }`}
              >
                {lang.name}
              </button>
            ))}
        </div>

        <label className="block text-sm font-medium text-gray-300 mb-2">Voice</label>
        <div className="space-y-2 max-h-40 overflow-y-auto mb-4">
          {translationVoices.map(voice => (
            <div key={voice.id} className="relative group">
              <button
                onClick={() => setSelectedVoice(voice.id)}
                className={`w-full p-3 pr-12 rounded-lg text-left transition-all ${selectedVoice === voice.id
                    ? 'bg-math-purple/20 border-math-purple border'
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-700'
                  }`}
              >
                <div className="flex flex-col">
                  <span className="font-medium">{voice.name}</span>
                  <span className="text-xs text-gray-500 capitalize">{voice.gender}</span>
                </div>
              </button>
              {voice.preview_url && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handlePreview(voice.id, voice.preview_url);
                  }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-full bg-gray-700 hover:bg-gray-600 transition-colors text-white"
                  title="Preview voice"
                >
                  {playingVoiceId === voice.id ? (
                    <Pause className="w-3.5 h-3.5 fill-white" />
                  ) : (
                    <Play className="w-3.5 h-3.5 fill-white" />
                  )}
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={!selectedLanguage || isTranslating}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-math-purple text-white 
                       rounded-lg hover:bg-math-purple/80 transition-colors disabled:opacity-50"
          >
            {isTranslating ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Starting...
              </>
            ) : (
              'Start Translation'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
