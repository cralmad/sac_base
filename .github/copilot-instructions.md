# SAC Base Project Instructions

## Overview
This is a fresh Django 6.0 project named `sac_base`, generated using `django-admin startproject`. It follows standard Django conventions with no custom apps or models implemented yet.

## Architecture
- **Framework**: Django 6.0
- **Pattern**: MTV (Model-Template-View)
- **Database**: SQLite3 (default, configured in [sac_base/settings.py](sac_base/settings.py))
- **Key Components**:
  - Project settings: [sac_base/settings.py](sac_base/settings.py)
  - URL routing: [sac_base/urls.py](sac_base/urls.py)
  - WSGI/ASGI configs: [sac_base/wsgi.py](sac_base/wsgi.py) and [sac_base/asgi.py](sac_base/asgi.py)

## Critical Workflows
- **Start development server**: `python manage.py runserver`
- **Apply migrations**: `python manage.py migrate`
- **Create admin user**: `python manage.py createsuperuser`
- **Create new app**: `python manage.py startapp <app_name>` (then add to INSTALLED_APPS in settings)
- **Run tests**: `python manage.py test` (once tests are added)

## Conventions
- Settings module: `sac_base.settings` (set in manage.py and configs)
- Admin interface available at `/admin/` (already routed in urls.py)
- Use `BASE_DIR` from pathlib for path handling (as in settings.py)
- Default INSTALLED_APPS include Django contrib apps; add custom apps there

## Patterns
- No custom patterns established yet; follow Django best practices for new features
- Example URL pattern: `path('admin/', admin.site.urls)` in [sac_base/urls.py](sac_base/urls.py)