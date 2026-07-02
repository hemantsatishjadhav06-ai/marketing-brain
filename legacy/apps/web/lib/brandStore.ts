// Tiny localStorage-backed "selected brand" store. The spec demands brands
// be fully isolated; the selected brand ID is what every page passes as the
// brand_id query parameter to the backend.

const KEY = "mb_selected_brand";

export function getSelectedBrand(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(KEY);
}

export function setSelectedBrand(id: string) {
  localStorage.setItem(KEY, id);
  // tell other tabs/components
  window.dispatchEvent(new StorageEvent("storage", { key: KEY, newValue: id }));
}
