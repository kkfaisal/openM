// Word-level diff (LCS) for showing what a recommendation changes.

export interface DiffPart {
  text: string;
  kind: "same" | "add" | "del";
}

export function wordDiff(before: string, after: string): DiffPart[] {
  const a = before.split(/(\s+)/).filter(Boolean);
  const b = after.split(/(\s+)/).filter(Boolean);
  // Guard against pathological sizes — fall back to a whole replacement.
  if (a.length * b.length > 250_000) {
    return [
      { text: before, kind: "del" },
      { text: after, kind: "add" },
    ];
  }
  const dp: number[][] = Array.from({ length: a.length + 1 }, () =>
    new Array(b.length + 1).fill(0)
  );
  for (let i = a.length - 1; i >= 0; i--) {
    for (let j = b.length - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: DiffPart[] = [];
  const push = (text: string, kind: DiffPart["kind"]) => {
    const last = out[out.length - 1];
    if (last && last.kind === kind) last.text += text;
    else out.push({ text, kind });
  };
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      push(a[i], "same");
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push(a[i++], "del");
    } else {
      push(b[j++], "add");
    }
  }
  while (i < a.length) push(a[i++], "del");
  while (j < b.length) push(b[j++], "add");
  return out;
}

/** Dice similarity of the two texts (0–1), by non-whitespace characters. */
export function similarity(parts: DiffPart[]): number {
  let same = 0;
  let changed = 0;
  for (const p of parts) {
    const n = p.text.replace(/\s+/g, "").length;
    if (p.kind === "same") same += n;
    else changed += n;
  }
  // old = same + del, new = same + add  →  2·same / (old + new)
  const denom = 2 * same + changed;
  return denom ? (2 * same) / denom : 1;
}
