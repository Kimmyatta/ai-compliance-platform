function sanitizeFilename(value: string) {
  return value
    .replace(/\.[^/.]+$/, "")
    .replace(/[^a-z0-9_-]+/gi, "_")
    .replace(/^_+|_+$/g, "")
    .toLowerCase();
}

export function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  downloadBlob(`${sanitizeFilename(filename)}.json`, blob);
}

export function downloadText(filename: string, text: string) {
  const blob = new Blob([text], {
    type: "text/plain;charset=utf-8",
  });
  downloadBlob(`${sanitizeFilename(filename)}.txt`, blob);
}

function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
