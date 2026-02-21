import os
import hashlib
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.files.storage import FileSystemStorage

from .models import Staff

SECRET_ACCESS_CODE = os.environ.get("STAFF_SECRET_CODE", "ARKONIX2025")

ROLE_CODES = {
    "admin123":   "admin",
    "bclead123":  "backend_lead",
    "frlead123":  "frontend_lead",
    # ── Универсальный код для обычных сотрудников ──
    "ARKONIX_2025": "staff",
    "ARKONIX2025":  "staff",   # без подчёркивания
}

LEAD_ACCOUNTS = {
    "backend_lead":  hashlib.sha256("bclead_pass".encode()).hexdigest(),
    "frontend_lead": hashlib.sha256("frlead_pass".encode()).hexdigest(),
}

BACKUP_LEAD_CODE = "bclead123"

BACKEND_SERVICES = [
    "webapp",
    "bot",
    "ai",
    "Веб-додатки",
    "Telegram-боти",
    "AI та автоматизація",
    "веб-додаток",
]
FRONTEND_SERVICES = [
    "website",
    "Розробка сайтів",
    "Розробка сайту",
    "сайт",
]


def login_staff_step1(request):
    if request.method == "POST":
        login_input = request.POST.get("login", "").strip()
        password    = request.POST.get("password", "").strip()
        hashed      = hashlib.sha256(password.encode()).hexdigest()

        # Резервный вход лида по коду
        if login_input == BACKUP_LEAD_CODE and password == BACKUP_LEAD_CODE:
            request.session["staff_login_pending"] = "backend_lead"
            request.session["is_lead_login"]       = True
            request.session["backup_lead_auth"]    = True
            return redirect("login_staff_step2")

        # Вход лидов по логину + паролю
        if login_input in LEAD_ACCOUNTS:
            if LEAD_ACCOUNTS[login_input] == hashed:
                request.session["staff_login_pending"] = login_input
                request.session["is_lead_login"]       = True
                return redirect("login_staff_step2")
            else:
                messages.error(request, "Невірний логін або пароль.")
                return render(request, "login_staff.html", {"step": 1})

        # Обычный сотрудник — поиск в БД
        try:
            staff = Staff.objects.get(login=login_input, password=hashed)
        except Staff.DoesNotExist:
            messages.error(request, "Невірний логін або пароль.")
            return render(request, "login_staff.html", {"step": 1})

        request.session["staff_login_pending"] = staff.pk
        request.session["is_lead_login"]       = False
        return redirect("login_staff_step2")

    return render(request, "login_staff.html", {"step": 1})


def login_staff_step2(request):
    if "staff_login_pending" not in request.session:
        return redirect("login_staff_step1")

    if request.method == "POST":
        code = request.POST.get("secret_code", "").strip()

        # ── Резервный лид-вход ──
        is_backup = request.session.get("backup_lead_auth", False)
        if is_backup and code == BACKUP_LEAD_CODE:
            request.session.pop("backup_lead_auth", None)
            request.session.pop("staff_login_pending", None)
            request.session.pop("is_lead_login", None)
            request.session["staff_id"]      = "backend_lead"
            request.session["is_staff_auth"] = True
            request.session["staff_role"]    = "backend_lead"
            request.session["user_id"]       = "backend_lead"
            return redirect("team_lead_panel")

        # ── Определяем роль по коду ──
        role = ROLE_CODES.get(code)

        if not role:
            messages.error(request, "Невірний секретний код доступу.")
            return render(request, "login_staff.html", {"step": 2})

        pending = request.session.pop("staff_login_pending")
        request.session.pop("is_lead_login", None)
        request.session.pop("backup_lead_auth", None)

        request.session["staff_id"]      = pending
        request.session["is_staff_auth"] = True
        request.session["staff_role"]    = role
        request.session["user_id"]       = pending

        # Лиды и админы → панель лида, остальные → профиль сотрудника
        if role in ("backend_lead", "frontend_lead", "admin"):
            return redirect("team_lead_panel")

        return redirect("staff_profile")

    return render(request, "login_staff.html", {"step": 2})


def logout_staff(request):
    for key in ("staff_id", "is_staff_auth", "staff_role", "user_id", "is_admin"):
        request.session.pop(key, None)
    return redirect("home")


