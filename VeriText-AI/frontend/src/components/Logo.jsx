import { Link } from 'react-router-dom'

/**
 * VeriText AI wordmark: a text-document glyph whose baseline doubles as an
 * "equals" stroke — matching words vs. understanding meaning.
 */
export default function Logo({ to = '/', variant = 'dark', showTagline = false, size = 'md' }) {
  const isLight = variant === 'light'
  const dimension = size === 'sm' ? 'h-7 w-7' : 'h-9 w-9'

  return (
    <Link to={to} className="group flex items-center gap-2.5" aria-label="VeriText AI home">
      <span
        className={`${dimension} flex shrink-0 items-center justify-center rounded-[9px] ${
          isLight ? 'bg-white/10 ring-1 ring-inset ring-white/20' : 'bg-navy-900'
        }`}
      >
        <svg viewBox="0 0 32 32" className="h-[62%] w-[62%]" aria-hidden="true">
          <path
            d="M8 8.5h8.5a4.75 4.75 0 0 1 0 9.5H8z"
            fill="none"
            stroke="white"
            strokeWidth="2.2"
            strokeLinejoin="round"
          />
          <path
            d="M8 18h11.5M8 23.5h7.5"
            fill="none"
            stroke="white"
            strokeWidth="2.2"
            strokeLinecap="round"
            opacity="0.65"
          />
        </svg>
      </span>
      <span className="leading-tight">
        <span
          className={`block text-[15px] font-semibold tracking-[-0.01em] ${
            isLight ? 'text-white' : 'text-navy-900'
          }`}
        >
          VeriText<span className={isLight ? 'text-white/60' : 'text-accent-600'}> AI</span>
        </span>
        {showTagline && (
          <span
            className={`mt-0.5 block text-[11px] ${
              isLight ? 'text-white/55' : 'text-navy-400'
            }`}
          >
            Beyond Matching Words. Understanding Meaning.
          </span>
        )}
      </span>
    </Link>
  )
}
