export function persistFileInLocalStorage(
  key: string,
  file: File,
  callback: (dataUrl: string) => void
) {
  const reader = new FileReader();
  reader.onload = () => {
    const dataUrl = reader.result as string;
    localStorage.setItem(key, dataUrl);
    callback(dataUrl);
  };
  reader.readAsDataURL(file);
}

// Expand 3‐digit hex to 6‐digit so <input type="color"> is happy
export function expandShortHex(hex: string): string {
  const m = hex.match(/^#([0-9a-fA-F])([0-9a-fA-F])([0-9a-fA-F])$/);
  if (m) {
    return "#" + m[1] + m[1] + m[2] + m[2] + m[3] + m[3];
  }
  return hex;
}
