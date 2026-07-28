import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.auth import (
    COOKIE_NAME,
    authenticate,
    csrf_token,
    current_admin,
    ensure_default_admin,
    make_session,
    valid_csrf,
)
from app.database import init_db
from app.services import (
    ValidationError,
    change_points,
    create_or_update_customer,
    customer_history,
    get_customer,
    get_customer_by_phone,
    list_customers,
    stats,
    update_customer,
)

load_dotenv()
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_default_admin()
    yield


app = FastAPI(title="The Open Store Loyalty", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def page(request: Request, name: str, **context):
    context.update(
        request=request,
        admin=current_admin(request),
        csrf=csrf_token(request),
        business_url="https://linktr.ee/theopenstore",
    )
    return templates.TemplateResponse(request, name, context)


def require_admin(request: Request):
    admin = current_admin(request)
    if not admin:
        raise HTTPException(status_code=303, headers={"Location": "/?login=required"})
    return admin


def redirect(path: str, message: str = "", error: str = ""):
    params = []
    if message:
        params.append("message=" + quote(message))
    if error:
        params.append("error=" + quote(error))
    return RedirectResponse(path + (("?" + "&".join(params)) if params else ""), 303)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, phone: str = "", login: str = "", error: str = ""):
    customer = None
    lookup_error = ""
    if phone:
        try:
            customer = get_customer_by_phone(phone)
            if not customer:
                lookup_error = "No customer was found with that phone number."
        except ValidationError as exc:
            lookup_error = str(exc)
    return page(
        request,
        "home.html",
        phone=phone,
        customer=customer,
        lookup_error=lookup_error,
        login_required=login == "required",
        login_error=error,
    )


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf: str = Form(...),
):
    if not valid_csrf(request, csrf):
        return redirect("/", error="Your form expired. Please try again.")
    admin = authenticate(username, password)
    if not admin:
        return redirect("/", error="Incorrect username or password.")
    response = RedirectResponse("/admin", 303)
    response.set_cookie(
        COOKIE_NAME,
        make_session(admin),
        httponly=True,
        secure=os.getenv("COOKIE_SECURE", "false").lower() == "true",
        samesite="lax",
        max_age=int(os.getenv("SESSION_HOURS", "12")) * 3600,
    )
    return response


@app.post("/logout")
def logout(request: Request, csrf: str = Form(...)):
    if not valid_csrf(request, csrf):
        return redirect("/", error="Invalid request.")
    response = RedirectResponse("/", 303)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/admin", response_class=HTMLResponse)
def dashboard(request: Request, q: str = "", message: str = "", error: str = ""):
    require_admin(request)
    return page(
        request,
        "dashboard.html",
        customers=list_customers(q),
        q=q,
        stats=stats(),
        message=message,
        error=error,
    )


@app.post("/admin/customers")
def save_customer(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    csrf: str = Form(...),
):
    require_admin(request)
    if not valid_csrf(request, csrf):
        return redirect("/admin", error="Your form expired. Please try again.")
    try:
        customer, created = create_or_update_customer(name, phone)
        action = "created" if created else "updated"
        return redirect(f"/admin/customers/{customer['id']}", f"Customer {action}.")
    except ValidationError as exc:
        return redirect("/admin", error=str(exc))


@app.get("/admin/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail(
    request: Request, customer_id: int, message: str = "", error: str = ""
):
    require_admin(request)
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(404)
    return page(
        request,
        "customer.html",
        customer=customer,
        history=customer_history(customer_id),
        message=message,
        error=error,
    )


@app.post("/admin/customers/{customer_id}/edit")
def edit_customer(
    request: Request,
    customer_id: int,
    name: str = Form(...),
    phone: str = Form(...),
    csrf: str = Form(...),
):
    require_admin(request)
    if not valid_csrf(request, csrf):
        return redirect(f"/admin/customers/{customer_id}", error="Invalid request.")
    try:
        update_customer(customer_id, name, phone)
        return redirect(f"/admin/customers/{customer_id}", "Customer details updated.")
    except ValidationError as exc:
        return redirect(f"/admin/customers/{customer_id}", error=str(exc))


@app.post("/admin/customers/{customer_id}/points")
def points(
    request: Request,
    customer_id: int,
    amount: int = Form(...),
    note: str = Form(""),
    csrf: str = Form(...),
):
    admin = require_admin(request)
    if not valid_csrf(request, csrf):
        return redirect(f"/admin/customers/{customer_id}", error="Invalid request.")
    try:
        change_points(customer_id, amount, note, f"web:{admin['username']}")
        return redirect(f"/admin/customers/{customer_id}", "Points updated.")
    except ValidationError as exc:
        return redirect(f"/admin/customers/{customer_id}", error=str(exc))


@app.get("/health")
def health():
    return {"status": "ok"}

