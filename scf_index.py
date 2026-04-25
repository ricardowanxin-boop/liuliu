"""Root Tencent Cloud SCF wrapper.

Tencent Cloud's console commonly asks for a handler like
`scf_index.main_handler`. Keep this tiny wrapper at the repository root so the
real FastAPI adapter can stay inside `backend/`.
"""

from backend.scf_index import main_handler


__all__ = ["main_handler"]
