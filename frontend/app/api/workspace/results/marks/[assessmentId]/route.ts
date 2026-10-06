import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function GET(request: Request, { params }: { params: Promise<{ assessmentId: string }> }) {
  const { assessmentId } = await params;
  return proxyWorkspaceRequest(`workspace/results/marks/${assessmentId}/`, request);
}

export async function POST(request: Request, { params }: { params: Promise<{ assessmentId: string }> }) {
  const { assessmentId } = await params;
  return proxyWorkspaceRequest(`workspace/results/marks/${assessmentId}/`, request);
}
