import { ChatApp } from "@/components/chat-app";
import { cookies } from "next/headers";
import { hasSupabaseAuthCookie } from "@/lib/server/auth-cookie";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function Home() {
  const cookieHeader = (await cookies()).getAll().map(({ name, value }) => `${name}=${value}`).join("; ");
  if (!hasSupabaseAuthCookie(cookieHeader)) return <ChatApp user={null} />;
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    if (data.user) {
      return <ChatApp user={{ id: data.user.id, email: data.user.email || "Signed-in user" }} />;
    }
  } catch {
    // Authentication is optional. Missing Supabase configuration falls back to
    // an in-memory guest session instead of blocking access to the guide.
  }
  return <ChatApp user={null} />;
}
