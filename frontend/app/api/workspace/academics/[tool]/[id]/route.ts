import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function GET(request: Request, { params }: { params: Promise<{ tool: string; id: string }> }) {
  const { tool, id } = await params;
  return proxyWorkspaceRequest(`workspace/academics/${tool}/${id}/`, request);
}

export async function POST(request: Request, { params }: { params: Promise<{ tool: string; id: string }> }) {
  const { tool, id } = await params;
  return proxyWorkspaceRequest(`workspace/academics/${tool}/${id}/`, request);
}
