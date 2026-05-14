/**
 * ElevareLogo — shared inline SVG logo mark.
 * variant="color" (default): Brand Blue left half + Amber right half
 * variant="white": both halves white (for dark backgrounds)
 */
export default function ElevareLogo({ size = 32, variant = 'color' }) {
  const left = variant === 'white' ? '#ffffff' : '#1A4D8F'
  const right = variant === 'white' ? '#ffffff' : '#E87722'

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {/* Left half — upward flame/leaf shape */}
      <path
        d="M16 3 C16 3 7 10 7 19 C7 24.5 11 28 16 28 L16 3Z"
        fill={left}
      />
      {/* Right half */}
      <path
        d="M16 3 C16 3 25 10 25 19 C25 24.5 21 28 16 28 L16 3Z"
        fill={right}
      />
    </svg>
  )
}
