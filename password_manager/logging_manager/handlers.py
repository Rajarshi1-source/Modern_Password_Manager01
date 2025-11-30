import logging

class DatabaseLogHandler(logging.Handler):
    def emit(self, record):
        try:
            # Import model here instead of at the top of the file
            from .models import SystemLog
            
            # Extract request details if available
            request = getattr(record, 'request', None)
            user = None
            ip_address = None
            user_agent = ''
            request_path = ''
            request_method = ''
            
            if request:
                user = request.user if hasattr(request, 'user') and request.user.is_authenticated else None
                ip_address = request.META.get('REMOTE_ADDR')
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                request_path = request.path
                request_method = request.method
            
            SystemLog.objects.create(
                level=record.levelname,
                logger_name=record.name,
                message=self.format(record),
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                request_path=request_path,
                request_method=request_method
            )
        except Exception:
            # Avoid infinite recursion if logging fails
            pass
