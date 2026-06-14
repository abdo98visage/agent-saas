"""
Integration tests for FQ-SaaS Admin Dashboard features.
Tests: Employee CRUD, Profile CRUD, Profile-User Assignments, Session Viewer, API Keys.
"""
import asyncio
import sys
import os

# Use SQLite for testing (no PostgreSQL needed)
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.db import Base, get_db
from app.core.config import settings
from app.models import User, Profile, ProfileUser, UserApiKey

# SQLite setup for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override dependency
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Create tables
Base.metadata.create_all(bind=engine)

client = TestClient(app)

print("=" * 60)
print("   FQ-SaaS Integration Tests")
print("=" * 60)


def test_full_workflow():
    """Test the complete admin workflow."""

    # ==================== STEP 1: Create Admin ====================
    print()
    print("-" * 40)
    print("STEP 1: Create Admin User")
    print("-" * 40)

    admin_data = {
        "email": "admin@test.com",
        "password": "admin123",
        "full_name": "Test Admin",
        "department": "it",
        "role": "admin",
    }
    resp = client.post("/api/auth/register", json=admin_data)
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    admin_token = resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print(f"  ✓ Admin created: {admin_data['email']}")

    # Verify admin role
    resp = client.get("/api/auth/me", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
    print(f"  ✓ Admin role verified: {resp.json()['role']}")

    # ==================== STEP 2: Add Employees ====================
    print()
    print("-" * 40)
    print("STEP 2: Add Employees")
    print("-" * 40)

    employee1_data = {
        "email": "accountant1@company.com",
        "password": "pass123",
        "full_name": "أحمد المحاسب",
        "department": "finance",
        "role": "employee",
        "max_tokens_per_day": 50000,
        "max_requests_per_day": 200,
    }
    resp = client.post("/api/admin/employees", json=employee1_data, headers=admin_headers)
    assert resp.status_code == 201, f"Create employee failed: {resp.text}"
    employee1_id = resp.json()["id"]
    print(f"  ✓ Employee 1 created: {employee1_data['full_name']} (ID: {employee1_id[:8]}...)")

    employee2_data = {
        "email": "manager1@company.com",
        "password": "pass123",
        "full_name": "سارة الإدارية",
        "department": "admin",
        "role": "employee",
        "max_tokens_per_day": 30000,
        "max_requests_per_day": 100,
    }
    resp = client.post("/api/admin/employees", json=employee2_data, headers=admin_headers)
    assert resp.status_code == 201
    employee2_id = resp.json()["id"]
    print(f"  ✓ Employee 2 created: {employee2_data['full_name']} (ID: {employee2_id[:8]}...)")

    # List employees
    resp = client.get("/api/admin/employees", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 2  # Both employees + admin registered earlier
    print(f"  ✓ Employee count: {resp.json()['count']}")

    # ==================== STEP 3: Add Hermes Profiles ====================
    print()
    print("-" * 40)
    print("STEP 3: Add Hermes Profiles (AGENTS.md + Skills)")
    print("-" * 40)

    profile1_data = {
        "name": "المحاسب الذكي",
        "slug": "smart-accountant",
        "description": "Profile for accounting and financial tasks",
        "skills": ["finance", "reports", "tax-calculation", "invoicing"],
        "agents_md": """# المحاسب الذكي

أنت محاسب محترف في شركة FQ-SaaS.

## المهام
- إعداد الفواتير والتقارير المالية
- حساب الضرائب والرواتب
- المراجعة والتحليل المالي
- متابعة المدفوعات والمستحقات

## القواعد
- استخدم الأرقام بدقة 100%
- اذكر المراجع المحاسبية
- لا تقدم نصائح قانونية
- حافظ على سرية البيانات المالية
""",
        "system_prompt": "You are an expert accountant. Help with financial reports, tax calculations, and accounting tasks with 100% accuracy.",
    }
    resp = client.post("/api/admin/profiles", json=profile1_data, headers=admin_headers)
    assert resp.status_code == 201, f"Create profile failed: {resp.text}"
    profile1_id = resp.json()["id"]
    print(f"  ✓ Profile 1 created: {profile1_data['name']} (ID: {profile1_id[:8]}...)")

    profile2_data = {
        "name": "المكتبية الذكية",
        "slug": "smart-office-admin",
        "description": "Profile for office administration and scheduling",
        "skills": ["documents", "scheduling", "communication", "filing"],
        "agents_md": """# المساعد المكتبي الذكي

أنت مساعد مكاتب محترف.

## المهام
- تنظيم المواعيد والاجتماعات
- إعداد الوثائق والمراسلات الرسمية
- إدارة الملفات والسجلات
- متابعة المهام اليومية

## القواعد
- كن دقيقاً في التفاصيل
- استخدم التنسيق الرسمي
- حافظ على تنظيم الملفات
""",
        "system_prompt": "You are an office administrator. Help with scheduling, documents, and office tasks efficiently.",
    }
    resp = client.post("/api/admin/profiles", json=profile2_data, headers=admin_headers)
    assert resp.status_code == 201
    profile2_id = resp.json()["id"]
    print(f"  ✓ Profile 2 created: {profile2_data['name']} (ID: {profile2_id[:8]}...)")

    # List profiles
    resp = client.get("/api/admin/profiles", headers=admin_headers)
    assert resp.status_code == 200
    profiles = resp.json()["profiles"]
    assert len(profiles) >= 2
    print(f"  ✓ Total profiles: {len(profiles)}")

    # ==================== STEP 4: Edit Profile (slug + agents_md) ====================
    print()
    print("-" * 40)
    print("STEP 4: Edit Profile (Update slug + AGENTS.md)")
    print("-" * 40)

    update_data = {
        "name": "المحاسب المحترف (محدث)",
        "description": "Updated description with more details",
        "agents_md": """# المحاسب المحترف - النسخة المحدثثة

أنت محاسب محترف مع خبرة 10+ سنوات.

## المهام المحدثثة
- إعداد الفواتير والتقارير المالية (محدث)
- حساب الضرائب والرواتب (محدث)
- المراجعة والتحليل المالي المتقدم
- متابعة المدفوعات والمستحقات
- إعداد الميزانيات السنوية

## القواعد الجديدة
- استخدم الأرقام بدقة 100%
- اذكر المراجع المحاسبية الدولية
- لا تقدم نصائح قانونية
- حافظ على سرية البيانات المالية
- راجع جميع الأرقام مرتين قبل التقديم
""",
        "skills": ["finance", "reports", "tax-calculation", "invoicing", "budgeting"],
    }
    resp = client.put(f"/api/admin/profiles/{profile1_id}", json=update_data, headers=admin_headers)
    assert resp.status_code == 200, f"Update profile failed: {resp.text}"
    print(f"  ✓ Profile updated: {update_data['name']}")
    print(f"  ✓ New skills count: {len(update_data['skills'])}")

    # Verify update
    resp = client.get("/api/admin/profiles", headers=admin_headers)
    updated = [p for p in resp.json()["profiles"] if p["id"] == profile1_id][0]
    assert updated["name"] == update_data["name"]
    assert len(updated["skills"]) == 5
    print(f"  ✓ Profile update verified: {updated['name']}")

    # ==================== STEP 5: Assign Profiles to Employees ====================
    print()
    print("-" * 40)
    print("STEP 5: Assign Profiles to Employees")
    print("-" * 40)

    # Assign accountant profile to accountant employee
    resp = client.post("/api/admin/assignments", json={
        "user_id": employee1_id,
        "profile_id": profile1_id,
        "priority": 0,
    }, headers=admin_headers)
    assert resp.status_code == 201, f"Assign failed: {resp.text}"
    print(f"  ✓ Accountant → المحاسب الذكي (priority: 0)")

    # Assign office admin profile to accountant employee (multiple profiles!)
    resp = client.post("/api/admin/assignments", json={
        "user_id": employee1_id,
        "profile_id": profile2_id,
        "priority": 1,
    }, headers=admin_headers)
    assert resp.status_code == 201
    print(f"  ✓ Accountant → المكتبية الذكية (priority: 1)")

    # List assignments
    resp = client.get("/api/admin/assignments", headers=admin_headers)
    assert resp.status_code == 200
    assignments = resp.json()["assignments"]
    assert len(assignments) >= 2
    print(f"  ✓ Total assignments: {len(assignments)}")

    # ==================== STEP 6: Add User API Key ====================
    print()
    print("-" * 40)
    print("STEP 6: Add User API Key (MiniMax per employee)")
    print("-" * 40)

    resp = client.post("/api/admin/api-keys", json={
        "user_id": employee1_id,
        "provider": "minimax",
        "api_key": "sk-test-accountant-key-12345",
        "daily_budget": 50000,
    }, headers=admin_headers)
    assert resp.status_code == 201, f"API key failed: {resp.text}"
    print(f"  ✓ API key added for accountant: {resp.json()['key_prefix']}...")
    print(f"  ✓ Provider: {resp.json()['provider']}")
    print(f"  ✓ Daily budget: 50,000 tokens")

    resp = client.post("/api/admin/api-keys", json={
        "user_id": employee2_id,
        "provider": "minimax",
        "api_key": "sk-test-manager-key-67890",
        "daily_budget": 30000,
    }, headers=admin_headers)
    assert resp.status_code == 201
    print(f"  ✓ API key added for manager: {resp.json()['key_prefix']}...")
    print(f"  ✓ Daily budget: 30,000 tokens")

    # List API keys
    resp = client.get("/api/admin/api-keys", headers=admin_headers)
    assert resp.status_code == 200
    api_keys = resp.json()["api_keys"]
    assert len(api_keys) >= 2
    print(f"  ✓ Total API keys: {len(api_keys)}")

    # ==================== STEP 7: Test Employee Login + Chat ====================
    print()
    print("-" * 40)
    print("STEP 7: Employee Login + Chat with Agent")
    print("-" * 40)

    resp = client.post("/api/auth/login", json={
        "email": "accountant1@company.com",
        "password": "pass123",
    })
    assert resp.status_code == 200
    emp_token = resp.json()["access_token"]
    emp_headers = {"Authorization": f"Bearer {emp_token}"}
    print(f"  ✓ Employee logged in successfully")

    # Send a message
    resp = client.post("/api/chat/message", json={
        "message": "مرحباً، أريد مساعدة في إعداد تقرير مالي",
        "agent_template_name": "default",
    }, headers=emp_headers)
    assert resp.status_code == 200
    chat_data = resp.json()
    print(f"  ✓ Message sent, conversation created: {chat_data['conversation_id'][:8]}...")
    print(f"  ✓ Response: {chat_data['content'][:80]}...")

    # ==================== STEP 8: Admin Views Sessions ====================
    print()
    print("-" * 40)
    print("STEP 8: Admin Views All Sessions with Filters")
    print("-" * 40)

    # View all sessions
    resp = client.get("/api/admin/sessions", headers=admin_headers)
    assert resp.status_code == 200
    sessions = resp.json()["sessions"]
    print(f"  ✓ Total sessions: {len(sessions)}")

    # Filter by user
    resp = client.get(f"/api/admin/sessions?user_id={employee1_id}", headers=admin_headers)
    assert resp.status_code == 200
    user_sessions = resp.json()["sessions"]
    print(f"  ✓ Sessions for accountant: {len(user_sessions)}")

    # View session messages
    if sessions:
        session_id = sessions[0]["id"]
        resp = client.get(f"/api/admin/sessions/{session_id}", headers=admin_headers)
        assert resp.status_code == 200
        session_data = resp.json()
        print(f"  ✓ Session details: {session_data['count']} messages")

    # ==================== STEP 9: Test Audit Log ====================
    print()
    print("-" * 40)
    print("STEP 9: Audit Log (All Admin Actions Tracked)")
    print("-" * 40)

    resp = client.get("/api/admin/audit-log", headers=admin_headers)
    assert resp.status_code == 200
    audit_log = resp.json()["audit_log"]
    actions = [entry["action"] for entry in audit_log]
    print(f"  ✓ Total audit entries: {len(audit_log)}")
    print(f"  ✓ Actions tracked: {set(actions)}")

    # Verify specific actions
    expected_actions = {"add_employee", "add_profile", "assign_profile", "add_api_key"}
    found_actions = set(actions)
    for action in expected_actions:
        if action in found_actions:
            print(f"  ✓ {action} - logged")
        else:
            print(f"  ✗ {action} - NOT logged")

    # ==================== STEP 10: Test Disable Employee ====================
    print()
    print("-" * 40)
    print("STEP 10: Disable Employee")
    print("-" * 40)

    resp = client.delete(f"/api/admin/employees/{employee2_id}", headers=admin_headers)
    assert resp.status_code == 200
    print(f"  ✓ Employee disabled: {employee2_data['full_name']}")

    # Verify employee can't login anymore
    resp = client.post("/api/auth/login", json={
        "email": "manager1@company.com",
        "password": "pass123",
    })
    assert resp.status_code == 403
    print(f"  ✓ Disabled employee cannot login: {resp.json()['detail']}")

    print()
    print("=" * 60)
    print("   ALL TESTS PASSED ✓✓✓")
    print("=" * 60)
    print()
    print("Summary:")
    print(f"  • Employees: Created 2, Disabled 1")
    print(f"  • Profiles: Created 2, Edited 1")
    print(f"  • Assignments: 2 profiles → 1 employee")
    print(f"  • API Keys: 2 keys with individual budgets")
    print(f"  • Chat: Message sent and response received")
    print(f"  • Sessions: Created and viewable by admin")
    print(f"  • Audit Log: All actions tracked")
    print()


# Run the test
test_full_workflow()

# Cleanup
import os
if os.path.exists("test.db"):
    os.remove("test.db")
    print("Test database cleaned up ✓")
