import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'

export default function Collapsible({ title, children, className = '' }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`card ${className}`}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-2 text-left"
      >
        <h4 className="text-sm font-bold text-ink flex items-center gap-1.5">
          {title}
        </h4>
        {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>
      {open && <div className="mt-4 pt-3 border-t border-border">{children}</div>}
    </div>
  )
}
