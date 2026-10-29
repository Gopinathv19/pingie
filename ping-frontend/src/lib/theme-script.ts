export const THEME_KEY = "pingie-theme";
export const DEFAULT_THEME_PREF = "dark";

// Runs in <head> before first paint so the page never flashes the wrong theme.
export const THEME_SCRIPT = `try{var p=localStorage.getItem("${THEME_KEY}")||"${DEFAULT_THEME_PREF}";var t=p==="system"?(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"):p;document.documentElement.dataset.theme=t}catch(e){}`;
