export interface Translation {
  language: string
  has_script: boolean
  has_video: boolean
  video_url: string | null
}

export interface TranslationsResponse {
  job_id: string
  original_language: string
  translations: Translation[]
}

export interface TranslationResponse {
  job_id: string
  translation_id: string
  target_language: string
  status: string
  message: string
}

export interface TranslationLanguage {
  code: string
  name: string
}

export interface TranslationLanguagesResponse {
  languages: TranslationLanguage[]
}
