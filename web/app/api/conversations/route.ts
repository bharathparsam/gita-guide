import { NextResponse } from "next/server";
import { listConversations } from "@/lib/server/history";
import { createClient } from "@/lib/supabase/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.getUser();
    if (error || !data.user) {
      return NextResponse.json(
        { error: { code: "unauthorized", message: "Sign in to continue." } },
        { status: 401 },
      );
    }
    // Read through the caller's authenticated client so Supabase RLS remains
    // the authorization boundary. The service-role client is reserved for the
    // trusted write path that persists assistant messages and summaries.
    const conversations = await listConversations(supabase, data.user.id);
    return NextResponse.json(
      { conversations },
      { headers: { "Cache-Control": "private, no-store" } },
    );
  } catch {
    return NextResponse.json(
      { error: { code: "history_unavailable", message: "Conversation history is unavailable." } },
      { status: 503 },
    );
  }
}
