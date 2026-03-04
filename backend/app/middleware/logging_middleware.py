import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

logger = logging.getLogger(__name__)


class RequestResponseLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Log request details
        logger.info(f">>> REQUEST: {request.method} {request.url}")
        logger.info(f"    Client: {request.client.host if request.client else 'unknown'}")
        logger.info(f"    Headers: {dict(request.headers)}")

        # Log request body for POST/PUT/PATCH (avoid logging file uploads)
        if request.method in ["POST", "PUT", "PATCH"]:
            content_type = request.headers.get("content-type", "")

            # Only log JSON requests, skip multipart (file uploads)
            if "application/json" in content_type:
                try:
                    body = await request.body()
                    body_str = body.decode('utf-8')
                    # Limit body logging to 2000 chars to avoid huge logs
                    if len(body_str) > 2000:
                        logger.info(f"    Body: {body_str[:2000]}... (truncated)")
                    else:
                        logger.info(f"    Body: {body_str}")
                except Exception as e:
                    logger.warning(f"    Body: <unable to read: {e}>")
            elif "multipart/form-data" in content_type:
                logger.info("    Body: <multipart file upload>")

        # Process request and handle errors
        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log response
            logger.info(
                f"<<< RESPONSE: {request.method} {request.url} | "
                f"Status: {response.status_code} | "
                f"Duration: {duration:.3f}s"
            )

            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"<<< ERROR: {request.method} {request.url} | "
                f"Duration: {duration:.3f}s | "
                f"Error: {str(e)}",
                exc_info=True
            )
            raise
