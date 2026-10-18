import asyncio
from functools import wraps


def async_celery_task(celery_app, **celery_kwargs):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # If there is already an event loop, use it
                loop = asyncio.get_event_loop()
                if loop.is_closed():
                    # If the loop is closed, create a new one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
            except RuntimeError:
                # In case there's no event loop in the current context, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            try:
                # Run the async function using the event loop
                result = loop.run_until_complete(func(*args, **kwargs))
            finally:
                # Only close the loop if we created it
                if loop.is_running():
                    loop.close()

            return result
        return celery_app.task(**celery_kwargs)(wrapper)
    return decorator


