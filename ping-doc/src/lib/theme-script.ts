// Runs in <head> before first paint so the page never flashes the wrong theme.
export const THEME_SCRIPT = `try{var t=localStorage.getItem("pingie-docs-theme")||(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");document.documentElement.dataset.theme=t}catch(e){}`;
