import { proxyWorkspaceDownload } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function GET(request: Request, { params }: { params: Promise<{ resource: string }> }) {
  const { resource } = await params;
  return proxyWorkspaceDownload(`workspace/export/${resource}/`, request);
}
