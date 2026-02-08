import { Upload, Loader2, FileText, Image } from 'lucide-react'
import { useDropzone } from 'react-dropzone'

interface UploadZoneProps {
  onDrop: (acceptedFiles: File[]) => void
  isUploading: boolean
  uploadProgress: number
}

export function UploadZone({ onDrop, isUploading, uploadProgress }: UploadZoneProps) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/png': ['.png'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/webp': ['.webp'],
      'text/plain': ['.txt'],
      'application/x-tex': ['.tex'],
      'text/x-tex': ['.tex'],
    },
    maxFiles: 1,
    disabled: isUploading,
  })

  return (
    <div
      {...getRootProps()}
      className={`
        relative max-w-2xl mx-auto p-12 border-2 border-dashed rounded-2xl cursor-pointer
        transition-all duration-300 card-hover
        ${isDragActive 
          ? 'border-math-blue bg-math-blue/10' 
          : 'border-gray-700 hover:border-math-blue/50 bg-gray-900/50'
        }
        ${isUploading ? 'pointer-events-none opacity-70' : ''}
      `}
    >
      <input {...getInputProps()} />
      
      {isUploading ? (
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-16 h-16 text-math-blue animate-spin" />
          <div className="w-full max-w-xs bg-gray-800 rounded-full h-2">
            <div 
              className="bg-math-blue h-2 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
          <p className="text-gray-400">Uploading your file...</p>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-4">
          <div className="relative">
            <Upload className="w-16 h-16 text-gray-500" />
            <div className="absolute inset-0 bg-math-blue/20 blur-xl" />
          </div>
          <div>
            <p className="text-lg font-medium text-white">
              {isDragActive ? 'Drop your file here' : 'Drag & drop your file here'}
            </p>
            <p className="text-gray-500 mt-1">or click to browse</p>
          </div>
          <div className="flex gap-4 mt-4">
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <FileText className="w-4 h-4" />
              <span>PDF, LaTeX, TXT</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-gray-500">
              <Image className="w-4 h-4" />
              <span>PNG, JPG, WebP</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
