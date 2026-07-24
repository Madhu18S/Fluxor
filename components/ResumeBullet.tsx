'use client'

import { useState } from 'react'
import { Copy, Check } from 'lucide-react'

interface Props {
  text: string
}

export function ResumeBullet({ text }: Props) {
  const [copied, setCopied] = useState(false)

  function handleCopy() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className="rounded-lg border border-cyan/30 bg-cyan/5 p-4">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-mono leading-relaxed text-foreground">{text}</p>
        <button
          onClick={handleCopy}
          title="Copy to clipboard"
          className="flex-shrink-0 rounded p-1.5 text-muted-foreground transition-colors hover:bg-surface-2 hover:text-cyan"
        >
          {copied
            ? <Check className="w-4 h-4 text-gain" />
            : <Copy className="w-4 h-4" />
          }
        </button>
      </div>
    </div>
  )
}
