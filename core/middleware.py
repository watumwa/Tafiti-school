import time

from django.db import connections
from django.shortcuts import redirect

from core.settings import common


class DatabaseConnectionCleanupMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except Exception:
            connections.close_all()
            raise

        if getattr(response, "_db_connections_wrapped", False):
            return response

        original_close = response.close

        def close_response():
            try:
                return original_close()
            finally:
                connections.close_all()

        response.close = close_response
        response._db_connections_wrapped = True
        return response

class AutoLogoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = time.time()
            raw_last_activity = request.session.get('last_activity')

            try:
                last_activity = float(raw_last_activity) if raw_last_activity is not None else None
            except (TypeError, ValueError):
                last_activity = None

            if last_activity is None:
                request.session['last_activity'] = now
            else:
                # Calculate elapsed time
                elapsed_time = now - last_activity

                # If inactive for more than SESSION_COOKIE_AGE, log out the user
                if elapsed_time > common.SESSION_COOKIE_AGE:
                    request.session.flush()  # Clears session (logs out the user)
                    return redirect('login')  # Redirect to login page

                # Avoid rewriting the session row on every request when users are active.
                if elapsed_time >= common.SESSION_ACTIVITY_SAVE_EVERY:
                    request.session['last_activity'] = now

        response = self.get_response(request)
        return response
