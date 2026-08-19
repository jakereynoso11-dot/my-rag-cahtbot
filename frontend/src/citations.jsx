import { visit } from "unist-util-visit";

// Powabase answers can include inline bracket citation markers like "[1]"
// referencing the `sources` list returned alongside the answer. This rehype
// plugin turns matches into small rounded <sup> badges after markdown has
// already been parsed, so it plays nicely with bold/lists/etc. instead of
// interfering with markdown syntax.
const MARKER_PATTERN = /\[(\d{1,2})\]/g;

export function rehypeCitationMarkers() {
  return (tree) => {
    visit(tree, "text", (node, index, parent) => {
      if (!parent || index == null || !node.value.includes("[")) return;

      MARKER_PATTERN.lastIndex = 0;
      const parts = [];
      let lastIndex = 0;
      let match;
      let matched = false;

      while ((match = MARKER_PATTERN.exec(node.value)) !== null) {
        matched = true;
        if (match.index > lastIndex) {
          parts.push({ type: "text", value: node.value.slice(lastIndex, match.index) });
        }
        parts.push({
          type: "element",
          tagName: "sup",
          properties: { className: ["citation-marker"] },
          children: [{ type: "text", value: match[1] }],
        });
        lastIndex = match.index + match[0].length;
      }
      if (!matched) return;
      if (lastIndex < node.value.length) {
        parts.push({ type: "text", value: node.value.slice(lastIndex) });
      }
      parent.children.splice(index, 1, ...parts);
      return index + parts.length;
    });
  };
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
