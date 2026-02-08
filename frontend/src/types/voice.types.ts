export interface Voice {
  id: string
  name: string
  gender: string
  preview_url?: string
}

export interface Language {
  code: string
  name: string
}

export interface VoicesResponse {
  voices: Voice[]
  languages: Language[]
  current_language: string
  default_voice: string
}
