from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from snower.api import paper, project, review

app = FastAPI(title="Snower API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(project.router)
app.include_router(paper.router)
app.include_router(review.router)
