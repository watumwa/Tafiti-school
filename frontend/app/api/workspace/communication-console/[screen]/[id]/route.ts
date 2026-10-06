import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function GET(request: Request, { params }: { params: Promise<{ screen: string; id: string }> }) {
  const { screen, id } = await params;
  return proxyWorkspaceRequest(`workspace/communication-console/${screen}/${id}/`, request);
}

export async function POST(request: Request, { params }: { params: Promise<{ screen: string; id: string }> }) {
  const { screen, id } = await params;
  return proxyWorkspaceRequest(`workspace/communication-console/${screen}/${id}/`, request);
}
