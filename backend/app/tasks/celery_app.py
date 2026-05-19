# Celery is disabled in container-free local mode.
# Using standard FastAPI BackgroundTasks instead.
class CeleryMock:
    def task(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator

celery_app = CeleryMock()
