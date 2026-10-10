import os

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from app.services.library_automation import accrue_overdue_library_fines
from app.services.outbound_messages import process_outbound_messages


class MaintenanceAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def _authorized(self, request):
        expected = str(os.environ.get("CRON_SECRET") or "").strip()
        supplied = str(request.headers.get("Authorization") or "").strip()
        return bool(expected and supplied == f"Bearer {expected}")

    def get(self, request, job: str):
        if not self._authorized(request):
            return Response({"detail": "Maintenance authentication failed."}, status=status.HTTP_401_UNAUTHORIZED)

        if job == "library-daily":
            return Response({"job": job, **accrue_overdue_library_fines(actor=None)})
        if job == "outbound":
            limit = request.query_params.get("limit", "100")
            try:
                parsed_limit = max(1, min(int(limit), 500))
            except (TypeError, ValueError):
                parsed_limit = 100
            return Response({"job": job, **process_outbound_messages(limit=parsed_limit)})
        return Response({"detail": "Unknown maintenance job."}, status=status.HTTP_404_NOT_FOUND)
