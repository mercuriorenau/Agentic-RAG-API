const UUID_FILENAME =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(pdf|txt|md)$/i;

const FRIENDLY_BY_EXT: Record<string, string> = {
  pdf: "Uploaded PDF",
  txt: "Uploaded text",
  md: "Uploaded markdown",
};

/** Prefer a human label when a citation/doc name is a bare storage UUID. */
export function displayDocumentName(filename: string | null | undefined): string {
  const name = (filename || "").trim() || "upload";
  const match = UUID_FILENAME.exec(name);
  if (!match) {
    return name;
  }
  const ext = match[1].toLowerCase();
  return FRIENDLY_BY_EXT[ext] || `Uploaded ${ext}`;
}

/** Chat title from an upload: basename without the final extension. */
export function chatTitleFromFilename(filename: string | null | undefined): string {
  const base = displayDocumentName(filename).split(/[/\\]/).pop()?.trim() || "upload";
  const stem = base.replace(/\.[^.]+$/, "").trim();
  return (stem || base).slice(0, 200);
}
