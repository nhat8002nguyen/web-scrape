/**
 * WebVTT → plain text (cue body lines; strip tags).
 * @param {string} raw
 */
export function vttToPlainText(raw) {
  if (!raw || typeof raw !== "string") return "";
  const text = raw.replace(/^\uFEFF/, "");
  const blocks = text.split(/\n{2,}/);
  /** @type {string[]} */
  const segments = [];

  for (const block of blocks) {
    const lines = block.split(/\r?\n/).map((l) => l.trim());
    const nonEmpty = lines.filter((l) => l.length > 0);
    if (!nonEmpty.length) continue;
    if (nonEmpty[0] === "WEBVTT" || nonEmpty[0].startsWith("WEBVTT ")) continue;
    if (nonEmpty[0].startsWith("NOTE") || nonEmpty[0].startsWith("STYLE")) continue;

    const arrowIdx = nonEmpty.findIndex((l) => l.includes("-->"));
    if (arrowIdx === -1) continue;

    const arrowLine = nonEmpty[arrowIdx];
    const afterArrow = arrowLine.split("-->", 2)[1]?.trim() ?? "";
    const afterParts = afterArrow.split(/\s+/);
    let k = 0;
    while (k < afterParts.length && /^[\d:.]+$/.test(afterParts[k])) k += 1;
    const inline = afterParts
      .slice(k)
      .join(" ")
      .replace(/<[^>]+>/g, "")
      .trim();
    if (inline) segments.push(inline);

    for (let i = arrowIdx + 1; i < nonEmpty.length; i += 1) {
      const line = nonEmpty[i];
      if (/^\d+$/.test(line)) continue;
      const plain = line.replace(/<[^>]+>/g, "").trim();
      if (plain) segments.push(plain);
    }
  }

  return segments.join(" ").replace(/\s+/g, " ").trim();
}
