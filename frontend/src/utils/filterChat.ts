import type { Paper } from '../types/paper'
import type { ChatFilterParams } from '../types/chat'

/**
 * Apply filter params returned by the chat agent to the current paper list.
 * Pure function — no side effects.
 *
 * Returns `{ papers, warning }`:
 *   - `papers` is the filtered list (falls back to the original if filtering yields 0 results)
 *   - `warning` is a non-null message when the fallback was triggered
 */
export function applyFilterParams(
  papers: Paper[],
  params: ChatFilterParams,
): { papers: Paper[]; warning: string | null } {
  let result = [...papers]

  // 1. Year range
  if (params.year_from != null) {
    result = result.filter((p) => p.year == null || p.year >= params.year_from!)
  }
  if (params.year_to != null) {
    result = result.filter((p) => p.year == null || p.year <= params.year_to!)
  }

  // 2. Venue filter (override)
  if (params.venues != null && params.venues.length > 0) {
    const venueSet = new Set(params.venues.map((v) => v.toUpperCase()))
    result = result.filter((p) => p.conf != null && venueSet.has(p.conf.toUpperCase()))
  }

  // 3. Exclude keywords — remove papers whose title or abstract contains any excluded term
  if (params.exclude_keywords.length > 0) {
    const excludeLower = params.exclude_keywords.map((k) => k.toLowerCase())
    result = result.filter((p) => {
      const haystack = `${p.titleEn} ${p.abstractEn ?? ''}`.toLowerCase()
      return !excludeLower.some((kw) => haystack.includes(kw))
    })
  }

  // 4. Include-only keywords — keep only papers that match at least one term
  if (params.include_only_keywords.length > 0) {
    const includeLower = params.include_only_keywords.map((k) => k.toLowerCase())
    result = result.filter((p) => {
      const haystack = `${p.titleEn} ${p.abstractEn ?? ''}`.toLowerCase()
      return includeLower.some((kw) => haystack.includes(kw))
    })
  }

  // Fallback: if filter is too strict, return original list with a warning
  if (result.length === 0 && papers.length > 0) {
    return {
      papers,
      warning:
        'Không tìm thấy paper nào khớp với bộ lọc. Đang hiển thị lại toàn bộ kết quả trước đó.',
    }
  }

  return { papers: result, warning: null }
}
