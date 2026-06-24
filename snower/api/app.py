from fastapi import FastAPI

from snower.api import paper, project

app = FastAPI(title="Snower API")
app.include_router(project.router)
app.include_router(paper.router)
