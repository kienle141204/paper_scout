/**
 * Renders academic abstract text with:
 * - Inline math: $...$ rendered via KaTeX
 * - Display math: $$...$$ rendered as block
 * - Markdown: **bold**, *italic*, \n → paragraph breaks
 */
import katex from 'katex'
import 'katex/dist/katex.min.css'

interface Props {
  text: string
  style?: React.CSSProperties
  className?: string
}

function renderMath(src: string, display: boolean): string {
  try {
    return katex.renderToString(src, {
      displayMode: display,
      throwOnError: false,
      trust: false,
      strict: false,
    })
  } catch {
    return display ? `<div class="math-err">$$${src}$$</div>` : `<span class="math-err">$${src}$</span>`
  }
}

/** Convert a plain-text segment (no math) to HTML with bold/italic/newlines. */
function markdownToHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/gs, '<strong>$1</strong>')
    .replace(/\*([^*\n]+?)\*/g, '<em>$1</em>')
    .replace(/\n{2,}/g, '</p><p style="margin:0.75em 0 0">')
    .replace(/\n/g, '<br />')
}

/** Split text into alternating [text, math, text, math, …] segments. */
function parseSegments(raw: string): Array<{ type: 'text' | 'display' | 'inline'; content: string }> {
  const segments: Array<{ type: 'text' | 'display' | 'inline'; content: string }> = []
  // Match $$...$$ first (display), then $...$ (inline)
  const RE = /(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)/g
  let last = 0
  let m: RegExpExecArray | null

  while ((m = RE.exec(raw)) !== null) {
    if (m.index > last) {
      segments.push({ type: 'text', content: raw.slice(last, m.index) })
    }
    const matched = m[0]
    if (matched.startsWith('$$')) {
      segments.push({ type: 'display', content: matched.slice(2, -2).trim() })
    } else {
      segments.push({ type: 'inline', content: matched.slice(1, -1).trim() })
    }
    last = m.index + matched.length
  }

  if (last < raw.length) {
    segments.push({ type: 'text', content: raw.slice(last) })
  }

  return segments
}

export default function RichText({ text, style, className }: Props) {
  if (!text) return null

  const segments = parseSegments(text)

  const html = segments
    .map((seg) => {
      if (seg.type === 'display') return renderMath(seg.content, true)
      if (seg.type === 'inline') return renderMath(seg.content, false)
      return markdownToHtml(seg.content)
    })
    .join('')

  return (
    <p
      className={className}
      style={{ margin: 0, ...style }}
      // eslint-disable-next-line react/no-danger
      dangerouslySetInnerHTML={{ __html: `<p style="margin:0">${html}</p>` }}
    />
  )
}
