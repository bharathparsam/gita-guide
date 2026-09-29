export function hasSupabaseAuthCookie(
  cookieHeader: string | null,
  supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL,
): boolean {
  if (!cookieHeader || !supabaseUrl) return false;
  let projectRef: string;
  try {
    projectRef = new URL(supabaseUrl).hostname.split(".")[0];
  } catch {
    return false;
  }
  if (!projectRef) return false;
  const authCookie = `sb-${projectRef}-auth-token`;
  return cookieHeader.split(";").some((entry) => {
    const name = entry.trim().split("=", 1)[0];
    return name === authCookie || name.startsWith(`${authCookie}.`);
  });
}
