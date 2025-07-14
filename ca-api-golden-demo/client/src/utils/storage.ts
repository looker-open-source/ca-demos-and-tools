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
