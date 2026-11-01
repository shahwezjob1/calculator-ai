from fastapi import FastAPI

from calculator_reviewer.core.exceptions.global_exception_handler import register_exception_handlers
from calculator_reviewer.core.logging_config import configure_logging
from calculator_reviewer.modules.review.controller.review_controller import router as review_router

configure_logging()
app = FastAPI(title="calculator-reviewer")

app.include_router(review_router, prefix="/api/v1")
register_exception_handlers(app)
