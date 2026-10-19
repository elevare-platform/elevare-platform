// The AI's assessment of an interview arrives as one block of text: a summary, then
// lists under headings such as "Strengths:" and "Weaknesses:", each item on a line
// starting with "- ". This splits it so the page can lay it out as a summary and lists.
//
//   "A confident communicator.\n\nStrengths:\n- Clear examples\n\nWeaknesses:\n- Light on numbers"
//   -> { summary: ['A confident communicator.'],
//        sections: [{ title: 'Strengths', items: ['Clear examples'] },
//                   { title: 'Weaknesses', items: ['Light on numbers'] }] }

export function parseAssessment(text) {
  const summary = []
  const sections = []
  if (!text) return { summary, sections }

  for (const block of text.split(/\n\s*\n/)) {
    const lines = block.split('\n').map((line) => line.trim()).filter(Boolean)
    if (lines.length === 0) continue

    const isHeading = /^[^-].*:$/.test(lines[0]) && lines.slice(1).every((l) => l.startsWith('- '))
    if (isHeading && lines.length > 1) {
      sections.push({
        title: lines[0].slice(0, -1),
        items: lines.slice(1).map((l) => l.slice(2).trim()),
      })
    } else {
      summary.push(lines.join(' '))
    }
  }
  return { summary, sections }
}
