const MAX_FILE_SIZE = 5_242_880 // 5 MB in bytes

const CV_ALLOWED_EXTENSIONS = ['.pdf']
const DOCUMENT_ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.png', '.jpg', '.jpeg']

function getExtension(filename) {
  const idx = filename.lastIndexOf('.')
  if (idx === -1) return ''
  return filename.slice(idx).toLowerCase()
}

// validateCvFile validates a file object for CV upload.
// Returns an error string if invalid, or null if valid.
// Requirements: 6.2, 6.3
export function validateCvFile(file) {
  const ext = getExtension(file.name)
  if (!CV_ALLOWED_EXTENSIONS.includes(ext)) {
    return 'Only PDF files are accepted for CVs.'
  }
  if (file.size > MAX_FILE_SIZE) {
    return 'File size must be under 5MB.'
  }
  return null
}

// validateDocumentFile validates a file object for career document upload.
// Returns an error string if invalid, or null if valid.
// Requirements: 7.2, 7.3
export function validateDocumentFile(file) {
  const ext = getExtension(file.name)
  if (!DOCUMENT_ALLOWED_EXTENSIONS.includes(ext)) {
    return 'Accepted formats: PDF, Word, PNG, JPG.'
  }
  if (file.size > MAX_FILE_SIZE) {
    return 'File size must be under 5MB.'
  }
  return null
}
