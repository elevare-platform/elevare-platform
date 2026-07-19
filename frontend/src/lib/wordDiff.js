// Minimal word-level diff (LCS-based) for highlighting AI suggestion changes.
// No external dependency — good enough for short-to-medium job description text.

export function wordDiff(oldText, newText) {
  const a = oldText.split(/(\s+)/).filter((t) => t !== '')
  const b = newText.split(/(\s+)/).filter((t) => t !== '')

  const m = a.length
  const n = b.length
  const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))

  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const ops = []
  let i = 0
  let j = 0
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      ops.push({ type: 'same', value: a[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push({ type: 'removed', value: a[i] })
      i++
    } else {
      ops.push({ type: 'added', value: b[j] })
      j++
    }
  }
  while (i < m) { ops.push({ type: 'removed', value: a[i] }); i++ }
  while (j < n) { ops.push({ type: 'added', value: b[j] }); j++ }

  return ops
}
