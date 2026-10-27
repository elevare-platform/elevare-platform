// The word "AI" is kept out of what employers, candidates and the public read (docs/08_DECISIONS.md,
// item 45). Candidates are still told plainly that an automated system assesses their answers and
// that a person decides (lib/interviewRules.js); that is said without the word. This scans the
// source so it does not creep back. Left out on purpose: staff-only admin screens, the privacy
// policy (its statement that data is not used to train AI/ML models has to say so), code comments,
// and the places where "AI" is a stored value or a speaker label, never shown as text.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { describe, expect, it } from 'vitest'

const ROOT = join(import.meta.dirname, '.')
const SKIPPED_FILES = [/pages\/admin\//, /components\/admin\//, /pages\/PrivacyPage\.jsx$/]
const DATA_USES = [
  /source\s*===\s*'AI'/,
  /speaker\s*===\s*'AI'/,
  /role:\s*'AI'/,
  /'AI'\s*\|\s*'Candidate'/,
  /AI_INTERVIEW/,
]

function sourceFiles(directory) {
  return readdirSync(directory).flatMap((name) => {
    const path = join(directory, name)
    if (statSync(path).isDirectory()) return sourceFiles(path)
    return /\.(jsx?|mjs)$/.test(name) && !/\.test\./.test(name) ? [path] : []
  })
}

function visibleLines(path) {
  return readFileSync(path, 'utf8')
    .split('\n')
    .map((text, index) => ({ text, number: index + 1 }))
    .filter(({ text }) => !/^\s*(\/\/|\*|\/\*|\{\/\*)/.test(text))
    .map(({ text, number }) => ({ text: text.replace(/(^|[^:'"`])\s\/\/\s.*$/, '$1'), number }))
}

describe('the wording of what people read', () => {
  it('never says AI outside the staff screens, the privacy policy and the places where it is only a value', () => {
    const found = []
    for (const path of sourceFiles(ROOT)) {
      const name = relative(ROOT, path)
      if (SKIPPED_FILES.some((pattern) => pattern.test(name))) continue
      for (const { text, number } of visibleLines(path)) {
        if (/\bAI\b/.test(text) && !DATA_USES.some((pattern) => pattern.test(text))) {
          found.push(`${name}:${number}: ${text.trim().slice(0, 100)}`)
        }
      }
    }

    expect(found).toEqual([])
  })
})
