"""Matrix adapter routes."""

from fastapi import APIRouter

router = APIRouter(prefix="/adapters/matrix", tags=["adapters", "matrix"])


@router.get("/info")
async def get_matrix_info():
    return {
        "adapter": "matrix",
        "status": "ready",
        "message": "Matrix adapter is available",
    }


@router.get("/health")
async def health_check():
    return {"status": "healthy"}
