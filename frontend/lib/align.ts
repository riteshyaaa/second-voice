export type Part = { t: string; k: "same" | "del" | "add" };

/** LCS word alignment between original and proposed text. */
export function alignWords(original: string, proposed: string): Part[] {
  const a = original.split(/\s+/).filter(Boolean);
  const b = proposed.split(/\s+/).filter(Boolean);
  const m = a.length, n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--)
    for (let j = n - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const parts: Part[] = [];
  let i = 0, j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      parts.push({ t: a[i], k: "same" });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      parts.push({ t: a[i], k: "del" });
      i++;
    } else {
      parts.push({ t: b[j], k: "add" });
      j++;
    }
  }
  while (i < m) parts.push({ t: a[i++], k: "del" });
  while (j < n) parts.push({ t: b[j++], k: "add" });
  return parts;
}
