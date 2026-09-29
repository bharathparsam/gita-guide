import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { AuthForm } from "@/components/auth-form";
import { hasSupabaseAuthCookie } from "@/lib/server/auth-cookie";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function Login({ searchParams }: { searchParams: Promise<{ auth_error?: string }> }) {
  const params = await searchParams;
  let signedIn = false;
  const cookieHeader = (await cookies()).getAll().map(({ name, value }) => `${name}=${value}`).join("; ");
  if (!hasSupabaseAuthCookie(cookieHeader)) return <AuthForm initialError={params.auth_error} />;
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    signedIn = Boolean(data.user);
  } catch {
    return <AuthForm initialError="Sign-in is not configured yet. You can continue as a guest." />;
  }
  if (signedIn) redirect("/");
  return <AuthForm initialError={params.auth_error} />;
}
