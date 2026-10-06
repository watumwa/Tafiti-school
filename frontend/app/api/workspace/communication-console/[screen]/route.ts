import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function GET(request: Request, { params }: { params: Promise<{ screen: string }> }) {
  const { screen } = await params;
  return proxyWorkspaceRequest(`workspace/communication-console/${screen}/`, request);
}

export async function POST(request: Request, { params }: { params: Promise<{ screen: string }> }) {
  const { screen } = await params;
  return proxyWorkspaceRequest(`workspace/communication-console/${screen}/`, request);
}
