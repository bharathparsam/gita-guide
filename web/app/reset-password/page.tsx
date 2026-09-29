import { redirect } from "next/navigation";
import { ResetPasswordForm } from "@/components/reset-password-form";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function ResetPasswordPage() {
  try {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.getUser();
    if (!error && data.user) return <ResetPasswordForm />;
  } catch {
    // The login page provides a safe recovery path when auth is unavailable.
  }
  redirect("/login?auth_error=The+recovery+link+is+invalid+or+has+expired");
}
