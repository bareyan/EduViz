import { Loader2 } from 'lucide-react'
import { TranslationsResponse } from '../../../types/translation.types'

interface TranslationModalProps {
  onClose: () => void;
  onConfirm: () => void;
  translationLanguages: { code: string; name: string }[];
  translations?: TranslationsResponse | null;
  selectedLanguage: string;
  setSelectedLanguage: (code: string) => void;
  selectedVoice: string;
  setSelectedVoice: (voice: string) => void;
  translationVoices: { id: string; name: string; gender: string }[];
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
                className={`w-full p-3 rounded-lg text-left transition-all ${
                  selectedLanguage === lang.code
                    ? 'bg-math-purple/20 border-math-purple border'
                    : 'bg-gray-800 border-gray-700 border hover:border-gray-700'
                }`}
              >
                {lang.name}
              </button>
            ))}
        </div>
        
        <label className="block text-sm font-medium text-gray-300 mb-2">Voice</label>
        <select
          value={selectedVoice}
          onChange={(e) => setSelectedVoice(e.target.value)}
          className="w-full p-3 rounded-lg bg-gray-800 border border-gray-700 text-white mb-4
                     focus:outline-none focus:border-math-purple"
        >
          {translationVoices.map(voice => (
            <option key={voice.id} value={voice.id}>
              {voice.name} ({voice.gender})
            </option>
          ))}
        </select>
        
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
