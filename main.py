from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import helper
app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
config = helper.readYaml("config.yaml")
@app.get("/")
def root(request: Request, lang: str = "ua"):
    return templates.TemplateResponse("main.html", {
        "request": request,
        "t": helper.getLanguageMetadata(lang),
        "price": config.get("check_price", 0),
        "on_site_visit": config.get("on_site_visit", {}),
        "check_list": config.get("check_list", []),
        "languages": config.get("languages", {}),
    })