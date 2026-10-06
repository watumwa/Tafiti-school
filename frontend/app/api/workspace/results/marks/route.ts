import { proxyWorkspaceRequest } from '@/lib/workspace-server';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  return proxyWorkspaceRequest('workspace/results/marks/', request);
}

export async function POST(request: Request) {
  return proxyWorkspaceRequest('workspace/results/marks/', request);
}