# ══════════════════════════════════════════════
#  РЕГИСТРАЦИЯ СОТРУДНИКА
# ══════════════════════════════════════════════

def register_staff_step1(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name", "").strip()
        last_name  = request.POST.get("last_name", "").strip()
        if not first_name or not last_name:
            messages.error(request, "Введіть ім'я та прізвище.")
            return render(request, "register_staff.html", {"step": 1})
        request.session["staff_reg"] = {
            "first_name": first_name,
            "last_name":  last_name,
        }
        return redirect("register_staff_step2")
    return render(request, "register_staff.html", {"step": 1})


def register_staff_step2(request):
    if "staff_reg" not in request.session:
        return redirect("register_staff_step1")
    if request.method == "POST":
        position = request.POST.get("position", "").strip()
        if not position:
            messages.error(request, "Введіть посаду.")
            return render(request, "register_staff.html", {"step": 2})
        request.session["staff_reg"]["position"] = position
        request.session.modified = True
        return redirect("register_staff_step3")
    return render(request, "register_staff.html", {"step": 2})


def register_staff_step3(request):
    if "staff_reg" not in request.session:
        return redirect("register_staff_step1")
    if request.method == "POST":
        login   = request.POST.get("login", "").strip()
        password = request.POST.get("password", "").strip()
        confirm  = request.POST.get("confirm", "").strip()
        if not login or not password:
            messages.error(request, "Заповніть усі поля.")
            return render(request, "register_staff.html", {"step": 3})
        if password != confirm:
            messages.error(request, "Паролі не збігаються.")
            return render(request, "register_staff.html", {"step": 3})
        if Staff.objects.filter(login=login).exists():
            messages.error(request, "Цей логін вже зайнятий.")
            return render(request, "register_staff.html", {"step": 3})
        hashed = hashlib.sha256(password.encode()).hexdigest()
        request.session["staff_reg"]["login"]    = login
        request.session["staff_reg"]["password"] = hashed
        request.session.modified = True
        return redirect("register_staff_step4")
    return render(request, "register_staff.html", {"step": 3})


def register_staff_step4(request):
    if "staff_reg" not in request.session:
        return redirect("register_staff_step1")
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        if not email or "@" not in email:
            messages.error(request, "Введіть коректний email.")
            return render(request, "register_staff.html", {"step": 4})
        request.session["staff_reg"]["email"] = email
        request.session.modified = True
        return redirect("register_staff_step5")
    return render(request, "register_staff.html", {"step": 4})


def register_staff_step5(request):
    if "staff_reg" not in request.session:
        return redirect("register_staff_step1")
    if request.method == "POST":
        code = request.POST.get("secret_code", "").strip()
        if code != SECRET_ACCESS_CODE:
            messages.error(request, "Невірний секретний код доступу.")
            return render(request, "register_staff.html", {"step": 5})
        request.session["staff_reg"]["code_ok"] = True
        request.session.modified = True
        return redirect("register_staff_step6")
    return render(request, "register_staff.html", {"step": 5})


def register_staff_step6(request):
    if "staff_reg" not in request.session or not request.session["staff_reg"].get("code_ok"):
        return redirect("register_staff_step1")
    if request.method == "POST":
        contract = request.FILES.get("contract")
        if not contract:
            messages.error(request, "Завантажте договір.")
            return render(request, "register_staff.html", {"step": 6})

        fs   = FileSystemStorage(location="media/contracts/")
        name = fs.save(contract.name, contract)

        data  = request.session["staff_reg"]
        staff = Staff.objects.create(
            first_name    = data["first_name"],
            last_name     = data["last_name"],
            position      = data["position"],
            login         = data["login"],
            password      = data["password"],
            email         = data["email"],
            contract_file = f"contracts/{name}",
        )
        del request.session["staff_reg"]
        request.session["staff_id"]      = staff.pk
        request.session["is_staff_auth"] = True
        request.session["staff_role"]    = "staff"
        request.session["user_id"]       = staff.pk
        messages.success(request, "Реєстрацію завершено!")
        return redirect("staff_profile")
    return render(request, "register_staff.html", {"step": 6})