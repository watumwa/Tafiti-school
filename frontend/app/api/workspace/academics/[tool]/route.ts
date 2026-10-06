import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function GET(request: Request, { params }: { params: Promise<{ tool: string }> }) {
  const { tool } = await params;
  return proxyWorkspaceRequest(`workspace/academics/${tool}/`, request);
}

export async function POST(request: Request, { params }: { params: Promise<{ tool: string }> }) {
  const { tool } = await params;
  return proxyWorkspaceRequest(`workspace/academics/${tool}/`, request);
}
