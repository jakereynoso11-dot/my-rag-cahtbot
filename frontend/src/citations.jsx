// Powabase answers can include inline bracket citation markers like "[1]"
// referencing the `sources` list returned alongside the answer. Rendered as
// plain text these look like stray brackets; this turns them into small
// rounded badges and renders a clean numbered source list underneath.

const MARKER_PATTERN = /\[(\d{1,2})\]/g;

export function renderCitedText(text) {
  if (!text) return text;
  const parts = [];
  let lastIndex = 0;
  let match;
  let key = 0;

  MARKER_PATTERN.lastIndex = 0;
  while ((match = MARKER_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <span className="citation-marker" key={`citation-${key++}`}>
        {match[1]}
      </span>
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }
  return parts.length ? parts : text;
}

export function citationLabel(source, index) {
  if (typeof source === "string") return source;
  if (source && typeof source === "object") {
    const label =
      source.title ||
      source.name ||
      source.filename ||
      source.source_name ||
      source.document_name ||
      source.file_name;
    if (label) return label;
  }
  return `Source ${index + 1}`;
}
